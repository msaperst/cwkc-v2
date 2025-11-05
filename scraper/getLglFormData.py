import email
import os
from email.policy import default

import gspread
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from imapclient import IMAPClient

from scraper.EmailParser import EmailParser, determine_source

# ===== CONFIG =====
load_dotenv()  # assumes .env in same dir
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

MAILBOX = os.getenv("MAILBOX", "INBOX")
FROM_FILTER = os.getenv("FROM_FILTER", "lglforms-submissions@littlegreenlight.com")

SPREADSHEET_KEY = os.getenv("SPREADSHEET_KEY")
CSV_PATH = os.getenv("RESULTS_CSV", "../public/assets/csv/results.csv")


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


def update_google_sheet(gc, worksheet_name, normalized_row):
    sh = gc.open_by_key(SPREADSHEET_KEY)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows="1000", cols=str(len(normalized_row)))

    # Ensure the headers exist
    headers = ws.row_values(1)
    if not headers:
        ws.append_row(list(normalized_row.keys()))  # add headers if sheet is empty

    # Append the normalized row
    ws.append_row(list(normalized_row.values()))


def perform_calculations(df):
    """Stub function to calculate metrics from the sheet."""
    # For now, just a placeholder; implement your calculations
    df['TotalAmount'] = pd.to_numeric(df['Total Amount'].str.replace('$', ''), errors='coerce')
    # Example: sum donations
    df.loc[0, 'totalDonations'] = df['TotalAmount'].sum()
    return df


# ===== MAIN SCRIPT =====
def main():
    # Connect to Gmail
    with IMAPClient(IMAP_SERVER, ssl=True) as server:
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.select_folder(MAILBOX)

        # search for unread LGL emails
        uids = server.search(['UNSEEN', f'FROM', FROM_FILTER])
        if not uids:
            print("No unread LGL emails found.")
            return

        print(f"Found {len(uids)} unread LGL emails.")

        # Connect to Google Sheets
        normalizer = EmailParser()
        gc = gspread.service_account(filename='spreadsheet_credentials.json')

        for uid in uids:
            raw_msg = server.fetch(uid, ['RFC822'])[uid][b'RFC822']
            try:
                from_email, data = parse_lgl_email(raw_msg)
                print(from_email, data)
                normalized_row = normalizer.normalize(
                    data, determine_source(from_email, data.get("Form title", "")))
                update_google_sheet(gc, "entries", normalized_row)  # data is raw from parse_lgl_email
                server.add_flags(uid, ['\\Seen'])  # mark as read
                print(f"Processed email UID {uid}")
            except Exception as e:
                print(f"Failed to process email UID {uid}: {e}")

    # Update local CSV
    df = pd.read_csv(CSV_PATH)
    # df = perform_calculations(df)
    # df.to_csv(CSV_PATH, index=False)
    # print("Updated results.csv")


if __name__ == "__main__":
    main()
