"""Synthetic forwarded LGL fixtures: never use real donor records in GitHub."""
from email.message import EmailMessage
from html import escape
from imaplib import IMAP4
from unittest.mock import MagicMock

import pytest

from scraper import audit_lgl, getLglFormData
from scraper.lgl_forwarding import search_unread_lgl, submission_key


SCHOOL = "Brody Jewish Center"
LGL = "lglforms-submissions@littlegreenlight.com"
FORM = "14th Annual Commonwealth Kiddush Cup Front End Form"


def _notification(*, amount="$103.00", source_id="synthetic-shared-id"):
    rows = [
        ("Form title", FORM),
        ("Submission ID", source_id),
        ("Submission Date", "2026-11-24 10:01:00 -0500"),
        ("Total Amount", amount),
        ("Amount - Details", "Gift: $100.00"),
        ("Name - First Name", "Synthetic"),
        ("Name - Last Name", "Giver"),
        ("Email", "synthetic@example.invalid"),
        ("Phone", "5550102026"),
        ("I am a/an", "Current Parent"),
        ("Related Grad Year", "2028"),
        ("Is Recurring", "false"),
    ]
    table = "<table>" + "".join(
        "<tr><td>" + escape(k) + "</td><td>" + escape(v) + "</td></tr>"
        for k, v in rows
    ) + "</table>"
    msg = EmailMessage()
    msg["From"] = f"{SCHOOL} <{LGL}>"
    msg["Subject"] = "New Submission: Donor -- " + FORM
    msg.set_content("Synthetic notification")
    msg.add_alternative(table, subtype="html", cte="quoted-printable")
    return msg.as_bytes(), table


def _forward(*, amount="$103.00", source_id="synthetic-shared-id",
             from_address="truman@brodyjewishcenter.org",
             original_address=LGL, include_marker=True):
    _, table = _notification(amount=amount, source_id=source_id)
    msg = EmailMessage()
    msg["From"] = f"CWKC Volunteer <{from_address}>"
    msg["Subject"] = "Fwd: New Submission: Donor -- " + FORM
    marker = "---------- Forwarded message ---------\n" if include_marker else ""
    forwarded_header = (
        marker
        + f"From: {SCHOOL} <{original_address}>\n"
        + "Date: Tue, Nov 24, 2026 at 10:01 AM\n"
        + "Subject: New Submission: Donor -- " + FORM + "\n"
        + "To: cwkc@example.invalid\n\n"
    )
    msg.set_content("Volunteer signature\n\n" + forwarded_header + "Synthetic original")
    msg.add_alternative(
        "<p>Volunteer signature</p>"
        + "<div class='gmail_attr'>"
        + escape(forwarded_header).replace("\n", "<br>")
        + "</div><div class='gmail_quote'>" + table + "</div>",
        subtype="html", cte="quoted-printable",
    )
    return msg.as_bytes()


def _server(messages):
    server = MagicMock()
    server.search.side_effect = lambda criteria: (
        [uid for uid, raw in messages.items() if b"Fwd:" in raw]
        if "SUBJECT" in criteria else
        [uid for uid, raw in messages.items() if b"Fwd:" not in raw]
    )
    server.fetch.side_effect = lambda uid, _flags: {
        uid: {b"BODY[]": messages[uid]}
    }
    return server


def test_direct_and_forwarded_have_the_same_durable_key():
    direct, _ = _notification()
    forwarded = _forward()
    sender1, fields1 = getLglFormData.parse_lgl_email(direct)
    sender2, fields2 = getLglFormData.parse_lgl_email(forwarded)
    assert sender1 == sender2 == f"{SCHOOL} <{LGL}>"
    assert fields1 == fields2
    assert submission_key(direct, fields1) == submission_key(forwarded, fields2)
    assert submission_key(direct, fields1) == "lgl:synthetic-shared-id"


def test_preview_deduplicates_direct_and_forward_without_mutating_mail():
    direct, _ = _notification()
    forwarded = _forward()
    server = _server({11: forwarded, 12: direct})
    assert search_unread_lgl(server) == [11, 12]
    report = audit_lgl.audit_unread(server)
    assert report["unread_matching"] == 2
    assert report["parsed"] == 1
    assert report["forwarded_parsed"] == 1
    assert report["duplicate_submissions_skipped"] == 1
    assert report["failed"] == 0
    assert report["provisional_metrics"]["uva"]["total_amount"] == "103.00"
    assert report["provisional_metrics"]["uva"]["most_money_families"] == "103.00"
    server.add_flags.assert_not_called()
    assert all(call.args[1] == ["BODY.PEEK[]"]
               for call in server.fetch.call_args_list)


def test_conflicting_source_records_fail_closed():
    direct, _ = _notification()
    server = _server({11: direct, 12: _forward(amount="$999.00")})
    report = audit_lgl.audit_unread(server)
    assert report["parsed"] == 1
    assert report["failed"] == 1
    assert report["errors"][0]["error_type"] == "ValueError"
    server.add_flags.assert_not_called()


@pytest.mark.parametrize("kwargs", [
    {"from_address": "untrusted@example.invalid"},
    {"original_address": "fraud@example.invalid"},
    {"include_marker": False},
])
def test_untrusted_or_unverifiable_forward_is_rejected(kwargs):
    with pytest.raises(ValueError):
        getLglFormData.parse_lgl_email(_forward(**kwargs))


def test_forward_without_source_submission_id_is_rejected():
    with pytest.raises(ValueError, match="Submission ID"):
        getLglFormData.parse_lgl_email(_forward(source_id=""))


def test_importer_uses_stable_key_for_both_delivery_methods():
    direct, _ = _notification()
    server = _server({21: direct, 22: _forward()})
    stored = set()
    ledger = MagicMock()
    ledger.known.side_effect = lambda key: key in stored
    def insert(row, key):
        assert row["total amount"] == "103.0"
        assert key not in stored
        stored.add(key)
        return True
    ledger.insert.side_effect = insert
    result = getLglFormData.process_messages(server, [21, 22], ledger)
    assert result == {"new": 1, "already_stored": 1, "pending": 0, "failed": 0}
    assert stored == {"lgl:synthetic-shared-id"}
    assert server.add_flags.call_count == 2


def test_acknowledgement_error_is_recovered_when_gmail_stored_seen():
    raw, _ = _notification(source_id="ack-confirmed")
    server = _server({41: raw})
    server.add_flags.side_effect = IMAP4.error("synthetic IMAP response failure")
    base_fetch = server.fetch.side_effect

    def fetch_with_flags(uid, items):
        if items == ["FLAGS"]:
            return {uid: {b"FLAGS": (b"\\Seen", b"\\Recent")}}
        return base_fetch(uid, items)

    server.fetch.side_effect = fetch_with_flags
    ledger = MagicMock()
    ledger.known.return_value = False
    ledger.insert.return_value = True

    result = getLglFormData.process_messages(server, [41], ledger)

    assert result == {"new": 1, "already_stored": 0, "pending": 0, "failed": 0}
    ledger.insert.assert_called_once()
    server.add_flags.assert_called_once_with(41, ["\\Seen"])
    server.fetch.assert_any_call(41, ["FLAGS"])


def test_unconfirmed_acknowledgement_fails_closed_but_replay_does_not_duplicate():
    raw, _ = _notification(source_id="ack-unconfirmed")
    server = _server({41: raw})
    server.add_flags.side_effect = IMAP4.error("synthetic failure before STORE")
    base_fetch = server.fetch.side_effect

    def fetch_without_seen(uid, items):
        if items == ["FLAGS"]:
            return {uid: {b"FLAGS": (b"\\Recent",)}}
        return base_fetch(uid, items)

    server.fetch.side_effect = fetch_without_seen
    ledger = MagicMock()
    persisted = set()
    ledger.known.side_effect = lambda key: key in persisted
    ledger.insert.side_effect = lambda row, key: (persisted.add(key) or True)

    first = getLglFormData.process_messages(server, [41], ledger)

    assert first == {"new": 0, "already_stored": 0, "pending": 0, "failed": 1}
    assert persisted == {"lgl:ack-unconfirmed"}
    assert ledger.insert.call_count == 1

    # On a later run, the same unread notification is acknowledged safely
    # without writing another row.
    server.add_flags.side_effect = None
    second = getLglFormData.process_messages(server, [41], ledger)

    assert second == {"new": 0, "already_stored": 1, "pending": 0, "failed": 0}
    assert ledger.insert.call_count == 1


def test_ack_verification_failure_does_not_mask_unconfirmed_email():
    raw, _ = _notification(source_id="ack-check-failed")
    server = _server({41: raw})
    server.add_flags.side_effect = IMAP4.error("synthetic STORE failure")
    base_fetch = server.fetch.side_effect

    def fetch_fails_for_flags(uid, items):
        if items == ["FLAGS"]:
            raise IMAP4.error("synthetic FETCH failure")
        return base_fetch(uid, items)

    server.fetch.side_effect = fetch_fails_for_flags
    ledger = MagicMock()
    ledger.known.return_value = False
    ledger.insert.return_value = True

    result = getLglFormData.process_messages(server, [41], ledger)

    assert result["failed"] == 1
    ledger.insert.assert_called_once()
    server.fetch.assert_any_call(41, ["FLAGS"])
