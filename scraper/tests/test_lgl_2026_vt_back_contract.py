"""VT 2026 backend LGL email contract, rebuilt with invented donor information.

The verified November 6 notification has a single generic "Grad Year" tied to
the related student even when donor affiliations include "Alum". That must
fail closed until the real form supplies the donor's own year separately.
No real donors, message IDs, payment records or external services are used.
"""
from email.message import EmailMessage
from html import escape
from unittest.mock import MagicMock

import pandas as pd
import pytest

from scraper.CalculateValues import CalculateValues
from scraper.EmailParser import EmailParser, determine_source
from scraper.donation_ledger import NORMALIZED_FIELDS
from scraper.getLglFormData import (
    parse_lgl_email, process_messages, validate_submission,
)


VT_BACK_2026_FIELDS = [
    ("Form title", "CWKC 2026 Back End Form (Virginia Tech)"),
    ("Submission ID", "synthetic-vt-back-id"),
    ("Submission Date", "2026-11-06 18:15:09 -0500"),
    ("Gift Amount", "20"),
    ("Date", "11/07/2026"),
    ("Is this a monthly gift?", "No"),
    ("Passthrough from", "Check"),
    ("Check Number", "TEST-CHECK-0001"),
    ("Other", ""),
    ("Transaction Details", "Gift in hand"),
    ("Gift Notes", "synthetic test record"),
    ("Name - Prefix", ""),
    ("Name - First Name", "Example"),
    ("Name - Last Name", "Donor"),
    ("Name - Suffix", ""),
    ("Email", "vt-backend@example.invalid"),
    ("Phone", "5550102028"),
    ("Address - Address Line 1", "100 Example Avenue"),
    ("Address - Address Line 2", ""),
    ("Address - City", "Sampletown"),
    ("Address - State/Province", "AZ"),
    ("Address - ZIP/Postal Code", "00000"),
    ("Address - Country", "United States"),
    ("Donor is a/an...", "Current Parent||Alum"),
    ("What is their name? - Prefix", ""),
    ("What is their name? - First Name", "Sample"),
    ("What is their name? - Last Name", "Student"),
    ("What is their name? - Suffix", ""),
    ("Grad Year", "2028"),  # Student's year, NOT donor's alumni year.
    ("What Is Their Email?", "student@example.invalid"),
    ("What Is Their Phone Number?", "5550100000"),
    ("Is This Gift Being Matched by Their Workplace?", "No"),
    ("Employer Name:", ""),
    ("Check All That Apply",
     "Donor's first gift to Hillel at VT||Donor asking to match gift||"
     "Donor wants to be anonymous"),
    ("Is Recurring", "false"),
]


def _mime(fields=VT_BACK_2026_FIELDS):
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in fields
    )
    msg = EmailMessage()
    msg["From"] = "Hillel at VT <lglforms-submissions@littlegreenlight.com>"
    msg["To"] = "office@example.invalid, service@example.invalid"
    msg["Subject"] = (
        "You just got a new submission -- "
        "CWKC 2026 Back End Form (Virginia Tech)"
    )
    msg.set_content(
        f"<p><table>{rows}</table></p>",
        subtype="html", charset="utf-8", cte="quoted-printable",
    )
    assert not msg.is_multipart()
    assert msg.get_content_type() == "text/html"
    assert msg["Content-Transfer-Encoding"] == "quoted-printable"
    return msg.as_bytes()


def _corrected_fields(*, donor_year="2006", student_year="2028"):
    fields = []
    for label, value in VT_BACK_2026_FIELDS:
        if label == "Grad Year":
            fields.append(("Alumni Graduation Year", donor_year))
            fields.append(("Related Student Graduation Year", student_year))
        else:
            fields.append((label, value))
    return fields


def _parse_and_normalize(fields):
    sender, data = parse_lgl_email(_mime(fields))
    source = determine_source(sender, data["Form title"])
    row = EmailParser().normalize(data, source)
    validate_submission(data, row)
    assert tuple(row) == NORMALIZED_FIELDS
    return data, row


def test_vt_backend_original_contract_is_unsafe_without_donor_year():
    sender, raw = parse_lgl_email(_mime())
    assert determine_source(sender, raw["Form title"]) == "vt-back"
    assert raw["Gift Amount"] == "20"
    assert raw["Donor is a/an..."] == "Current Parent||Alum"
    assert raw["Grad Year"] == "2028"
    assert "Alumni Graduation Year" not in raw
    with pytest.raises(ValueError, match="VT backend donor alumni year"):
        EmailParser().normalize(raw, "vt-back")


@pytest.mark.parametrize("student_year", ["2026", "2028"])
def test_bad_vt_backend_year_stays_unread_with_no_sheet_write(student_year):
    fields = [
        (label, student_year) if label == "Grad Year" else (label, value)
        for label, value in VT_BACK_2026_FIELDS
    ]
    server = MagicMock()
    server.fetch.return_value = {73: {b"BODY[]": _mime(fields)}}
    ledger = MagicMock()
    ledger.known.return_value = False
    result = process_messages(server, [73], ledger)
    assert result == {"new": 0, "already_stored": 0, "pending": 0, "failed": 1}
    server.fetch.assert_called_once_with(73, ["BODY.PEEK[]"])
    ledger.insert.assert_not_called()
    server.add_flags.assert_not_called()


def test_distinct_backend_years_recognize_all_actual_labels_and_flags():
    raw, row = _parse_and_normalize(_corrected_fields())
    assert raw["Related Student Graduation Year"] == "2028"
    assert raw["Alumni Graduation Year"] == "2006"
    assert row["source"] == "vt-back"
    assert row["total amount"] == "20.0"
    assert row["status"] == "Alumni, Current Parent"
    assert row["graduation year"] == "2006"
    assert row["recurring payment"] == "false"
    assert row["anonymous donation"] == "true"
    assert row["first time giver"] == "true"
    assert row["work referral"] == "true"


def test_corrected_vt_backend_scores_once_with_independent_categories():
    _, row = _parse_and_normalize(_corrected_fields())
    calc = CalculateValues.__new__(CalculateValues)
    calc.df = pd.DataFrame([{
        **row,
        "total amount": float(row["total amount"]),
        "recurring payment": False,
    }])
    vt = calc.calculate_all()["vt"]
    assert vt["total_amount"] == 20
    assert vt["most_individual_donors"] == 1
    assert vt["most_first_time_donors"] == 1
    assert vt["most_money_families"] == 20
    assert vt["most_alum_work_matched"] == 1
    assert vt["donor_names"] == ""
    assert vt["most_donors_class_2026"] == 0
    assert vt["most_gifts_over_1000"] == 0
    assert vt["most_alum_monthly_10_plus"] == 0


def test_student_year_2028_does_not_obscure_actual_2026_alumni_year():
    _, row = _parse_and_normalize(_corrected_fields(donor_year="2026"))
    assert row["graduation year"] == "2026"
    calc = CalculateValues.__new__(CalculateValues)
    calc.df = pd.DataFrame([{
        **row,
        "total amount": 20.0,
        "recurring payment": False,
    }])
    assert calc.calculate_all()["vt"]["most_donors_class_2026"] == 1


def test_vt_backend_parent_only_student_grad_year_is_not_donor_year():
    fields = [
        (label, "Current Parent") if label == "Donor is a/an..." else
        (label, value)
        for label, value in VT_BACK_2026_FIELDS
    ]
    _, row = _parse_and_normalize(fields)
    assert row["status"] == "Current Parent"
    assert row["graduation year"] == ""
    assert row["total amount"] == "20.0"


@pytest.mark.parametrize("answer, expected", [
    ("Yes", "true"), ("No", "false"),
])
def test_vt_backend_their_workplace_radio_is_recognized(answer, expected):
    fields = [
        (label, answer)
        if label == "Is This Gift Being Matched by Their Workplace?"
        else (label, "")
        if label == "Check All That Apply"
        else (label, value)
        for label, value in _corrected_fields()
    ]
    _, row = _parse_and_normalize(fields)
    assert row["work referral"] == expected


def test_backend_no_matching_box_does_not_create_match_credit():
    fields = [
        (label, "No")
        if label == "Is This Gift Being Matched by Their Workplace?"
        else (label, "Donor wants to be anonymous")
        if label == "Check All That Apply"
        else (label, value)
        for label, value in _corrected_fields()
    ]
    _, row = _parse_and_normalize(fields)
    assert row["work referral"] == "false"
    assert row["anonymous donation"] == "true"
