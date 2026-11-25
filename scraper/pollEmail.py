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

    response = requests.post(GITHUB_API_URL, json=payload, headers=headers, timeout=15)
    if response.status_code == 204:
        print("✅ GitHub Action triggered successfully.")
        return True
    print(f"❌ Failed to trigger GitHub Action: HTTP {response.status_code}")
    return False


# Keep these searches aligned with lgl_forwarding.search_unread_lgl.
# Approved staff forwards do not have the LGL address in their outer From.
SEARCH_CRITERIA = (
    f'(UNSEEN FROM "{FROM_FILTER}")',
    '(UNSEEN SUBJECT "Fwd: New Submission:")',
)


def check_for_unread_lgl_emails(mail):
    """Dispatch once if a direct OR forwarded LGL notification is unread.

    This is only a lightweight wake-up; production getLglFormData validates
    original senders, forwarding headers, form titles, and amounts. No flags
    are modified here.
    """
    unread_ids = set()
    for criteria in SEARCH_CRITERIA:
        status, response = mail.search(None, criteria)
        if status != "OK" or not response:
            print("⚠️ Error searching mailbox.")
            return False
        unread_ids.update(response[0].split())

    if unread_ids:
        print(f"📧 Found {len(unread_ids)} matching unread notification(s). Triggering GitHub Action...")
        return trigger_github_action()
    print("💤 No unread direct or forwarded LGL notifications found.")
    return False


def poll_once():
    """Perform one real poll and dispatch without starting an endless loop."""
    mail = connect_mailbox()
    try:
        return check_for_unread_lgl_emails(mail)
    finally:
        mail.logout()


def main(once=False):
    if once:
        return poll_once()
    while True:
        try:
            poll_once()
        except Exception as e:
            print(f"❌ Error during polling: {e}")
        time.sleep(IDLE_TIMEOUT)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Poll LGL inbox and notify CWKC")
    parser.add_argument(
        "--once", action="store_true",
        help="Poll once and exit; does not modify mail read/unread flags",
    )
    main(once=parser.parse_args().once)
