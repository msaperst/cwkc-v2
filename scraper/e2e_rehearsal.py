"""Isolated 2026 integration rehearsal: LGL MIME -> Sheet -> CSV -> browser.

Default is OFFLINE and uses in-memory gspread-compatible test doubles.
--sandbox writes ONLY 10 invented donation rows to a new worksheet in a
separately designated, explicitly named sandbox Google spreadsheet. It never
connects to a live mailbox, real Forms response sheets, or the results branch.
"""
import argparse
import csv
import json
import os
import re
from email.message import EmailMessage
from html import escape
from pathlib import Path
from unittest.mock import patch

import gspread

from . import getLglFormData as importer
from .audit_lgl import FORM_TITLES
from .donation_ledger import NORMALIZED_FIELDS, SUBMISSION_ID, SubmissionLedger
from .getGoogleFormData import (
    CURRENT_TAB, GATHERING_FIELDS, GATHERING_SHEET_ID, HANUKKAH_FIELDS,
    HANUKKAH_SHEET_ID, SubmissionUpdater,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_TEMPLATE = ROOT / "public/assets/csv/results.csv"
RESULTS_PREVIEW = Path(".cwkc-e2e-results.csv")
RESULTS_REPORT = Path(".cwkc-e2e-report.json")
SANDBOX_TITLE = "CWKC-E2E-SANDBOX"
EXPECTED = {
    "uva_total_amount": 269.68,
    "vt_total_amount": 373.00,
    "uva_most_individual_donors": 2,
    "vt_most_individual_donors": 2,
    "uva_most_alum_work_matched": 3,
    "vt_most_alum_work_matched": 3,
    "uva_most_first_time_donors": 1,
    "vt_most_first_time_donors": 1,
    "uva_most_donors_class_2026": 0,
    "vt_most_donors_class_2026": 0,
    "uva_most_gifts_over_1000": 0,
    "vt_most_gifts_over_1000": 0,
    "uva_most_alum_monthly_10_plus": 0,
    "vt_most_alum_monthly_10_plus": 1,
    "uva_most_money_families": 264.68,
    "vt_most_money_families": 373.00,
    "uva_most_money_grandparents_current_students": 0,
    "vt_most_money_grandparents_current_students": 0,
    "uva_alumni_gatherings": 1,
    "vt_alumni_gatherings": 1,
    "uva_hanukkah_photos": 1,
    "vt_hanukkah_photos": 2,
}


def _notification(source, amount, number, attributes, *, donor=1):
    """Construct a synthetic quoted-printable LGL notification, no real PII."""
    school = source.split("-")[0]
    is_backend = source.endswith("-back")
    data = [
        ("Form title", FORM_TITLES[source]),
        ("Submission ID", f"synthetic-{number:02d}"),
        ("Submission Date", f"2026-11-{6 if number < 5 else 10:02d} 10:00:00 -0500"),
        ("Gift amount" if is_backend else "Total Amount", str(amount)),
        ("Name - First Name", f"Example{school.upper()}"),
        ("Name - Last Name", f"Donor{donor}"),
        ("Phone", f"555010{1 if school == 'uva' else 2}{donor:03d}"),
        ("Email", f"e2e-{school}-{donor}@example.invalid"),
        *attributes,
        ("Is Recurring", "false"),
    ]
    table = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in data
    )
    sender = "Brody Jewish Center" if school == "uva" else "Hillel at VT"
    message = EmailMessage()
    message["From"] = f"{sender} <lglforms-submissions@littlegreenlight.com>"
    message["To"] = "synthetic-audit@example.invalid"
    message["Subject"] = f"Synthetic LGL {number}"
    message.set_content(
        f"<p><table>{table}</table></p>",
        subtype="html", charset="utf-8", cte="quoted-printable",
    )
    return message.as_bytes()


def messages():
    """Ten fake gifts reproduce the confirmed Nov 6–10 score totals."""
    return {
        101: _notification("uva-front", "$5.00", 1, [
            ("I am a/an", "Alum"), ("Grad Year", "2006"),
            ("Check all that apply", "This is my first gift to Hillel at UVA"),
            ("Does your workplace match charitable giving?",
             "Yes! I'll go ahead and ask them"),
        ]),
        102: _notification("uva-back", "0.01", 2, [
            ("Donor is a/n...", "Parent of an Alum"),
            ("Grad Year", "2016"),
            ("Is this a monthly gift?", "Yes"),
            ("Check all that apply", "Donor asking to match gift"),
        ]),
        103: _notification("vt-front", "$5.00", 3, [
            ("I am a/an...", "Current Parent||Alumni"),
            ("Graduation Year", "2006"),
            ("Graduation Year", "2028"),
            ("Does Your Workplace Match Charitable Giving?",
             "I'm not sure, can you look into it for me?"),
        ]),
        104: _notification("vt-back", "20", 4, [
            ("Donor is a/an...", "Current Parent||Alum"),
            ("Grad Year", "2028"), ("Is this a monthly gift?", "No"),
            ("Check All That Apply", "Donor asking to match gift"),
        ]),
        105: _notification("vt-front", "$103.00", 5, [
            ("I am a/an...", "Current Parent"),
            ("Related Student Graduation Year", "2029"),
            ("Amount - Details", "Amount: $100.00"),
        ], donor=2),
        106: _notification("uva-front", "$257.50", 6, [
            ("I am a/an", "Family member of an Alum"),
            ("Amount - Details", "Support the program: $250.00"),
            ("Check all that apply",
             "Please don't list my name. I would like to remain anonymous."),
        ], donor=2),
        107: _notification("uva-front", "$5.00", 7, [
            ("I am a/an", "Current Parent||Alum"),
            ("Alumni Grad Year", ""), ("Related Grad Year", "2028"),
            ("Check all that apply", "This is my first gift to Hillel at UVA||"
             "Please don't list my name. I would like to remain anonymous."),
            ("Does your workplace match charitable giving?",
             "I'm not sure, can you look into it for me?"),
        ]),
        108: _notification("vt-front", "$5.00", 8, [
            ("I am a/an...", "Graduate Student||Current Parent||Alumni"),
            ("Intended Graduation Year", "2027"),
            ("Alumni Graduation Year", "2006"),
            ("Related Student Graduation Year", "2028"),
            ("Check All That Apply:", "This is my first gift to Hillel at VT"),
            ("Does Your Workplace Match Charitable Giving?",
             "Yes! I'll go ahead and ask them"),
        ]),
        109: _notification("vt-back", "20", 9, [
            ("Donor is a/an...", "Current Parent||Alum"),
            ("Alumni Graduation Year", "2006"),
            ("Related Student Graduation Year", "2027"),
            ("Is this a monthly gift?", "Yes"),
            ("Gift Notes", "TEST GIFT"),
        ]),
        110: _notification("uva-back", "2.06", 10, [
            ("Donor is a/n...", "Current Parent||Alum"),
            ("Alumni Grad Year", ""), ("Related Grad Year", "2026"),
            ("Is this a monthly gift?", "No"),
            ("Is this gift being matched by workplace?", "Yes"),
        ]),
    }


class SimulatedIMAP:
    """Only local messages; never instantiate the real IMAPClient."""
    def __init__(self):
        self.mail = messages()
        self.flags = []

    def fetch(self, uid, parts):
        assert parts == ["BODY.PEEK[]"]
        return {uid: {b"BODY[]": self.mail[uid]}}

    def add_flags(self, uid, flags):
        assert flags == ["\\Seen"]
        self.flags.append(uid)


class MemoryWorksheet:
    def __init__(self, rows=()):
        self.rows = [list(map(str, row)) for row in rows]

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def row_values(self, index):
        return self.rows[index - 1] if len(self.rows) >= index else []

    def append_row(self, values, value_input_option="RAW"):
        assert value_input_option == "RAW"
        self.rows.append([str(value) for value in values])

    def update_cell(self, row, col, value):
        self.rows[row - 1][col - 1] = value

    def get_all_records(self):
        if not self.rows:
            return []
        return [
            dict(zip(self.rows[0], row)) for row in self.rows[1:]
        ]


class MemorySpreadsheet:
    def __init__(self, title="OFFLINE SANDBOX", tabs=None):
        self.title = title
        self.tabs = tabs or {}

    def worksheet(self, name):
        if name not in self.tabs:
            raise gspread.WorksheetNotFound(name)
        return self.tabs[name]

    def add_worksheet(self, title, rows, cols):
        assert title not in self.tabs
        self.tabs[title] = MemoryWorksheet()
        return self.tabs[title]


class MemoryClient:
    def __init__(self, sheets):
        self.sheets = sheets

    def open_by_key(self, key):
        return self.sheets[key]


def synthetic_form_client():
    """Fake actual LGL-independent Google Forms response worksheet reads."""
    gathering_headers = list(GATHERING_FIELDS.values())
    photo_headers = list(HANUKKAH_FIELDS.values())

    def row(fields, values):
        return [values.get(name, "") for name in fields]

    gatherings = [
        row(gathering_headers, {
            "timestamp": "11/30/2026 10:00:00", "name": "Synthetic Host One",
            "which school are you supporting?": "UVA", "affiliation": "Alumni",
            "who was in attendance at your event?": "One, Two, Three, Four",
            "where was your event?": "UVA House",
            "please submit photos of your event!": "https://example.invalid/uva.jpg",
        }),
        row(gathering_headers, {
            "timestamp": "12/01/2026 10:00:00", "name": "Synthetic Host Two",
            "which school are you supporting?": "Virginia Tech",
            "affiliation": "Current Parent",
            "who was in attendance at your event?": "Five, Six, Seven, Eight",
            "where was your event?": "VT House",
            "please submit photos of your event!": "https://example.invalid/vt.jpg",
        }),
    ]
    photos = [
        row(photo_headers, {
            "timestamp": "12/01/2026", "name": f"Synthetic Participant {i}",
            "non-school affiliated email": f"participant-{i}@example.invalid",
            "which school are you supporting?": school,
            "are you an alumni that graduated in the past 15 years, or a parent of one?": "Yes",
            "graduation year (if applicable)": "2020",
            "submit your photo here!": "https://example.invalid/photo.jpg",
        }) for i, school in enumerate(("UVA", "VT", "VT"), 1)
    ]
    return MemoryClient({
        GATHERING_SHEET_ID: MemorySpreadsheet(tabs={
            CURRENT_TAB: MemoryWorksheet([gathering_headers, *gatherings])
        }),
        HANUKKAH_SHEET_ID: MemorySpreadsheet(tabs={
            CURRENT_TAB: MemoryWorksheet([photo_headers, *photos])
        }),
    })


def _client(mode, run_name):
    if mode == "offline":
        key = "offline-synthetic-sheet"
        return MemoryClient({key: MemorySpreadsheet()}), key

    key = os.environ.get("CWKC_E2E_SPREADSHEET_KEY", "")
    production_key = os.environ.get("SPREADSHEET_KEY", "")
    if (not key or not production_key or key == production_key
            or not re.fullmatch(r"[a-zA-Z0-9_-]{20,}", key)):
        raise ValueError("A distinct sandbox spreadsheet key and production comparison are required")
    client = gspread.service_account(filename="spreadsheet_credentials.json")
    sheet = client.open_by_key(key)
    if sheet.title != SANDBOX_TITLE:
        raise ValueError("Target spreadsheet must be named CWKC-E2E-SANDBOX")
    try:
        sheet.worksheet(run_name)
    except gspread.WorksheetNotFound:
        pass
    else:
        raise ValueError("Sandbox worksheet already exists; use a new run")
    return client, key


def _assert_csv_and_sheet(worksheet, path):
    headers = worksheet.row_values(1)
    assert headers == [*NORMALIZED_FIELDS, SUBMISSION_ID]
    records = worksheet.get_all_records()
    assert len(records) == 10
    assert len({str(r[SUBMISSION_ID]) for r in records}) == 10
    assert all(str(r["phone number"]).startswith("555010") for r in records)
    assert all(str(r["source"]) in FORM_TITLES for r in records)

    with RESULTS_TEMPLATE.open(newline="", encoding="utf-8") as stream:
        expected_headers = next(csv.reader(stream))
    with path.open(newline="", encoding="utf-8") as stream:
        parsed = list(csv.DictReader(stream))
    assert len(parsed) == 1
    assert list(parsed[0]) == expected_headers
    for field, expected in EXPECTED.items():
        actual = float(parsed[0][field])
        if abs(actual - expected) > 0.001:
            raise AssertionError(f"Unexpected {field}: {actual}, expected {expected}")
    assert parsed[0]["uva_football_score"] == "0"
    assert parsed[0]["vt_football_score"] == "0"
    return parsed[0]


def run(mode="offline"):
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", run_id + attempt):
        raise ValueError("Invalid run identity")
    sheet_name = f"E2E_{run_id}_{attempt}"
    # No remote IMAP: parse only generated fake MIME messages.
    client, key = _client(mode, sheet_name)
    ledger = SubmissionLedger(client, key, sheet_name, NORMALIZED_FIELDS, sleeper=lambda _: None)
    server = SimulatedIMAP()
    uids = sorted(server.mail)
    first = importer.process_messages(server, uids, ledger)
    assert first == {"new": 10, "already_stored": 0, "pending": 0, "failed": 0}
    second = importer.process_messages(server, uids, ledger)
    assert second == {"new": 0, "already_stored": 10, "pending": 0, "failed": 0}
    assert server.flags == uids + uids  # synthetic-only IMAP acknowledgements

    # Both real production CSV construction and actual worksheet reload.
    import shutil
    shutil.copyfile(RESULTS_TEMPLATE, RESULTS_PREVIEW)
    with patch("gspread.service_account", return_value=client), \
         patch.object(importer, "SPREADSHEET_KEY", key), \
         patch.object(importer, "SPREADSHEET_SHEET", sheet_name), \
         patch.object(importer, "CSV_PATH", str(RESULTS_PREVIEW)):
        importer.update_local_csv()

    # Exercise real Forms column parsing and CSV write using fake response tabs.
    with patch("gspread.service_account", return_value=synthetic_form_client()):
        updater = SubmissionUpdater("synthetic-only", str(RESULTS_PREVIEW))
        updater.update_results(dry_run=False)

    final = _assert_csv_and_sheet(client.open_by_key(key).worksheet(sheet_name), RESULTS_PREVIEW)
    summary = {
        "mode": mode, "synthetic_messages": len(uids),
        "inserted": first["new"], "replay_duplicates": second["already_stored"],
        "worksheet": sheet_name, "fields_checked": len(EXPECTED),
        "csv_columns": len(final), "browser_fixture": RESULTS_PREVIEW.name,
        "result": "passed",
    }
    RESULTS_REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Synthetic email → sheet → scoring → CSV rehearsal passed")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Isolated CWKC end-to-end rehearsal")
    parser.add_argument("--mode", choices=("offline", "sandbox"), default="offline")
    args = parser.parse_args()
    run(mode=args.mode)


if __name__ == "__main__":
    main()
