# tests/test_pollEmail.py
import io
import sys
from unittest.mock import MagicMock

import pytest

from scraper import pollEmail


def test_connect_mailbox(monkeypatch):
    mock_mail = MagicMock()
    # Patch imaplib.IMAP4_SSL to return our mock
    monkeypatch.setattr(pollEmail.imaplib, "IMAP4_SSL", lambda server: mock_mail)
    mock_mail.login = MagicMock()
    mock_mail.select = MagicMock()

    mail = pollEmail.connect_mailbox()
    assert mail is mock_mail
    mail.login.assert_called_once_with(pollEmail.EMAIL_ACCOUNT, pollEmail.EMAIL_PASSWORD)
    mail.select.assert_called_once_with(pollEmail.MAILBOX)


def test_check_for_unread_lgl_emails_triggers(monkeypatch):
    # Setup mock mailbox that returns one unread email
    mock_mail = MagicMock()
    mock_mail.search.return_value = ("OK", [b"1 2 3"])

    triggered = []

    def fake_trigger():
        triggered.append(True)

    monkeypatch.setattr(pollEmail, "trigger_github_action", fake_trigger)

    result = pollEmail.check_for_unread_lgl_emails(mock_mail)
    assert result is True
    assert triggered, "GitHub action should have been triggered"


def test_check_for_unread_lgl_emails_none(monkeypatch):
    # No unread emails
    mock_mail = MagicMock()
    mock_mail.search.return_value = ("OK", [b""])

    triggered = []

    def fake_trigger():
        triggered.append(True)

    monkeypatch.setattr(pollEmail, "trigger_github_action", fake_trigger)

    result = pollEmail.check_for_unread_lgl_emails(mock_mail)
    assert result is False
    assert not triggered, "GitHub action should NOT have been triggered"


def test_trigger_github_action(monkeypatch):
    # Patch requests.post to prevent real network call
    mock_post = MagicMock()
    mock_post.return_value.status_code = 204
    monkeypatch.setattr(pollEmail.requests, "post", mock_post)

    pollEmail.trigger_github_action()
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    assert payload["event_type"] == pollEmail.EVENT_TYPE


def test_main_runs_once(monkeypatch):
    mock_mail = MagicMock()

    # Patch mailbox connection and email checking
    monkeypatch.setattr(pollEmail, "connect_mailbox", lambda: mock_mail)
    monkeypatch.setattr(pollEmail, "check_for_unread_lgl_emails", lambda mail: True)

    # Patch time.sleep to break the loop immediately
    def fake_sleep(seconds):
        raise KeyboardInterrupt()  # stops infinite while True

    monkeypatch.setattr(pollEmail, "time", type("time", (), {"sleep": fake_sleep}))

    # Run main and ensure loop executes one iteration
    with pytest.raises(KeyboardInterrupt):
        pollEmail.main()

    mock_mail.logout.assert_called_once()


def test_check_for_unread_lgl_emails_search_error(monkeypatch):
    mock_mail = MagicMock()
    # Make search return something other than 'OK'
    mock_mail.search.return_value = ("NO", [])

    result = pollEmail.check_for_unread_lgl_emails(mock_mail)

    assert result is False
    mock_mail.search.assert_called_once_with(None, f'(UNSEEN FROM "{pollEmail.FROM_FILTER}")')


def test_trigger_github_action_failure_output(monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "Internal Server Error"

    monkeypatch.setattr(pollEmail.requests, "post", mock_post)

    captured = io.StringIO()
    sys.stdout = captured

    pollEmail.trigger_github_action()

    sys.stdout = sys.__stdout__
    assert "Failed to trigger GitHub Action" in captured.getvalue()


def test_main_error_handling(monkeypatch):
    # Patch connect_mailbox to raise an exception immediately
    def mock_connect_mailbox():
        raise Exception("Test exception")

    monkeypatch.setattr(pollEmail, "connect_mailbox", mock_connect_mailbox)

    # Patch time.sleep to raise StopIteration, so the loop exits after first iteration
    def stop_sleep(seconds):
        raise StopIteration

    monkeypatch.setattr(pollEmail.time, "sleep", stop_sleep)

    # Capture printed output
    captured = io.StringIO()
    sys.stdout = captured

    # Run main and let StopIteration break the loop
    try:
        pollEmail.main()
    except StopIteration:
        pass

    sys.stdout = sys.__stdout__
    output = captured.getvalue()
    assert "Error during polling: Test exception" in output
