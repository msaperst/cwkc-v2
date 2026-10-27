import argparse
import email
import math
import os
from email.policy import default

import gspread
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from imapclient import IMAPClient

from .CalculateValues import CalculateValues
from .EmailParser import EmailParser, determine_source
from .donation_ledger import NORMALIZED_FIELDS, SubmissionLedger, fingerprint

# ===== CONFIG =====
load_dotenv()  # assumes .env in same dir
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

MAILBOX = os.getenv("MAILBOX", "INBOX")
FROM_FILTER = os.getenv("FROM_FILTER", "lglforms-submissions@littlegreenlight.com")

SPREADSHEET_KEY = os.getenv("SPREADSHEET_KEY")
SPREADSHEET_SHEET = os.getenv("SPREADSHEET_SHEET", "entries")
CSV_PATH = os.getenv("RESULTS_CSV", "public/assets/csv/results.csv")


# ===== FUNCTIONS =====
def parse_lgl_email(raw_msg):
    """Parse an LGL email with a 2-column HTML table and return a dict of form fields."""
    msg = email.message_from_bytes(raw_msg, policy=default)
    email_from = msg.get("From", "")

    # Get the HTML part
    html_part = msg.get_body(preferencelist=('html'))
    if html_part is None:
        raise ValueError("Email has no HTML part")

    html = html_part.get_content()
    soup = BeautifulSoup(html, "html.parser")

    data = {}
    # Find the first table (assuming the form submission table is the first)
    table = soup.find("table")
    if not table:
        raise ValueError("No table found in email")

    # Iterate over rows
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            data[key] = val

    return email_from, data


def update_google_sheet(ledger: SubmissionLedger, normalized_row: dict,
                        submission_id: str) -> bool:
    """Insert one identified submission, or recognize a previously stored one."""
    return ledger.insert(normalized_row, submission_id)


def validate_submission(data: dict, normalized_row: dict) -> None:
    """Do not silently turn malformed live notifications into zero-dollar gifts."""
    if not ("Total Amount" in data or "Gift amount" in data):
        raise ValueError("Donation notification is missing its amount")
    amount = float(normalized_row["total amount"])
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Donation amount must be positive and finite")
    if normalized_row["source"].startswith("unknown"):
        raise ValueError("Donation notification has an unknown Hillel sender")


def handle_message(server, uid, ledger, normalizer, reconcile_only):
    """Handle one notification and return its summary category."""
    fetched = server.fetch(uid, ["BODY.PEEK[]"])
    raw = fetched[uid][b"BODY[]"]
    submission_id = fingerprint(raw)
    if reconcile_only:
        return "already_stored" if ledger.known(submission_id) else "pending"

    if ledger.known(submission_id):
        category = "already_stored"
    else:
        sender, data = parse_lgl_email(raw)
        normalized = normalizer.normalize(
            data, determine_source(sender, data.get("Form title", "")))
        validate_submission(data, normalized)
        if tuple(normalized) != NORMALIZED_FIELDS:
            raise ValueError("Normalized donation column contract changed")
        was_inserted = update_google_sheet(ledger, normalized, submission_id)
        category = "new" if was_inserted else "already_stored"
    # Only acknowledge an email after the normalized row is durable.
    server.add_flags(uid, ["\\Seen"])
    return category


def process_messages(server, uids: list, ledger: SubmissionLedger,
                     *, reconcile_only: bool = False) -> dict:
    """Process unread emails; never hide a failed notification from retries."""
    summary = {"new": 0, "already_stored": 0, "pending": 0, "failed": 0}
    normalizer = EmailParser()
    for uid in uids:
        try:
            category = handle_message(server, uid, ledger, normalizer, reconcile_only)
            summary[category] += 1
        except Exception as error:
            summary["failed"] += 1
            # Error messages can contain PII; print only type and mailbox UID.
            print(f"LGL UID {uid} failed ({type(error).__name__}); left unread")
    return summary

def update_local_csv():
    calc = CalculateValues(spreadsheet_key=SPREADSHEET_KEY)
    metrics = calc.calculate_all()
    df = pd.read_csv(CSV_PATH)

    for school_code, school_metrics in metrics.items():
        for metric_name, value in school_metrics.items():
            # Flatten any list or set into a comma-separated string
            if isinstance(value, (list, set)):
                value = ", ".join(map(str, value))

            # Construct CSV column name
            csv_col = f"{school_code}_{metric_name}"

            # If column exists in CSV, update; else optionally create
            if csv_col in df.columns:
                df[csv_col] = df[csv_col].astype(object)
                df.at[0, csv_col] = value
            else:
                # Optionally create the column if it doesn't exist
                df[csv_col] = pd.Series([value], dtype=object)

        # 5. Write CSV back
    df.to_csv(CSV_PATH, index=False)
    print("Local CSV updated successfully.")


# ===== MAIN SCRIPT =====
def main(argv=None):
    parser = argparse.ArgumentParser(description="Import unread CWKC LGL submissions")
    parser.add_argument(
        "--reconcile-only", action="store_true",
        help="Read-only preflight: count persisted vs pending unread messages",
    )
    args = parser.parse_args(argv)
    with IMAPClient(IMAP_SERVER, ssl=True) as server:
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.select_folder(MAILBOX)

        uids = server.search(["UNSEEN", "FROM", FROM_FILTER])
        print(f"Unseen LGL notifications: {len(uids)}")
        if uids:
            gc = gspread.service_account(filename="spreadsheet_credentials.json")
            ledger = SubmissionLedger(
                gc, SPREADSHEET_KEY, SPREADSHEET_SHEET,
                NORMALIZED_FIELDS, read_only=args.reconcile_only,
            )
            summary = process_messages(
                server, uids, ledger, reconcile_only=args.reconcile_only,
            )
            print("Reconciliation:", ", ".join(
                f"{key}={value}" for key, value in summary.items()))
            if ledger.legacy_rows:
                print(f"WARNING: {ledger.legacy_rows} existing unkeyed Sheet rows need reconciliation")
            if summary["failed"]:
                raise RuntimeError(
                    f"{summary['failed']} LGL notifications remain unprocessed; "
                    "blocking CSV publication"
                )
        if not args.reconcile_only:
            # No publication on partial email failure. A later run can resume
            # unread messages and recalculate from the durable Sheet.
            update_local_csv()


if __name__ == "__main__":
    main()
