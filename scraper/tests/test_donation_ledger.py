"""Synthetic, offline replay and quota-failure tests; no production accounts."""
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import gspread
import pytest
import requests

from scraper import getLglFormData as lgl
from scraper.donation_ledger import (
    NORMALIZED_FIELDS, SUBMISSION_ID, SubmissionLedger, fingerprint, retry,
)


class FakeSheet:
    def __init__(self, rows=None):
        self.rows = [list(x) for x in (rows or [])]
        self.append_error = None
        self.append_attempts = 0
        self.read_error = None

    def row_values(self, number):
        assert number == 1
        return list(self.rows[0]) if self.rows else []

    def get_all_values(self):
        if self.read_error is not None:
            error = self.read_error
            self.read_error = None
            raise error
        return [list(row) for row in self.rows]

    def update_cell(self, row, col, value):
        assert row == 1
        self.rows[0].extend([""] * (col - len(self.rows[0])))
        self.rows[0][col - 1] = value

    def append_row(self, values, *, value_input_option):
        assert value_input_option == "RAW"
        self.append_attempts += 1
        self.rows.append(list(values))
        if self.append_error is not None:
            exc = self.append_error
            self.append_error = None
            raise exc


def build_ledger(sheet, *, read_only=False, sleeper=None):
    sh = MagicMock()
    sh.worksheet.return_value = sheet
    gc = MagicMock()
    gc.open_by_key.return_value = sh
    return SubmissionLedger(
        gc, "synthetic-sheet", "entries", NORMALIZED_FIELDS,
        read_only=read_only, sleeper=sleeper or (lambda _: None),
    )


def make_email(amount="$25.00", *, sender=None, include_amount=True, extra_rows=()):
    msg = EmailMessage()
    msg["From"] = sender or "Hillel at VT <lglforms-submissions@littlegreenlight.com>"
    msg["Message-ID"] = "<synthetic-message@example.invalid>"
    body = [
        ("Form title", "CWKC 2026 Donation Form"),
        ("I am a/an", "Alumni"),
        ("Name - First Name", "Synthetic"),
        ("Name - Last Name", "Donor"),
    ]
    if include_amount:
        body.append(("Total Amount", amount))
    body.extend(extra_rows)
    html = "<table>" + "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in body
    ) + "</table>"
    msg.set_content("Synthetic test notification")
    msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


class FakeServer:
    def __init__(self, emails, fail_flags=False):
        self.emails = dict(emails)
        self.fail_flags = fail_flags
        self.seen = set()
        self.peek_calls = []

    def fetch(self, uid, request):
        assert request == ["BODY.PEEK[]"]
        self.peek_calls.append(uid)
        return {uid: {b"BODY[]": self.emails[uid]}}

    def add_flags(self, uid, flags):
        assert flags == ["\\Seen"]
        if self.fail_flags:
            self.fail_flags = False
            raise OSError("synthetic acknowledgment failure")
        self.seen.add(uid)


def test_fingerprint_is_stable_and_does_not_expose_donor():
    email = make_email()
    stored_id = fingerprint(email)
    assert stored_id == fingerprint(email)
    assert fingerprint(email) != fingerprint(make_email("$55"))
    assert "Synthetic" not in fingerprint(email)
    assert len(fingerprint(email)) == 64


def test_new_sheet_stores_id_atomically():
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    row = dict.fromkeys(NORMALIZED_FIELDS, "synthetic")
    assert ledger.insert(row, "sha256-test") is True
    assert sheet.rows[0] == [*NORMALIZED_FIELDS, SUBMISSION_ID]
    assert sheet.rows[1][-1] == "sha256-test"
    assert ledger.insert(row, "sha256-test") is False
    assert len(sheet.rows) == 2


def test_header_append_lost_response_does_not_create_duplicate_header():
    sheet = FakeSheet()
    sheet.append_error = requests.exceptions.Timeout("header response lost")
    ledger = build_ledger(sheet)
    assert ledger.headers == [*NORMALIZED_FIELDS, SUBMISSION_ID]
    assert len(sheet.rows) == 1
    assert sheet.append_attempts == 1


def test_existing_legacy_rows_block_unverified_replay():
    sheet = FakeSheet([[*NORMALIZED_FIELDS], ["123", "25"]])
    with pytest.raises(ValueError, match="unkeyed"):
        build_ledger(sheet)
    assert sheet.rows[0] == list(NORMALIZED_FIELDS)
    assert len(sheet.rows) == 2


def test_legacy_reconciliation_is_read_only():
    sheet = FakeSheet([[*NORMALIZED_FIELDS], ["123", "25"]])
    ledger = build_ledger(sheet, read_only=True)
    assert ledger.legacy_rows == 1
    assert ledger.tracking_enabled is False
    assert SUBMISSION_ID not in sheet.rows[0]


def test_already_persisted_key_is_not_appended():
    sheet = FakeSheet([[*NORMALIZED_FIELDS, SUBMISSION_ID],
                       [*["sample"] * len(NORMALIZED_FIELDS), "saved-id"]])
    ledger = build_ledger(sheet)
    assert ledger.insert(dict.fromkeys(NORMALIZED_FIELDS, "test"), "saved-id") is False
    assert sheet.append_attempts == 0


def test_ambiguous_network_error_after_successful_append_does_not_duplicate():
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    sheet.append_error = requests.exceptions.Timeout("simulated lost response")
    assert ledger.insert(dict.fromkeys(NORMALIZED_FIELDS, "data"), "first-id") is False
    assert len(sheet.rows) == 2
    assert "first-id" in ledger.ids


def test_duplicate_stored_ids_fail_closed():
    row = [*["data"] * len(NORMALIZED_FIELDS), "duplicate-id"]
    sheet = FakeSheet([[*NORMALIZED_FIELDS, SUBMISSION_ID], row, row])
    with pytest.raises(ValueError, match="Duplicate submission IDs"):
        build_ledger(sheet)


def test_failed_persisted_state_check_fails_closed():
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    sheet.append_error = requests.exceptions.Timeout("lost result")
    sheet.read_error = RuntimeError("cannot verify")
    row = dict.fromkeys(NORMALIZED_FIELDS, "data")
    with pytest.raises(RuntimeError, match="cannot verify"):
        ledger.insert(row, "key")
    assert len(sheet.rows) == 2


def test_429_retries_with_bounded_delay():
    attempts = 0
    sleeps = []

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise gspread.exceptions.APIError(SimpleNamespace(
                status_code=429,
                json=lambda: {"error": {"code": 429, "message": "quota exceeded"}},
            ))
        return "ready"

    assert retry(operation, sleeper=sleeps.append) == "ready"
    assert sleeps == [15, 30]
    assert attempts == 3


def test_permanent_api_error_does_not_retry():
    calls = 0
    def operation():
        nonlocal calls
        calls += 1
        raise ValueError("unrecognized columns")

    with pytest.raises(ValueError, match="unrecognized"):
        retry(operation, sleeper=lambda _: None)
    assert calls == 1


def test_unread_backlog_is_acked_only_after_durable_append():
    raw = make_email()
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({1: raw})
    result = lgl.process_messages(server, [1], ledger)
    assert result == {"new": 1, "already_stored": 0, "pending": 0, "failed": 0}
    assert server.seen == {1}
    assert len(sheet.rows) == 2


def test_ingested_synthetic_gift_reconciles_to_expected_score():
    from scraper.CalculateValues import CalculateValues

    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({1: make_email("$25.00")})
    summary = lgl.process_messages(server, [1], ledger)
    assert summary["new"] == 1
    values = [
        dict(zip(sheet.rows[0], row, strict=True))
        for row in sheet.rows[1:]
    ]
    worksheet = MagicMock()
    worksheet.get_all_records.return_value = values
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet
    client = MagicMock()
    client.open_by_key.return_value = spreadsheet
    with patch("scraper.CalculateValues.gspread.service_account", return_value=client):
        totals = CalculateValues("synthetic-spreadsheet").calculate_all()

    assert totals["vt"]["total_amount"] == 25
    assert totals["vt"]["most_individual_donors"] == 1
    assert totals["uva"]["total_amount"] == 0


def test_flag_failure_leaves_unread_but_replay_does_not_append_again():
    raw = make_email()
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({1: raw}, fail_flags=True)
    first = lgl.process_messages(server, [1], ledger)
    assert first["failed"] == 1
    assert server.seen == set()
    assert len(sheet.rows) == 2

    # Fresh process / read of the same durable Sheet.
    ledger = build_ledger(sheet)
    second = lgl.process_messages(server, [1], ledger)
    assert second["already_stored"] == 1
    assert second["failed"] == 0
    assert server.seen == {1}
    assert len(sheet.rows) == 2


def test_unrecognized_sender_leaves_email_unread():
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({1: make_email(sender="Unrecognized Sender <source@example.invalid>")})
    result = lgl.process_messages(server, [1], ledger)
    assert result["failed"] == 1
    assert server.seen == set()
    assert len(sheet.rows) == 1


def test_bad_amount_and_missing_amount_leave_messages_unread():
    for raw in (make_email("$not-a-number"), make_email(include_amount=False),
                make_email("NaN"), make_email("-20")):
        sheet = FakeSheet()
        ledger = build_ledger(sheet)
        server = FakeServer({1: raw})
        result = lgl.process_messages(server, [1], ledger)
        assert result["failed"] == 1
        assert not server.seen
        assert len(sheet.rows) == 1


def test_bad_html_does_not_stop_other_messages_but_blocks_publication():
    valid = make_email()
    server = FakeServer({1: b"malformed MIME", 2: valid})
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    result = lgl.process_messages(server, [1, 2], ledger)
    assert result["failed"] == 1
    assert result["new"] == 1
    assert server.seen == {2}



@pytest.mark.parametrize("extra_rows", [
    [("Graduation Year", "2026"), ("Graduation Year", "2025")],
    [("Graduation Year", "2026"), ("Graduation Year", "2026")],
    [("Total Amount", "$999.00")],
    [("I am a/an", "Current Parent")],
])
def test_ambiguous_notification_is_not_stored_or_marked_seen(extra_rows, capsys):
    raw = make_email(extra_rows=extra_rows)
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({7: raw})

    summary = lgl.process_messages(server, [7], ledger)

    assert summary == {"new": 0, "already_stored": 0, "pending": 0, "failed": 1}
    assert sheet.rows == [[*NORMALIZED_FIELDS, SUBMISSION_ID]]
    assert sheet.append_attempts == 1  # Header only, never a donation.
    assert server.seen == set()
    assert server.peek_calls == [7]
    output = capsys.readouterr().out
    assert "ValueError" in output
    assert "$999.00" not in output
    assert "2026" not in output


def test_duplicate_conflict_does_not_prevent_other_email_processing():
    bad = make_email(extra_rows=[
        ("Graduation Year", "2025"), ("Graduation Year", "2026"),
    ])
    good = make_email()
    sheet = FakeSheet()
    ledger = build_ledger(sheet)
    server = FakeServer({7: bad, 8: good})

    summary = lgl.process_messages(server, [7, 8], ledger)

    assert summary["new"] == 1
    assert summary["failed"] == 1
    assert server.seen == {8}
    assert len(sheet.rows) == 2


def test_ambiguous_notification_blocks_csv_publication(monkeypatch):
    raw = make_email(extra_rows=[
        ("Graduation Year", "2026"), ("Graduation Year", "2025"),
    ])
    server = FakeServer({7: raw})
    server.login = MagicMock()
    server.select_folder = MagicMock()
    server.search = MagicMock(return_value=[7])
    context = MagicMock()
    context.__enter__.return_value = server
    monkeypatch.setattr(lgl, "IMAPClient", lambda *args, **kwargs: context)
    sheet = FakeSheet()
    book = MagicMock()
    book.worksheet.return_value = sheet
    client = MagicMock()
    client.open_by_key.return_value = book
    monkeypatch.setattr(lgl.gspread, "service_account", lambda **kwargs: client)
    recalculate = MagicMock()
    monkeypatch.setattr(lgl, "update_local_csv", recalculate)

    with pytest.raises(RuntimeError, match="blocking CSV publication"):
        lgl.main([])

    recalculate.assert_not_called()
    assert server.seen == set()
    assert len(sheet.rows) == 1

def test_reconcile_only_has_no_writes_or_flags():
    raw = make_email()
    sheet = FakeSheet()
    ledger = build_ledger(sheet, read_only=True)
    server = FakeServer({1: raw})
    result = lgl.process_messages(server, [1], ledger, reconcile_only=True)
    assert result["pending"] == 1
    assert result["new"] == 0
    assert not server.seen
    assert sheet.append_attempts == 0


def test_main_raises_and_skips_csv_if_batch_has_failure(monkeypatch):
    raw = make_email(include_amount=False)
    server = FakeServer({3: raw})
    server.login = MagicMock()
    server.select_folder = MagicMock()
    server.search = MagicMock(return_value=[3])
    context = MagicMock()
    context.__enter__.return_value = server
    monkeypatch.setattr(lgl, "IMAPClient", lambda *args, **kwargs: context)
    sheet = FakeSheet()
    sh = MagicMock()
    sh.worksheet.return_value = sheet
    gc = MagicMock()
    gc.open_by_key.return_value = sh
    monkeypatch.setattr(lgl.gspread, "service_account", lambda **kwargs: gc)
    csv = MagicMock()
    monkeypatch.setattr(lgl, "update_local_csv", csv)
    with pytest.raises(RuntimeError, match="blocking CSV publication"):
        lgl.main([])
    csv.assert_not_called()
    assert server.seen == set()


def test_main_reconcile_only_does_not_recalculate(monkeypatch):
    server = FakeServer({3: make_email()})
    server.login = MagicMock()
    server.select_folder = MagicMock()
    server.search = MagicMock(return_value=[3])
    context = MagicMock()
    context.__enter__.return_value = server
    monkeypatch.setattr(lgl, "IMAPClient", lambda *args, **kwargs: context)
    sheet = FakeSheet([[*NORMALIZED_FIELDS]])
    sh = MagicMock()
    sh.worksheet.return_value = sheet
    gc = MagicMock()
    gc.open_by_key.return_value = sh
    monkeypatch.setattr(lgl.gspread, "service_account", lambda **kwargs: gc)
    csv = MagicMock()
    monkeypatch.setattr(lgl, "update_local_csv", csv)
    lgl.main(["--reconcile-only"])
    csv.assert_not_called()
    assert server.seen == set()
    assert SUBMISSION_ID not in sheet.rows[0]


def _prepare_empty_mailbox_main(monkeypatch, sheet):
    """Use only mocked Gmail and Sheets; no real access or writes."""
    server = FakeServer({})
    server.login = MagicMock()
    server.select_folder = MagicMock()
    server.search = MagicMock(return_value=[])
    context = MagicMock()
    context.__enter__.return_value = server
    monkeypatch.setattr(lgl, "IMAPClient", lambda *args, **kwargs: context)

    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = sheet
    gc = MagicMock()
    gc.open_by_key.return_value = spreadsheet
    service_account = MagicMock(return_value=gc)
    monkeypatch.setattr(lgl.gspread, "service_account", service_account)

    recalculate = MagicMock()
    monkeypatch.setattr(lgl, "update_local_csv", recalculate)
    return server, service_account, recalculate


def test_reconcile_only_checks_sheet_even_with_zero_unread_mail(monkeypatch, capsys):
    sheet = FakeSheet([[*NORMALIZED_FIELDS], ["historical", "25"]])
    original = [list(row) for row in sheet.rows]
    server, service_account, recalculate = _prepare_empty_mailbox_main(monkeypatch, sheet)

    lgl.main(["--reconcile-only"])

    assert sheet.rows == original
    assert sheet.append_attempts == 0
    assert server.seen == set()
    assert server.peek_calls == []
    assert recalculate.call_count == 0
    service_account.assert_called_once()
    output = capsys.readouterr().out
    assert "Unseen LGL notifications: 0" in output
    assert "pending=0" in output
    assert "legacy=1" in output
    assert "id_tracking=missing" in output
    assert "existing unkeyed Sheet rows need reconciliation" in output


def test_empty_mailbox_legacy_rows_block_live_csv_refresh(monkeypatch):
    sheet = FakeSheet([[*NORMALIZED_FIELDS], ["historical", "25"]])
    original = [list(row) for row in sheet.rows]
    server, _, recalculate = _prepare_empty_mailbox_main(monkeypatch, sheet)

    with pytest.raises(ValueError, match="reconciliation before CSV publication"):
        lgl.main([])

    recalculate.assert_not_called()
    assert sheet.rows == original
    assert sheet.append_attempts == 0
    assert not server.seen


def test_empty_mailbox_clean_ledger_allows_refresh_without_sheet_mutation(
    monkeypatch, capsys,
):
    sheet = FakeSheet([
        [*NORMALIZED_FIELDS, SUBMISSION_ID],
        [*[ "synthetic" ] * len(NORMALIZED_FIELDS), "test-id"],
    ])
    original = [list(row) for row in sheet.rows]
    server, _, recalculate = _prepare_empty_mailbox_main(monkeypatch, sheet)

    lgl.main([])

    recalculate.assert_called_once_with()
    assert sheet.rows == original
    assert sheet.append_attempts == 0
    assert not server.seen
    output = capsys.readouterr().out
    assert "identified=1, legacy=0, id_tracking=enabled" in output


def test_empty_mailbox_fails_closed_when_sheet_is_inaccessible(monkeypatch):
    sheet = FakeSheet()
    _, service_account, recalculate = _prepare_empty_mailbox_main(monkeypatch, sheet)
    gc = service_account.return_value
    gc.open_by_key.side_effect = PermissionError("synthetic: access denied")

    with pytest.raises(PermissionError, match="access denied"):
        lgl.main([])

    recalculate.assert_not_called()
    assert sheet.append_attempts == 0
