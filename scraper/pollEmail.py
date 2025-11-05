import imaplib
import os
import time

import requests
from dotenv import load_dotenv

# ====== CONFIGURATION ======
load_dotenv()  # .env file in same directory

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "msaperst/cwkc-v2")
EVENT_TYPE = os.getenv("GITHUB_EVENT_TYPE", "lgl-form-submission")
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"

MAILBOX = os.getenv("MAILBOX", "INBOX")
FROM_FILTER = os.getenv("FROM_FILTER", "lglforms-submissions@littlegreenlight.com")

IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT_SECONDS", "60"))  # seconds between polls


# ===========================


def connect_mailbox():
    """Connect to Gmail IMAP and select the mailbox."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select(MAILBOX)
    return mail


def trigger_github_action():
    """Trigger the GitHub Actions workflow for an LGL form submission."""
    payload = {
        "event_type": EVENT_TYPE,
        "client_payload": {
            "message": f"New unread email from {FROM_FILTER} detected"
        },
    }
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.post(GITHUB_API_URL, json=payload, headers=headers)
    if response.status_code == 204:
        print("✅ GitHub Action triggered successfully.")
    else:
        print(f"❌ Failed to trigger GitHub Action: {response.status_code} - {response.text}")


def check_for_unread_lgl_emails(mail):
    """Check for unread emails from the LGL sender."""
    status, response = mail.search(None, f'(UNSEEN FROM "{FROM_FILTER}")')
    if status != "OK":
        print("⚠️ Error searching mailbox.")
        return False

    unread_ids = response[0].split()
    if unread_ids:
        print(f"📧 Found {len(unread_ids)} unread email(s) from {FROM_FILTER}. Triggering GitHub Action...")
        trigger_github_action()
        return True
    else:
        print("💤 No unread emails from LGL found.")
        return False


def main():
    while True:
        try:
            mail = connect_mailbox()
            check_for_unread_lgl_emails(mail)
            mail.logout()
        except Exception as e:
            print(f"❌ Error during polling: {e}")
        time.sleep(IDLE_TIMEOUT)


if __name__ == "__main__":
    main()
