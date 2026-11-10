"""Offline tests for the private read-only prelaunch audit command."""
from email.message import EmailMessage
from html import escape
import json
import stat
from unittest.mock import MagicMock, patch

import pytest

from scraper import audit_lgl as audit


def _mime(school, title, submission_id, amount, extra=()):
    rows = [
        ("Form title", title),
        ("Submission ID", submission_id),
        ("Submission Date", "2026-11-10 09:00:00 -0500"),
        ("Total Amount", amount),
        ("Name - First Name", "Example"),
        ("Name - Last Name", "Auditor"),
        ("Email", "auditor@example.invalid"),
        ("Phone", "5550102026"),
        *extra,
    ]
    table = "".join(
        f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>"
        for k, v in rows
    )
    msg = EmailMessage()
    sender = "Brody Jewish Center" if school == "uva" else "Hillel at VT"
    msg["From"] = f"{sender} <lglforms-submissions@littlegreenlight.com>"
    msg["To"] = "service@example.invalid"
    msg.set_content(
        f"<p><table>{table}</table></p>",
        subtype="html", charset="utf-8", cte="quoted-printable",
    )
    return msg.as_bytes()


MESSAGES = {
    11: _mime(
        "uva", audit.FORM_TITLES["uva-front"], "synthetic-uva-front", "$5.00",
        [
            ("I am a/an", "Current Parent||Alum"),
            ("Alumni Grad Year", ""),
            ("Related Grad Year", "2026"),
            ("Check all that apply",
             "This is my first gift to Hillel at UVA||"
             "Please don't list my name. I would like to remain anonymous."),
            ("Does your workplace match charitable giving?",
             "I'm not sure, can you look into it for me?"),
        ],
    ),
    12: _mime(
        "vt", audit.FORM_TITLES["vt-front"], "synthetic-vt-front", "$5.00",
        [
            ("I am a/an...", "Graduate Student||Current Parent||Alumni"),
            ("Alumni Graduation Year", "2006"),
            ("Intended Graduation Year", "2027"),
            ("Related Student Graduation Year", "2028"),
            ("Check All That Apply:",
             "This is my first gift to Hillel at VT||"
             "Please don't list my name. I would like to remain anonymous."),
        ],
    ),
    13: _mime(
        "uva", audit.FORM_TITLES["uva-back"], "synthetic-uva-back", "2.06",
        [
            ("Donor is a/n...", "Current Parent||Alum"),
            ("Alumni Grad Year", ""),
            ("Related Grad Year", "2026"),
            ("Gift notes", "TEST GIFT - no payment"),
            ("Is this a monthly gift?", "No"),
        ],
    ),
    14: _mime(
        "vt", audit.FORM_TITLES["vt-back"], "synthetic-vt-back", "20",
        [
            ("Donor is a/an...", "Current Parent||Alum"),
            ("Alumni Graduation Year", "2006"),
            ("Related Student Graduation Year", "2027"),
            ("Is this a monthly gift?", "Yes"),
            ("Is Recurring", "false"),
            ("Gift Notes", "TEST GIFT - no payment"),
        ],
    ),
}


def _fake_server(messages=MESSAGES):
    server = MagicMock()
    server.search.return_value = list(messages)
    server.fetch.side_effect = lambda uid, flags: {
        uid: {b"BODY[]": messages[uid]}
    }
    return server


def test_all_four_nov10_contracts_audit_without_mutations():
    server = _fake_server()
    report = audit.audit_unread(server)
    assert report["unread_matching"] == 4
    assert report["parsed"] == 4
    assert report["failed"] == 0
    assert report["excluded"] == 0
    assert report["provisional_metrics"]["uva"]["total_amount"] == "7.06"
    assert report["provisional_metrics"]["vt"]["total_amount"] == "245.00"
    assert report["provisional_metrics"]["uva"]["most_individual_donors"] == 1
    assert report["provisional_metrics"]["vt"]["most_individual_donors"] == 1
    assert report["provisional_metrics"]["uva"]["most_donors_class_2026"] == 0
    assert report["provisional_metrics"]["vt"]["most_donors_class_2026"] == 0
    assert report["independent_score_comparison"] == "passed"
    assert report["unreconciled_flags"] >= 3
    assert report["errors"] == []
    assert server.fetch.call_count == 4
    for call in server.fetch.call_args_list:
        assert call.args[1] == ["BODY.PEEK[]"]
    server.add_flags.assert_not_called()
    server.delete_messages.assert_not_called()


def test_excluding_only_verified_backend_tests_preserves_actual_public_gifts():
    server = _fake_server()
    report = audit.audit_unread(server, {
        "synthetic-vt-back", "synthetic-uva-back",
    })
    assert report["excluded"] == 2
    assert report["provisional_metrics"]["uva"]["total_amount"] == "5.00"
    assert report["provisional_metrics"]["vt"]["total_amount"] == "5.00"
    assert report["provisional_metrics"]["uva"]["most_individual_donors"] == 1
    assert report["provisional_metrics"]["vt"]["most_individual_donors"] == 1
    assert report["provisional_metrics"]["uva"]["most_first_time_donors"] == 1
    assert report["provisional_metrics"]["vt"]["most_first_time_donors"] == 1
    assert report["provisional_metrics"]["uva"]["most_money_families"] == "5.00"
    assert report["provisional_metrics"]["vt"]["most_money_families"] == "5.00"
    assert "donor_names" not in report["provisional_metrics"]["uva"]


def test_inventory_contains_no_donor_contact_data():
    report = audit.audit_unread(_fake_server())
    exported = json.dumps(report)
    for private_value in ("auditor@example.invalid", "5550102026", "Example", "Auditor"):
        assert private_value not in exported
    assert report["inventory"][0]["submission_id"] == "synthetic-uva-front"
    assert "unverified-alumni-year" in report["inventory"][0]["flags"]
    assert "staff-entry-check-payment" in report["inventory"][2]["flags"]
    assert "monthly-form-vs-recurring-flag" in report["inventory"][3]["flags"]


def test_readonly_mode_closes_connection_and_does_not_log_donors(capsys):
    server = _fake_server()
    client = MagicMock()
    client.__enter__.return_value = server
    with patch.object(audit, "IMAPClient", return_value=client), \
         patch.object(audit, "EMAIL_ACCOUNT", "service@example.invalid"), \
         patch.object(audit, "EMAIL_PASSWORD", "fake-local-only"), \
         patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
        audit.main([])

    server.select_folder.assert_called_once_with(
        audit.MAILBOX, readonly=True,
    )
    server.add_flags.assert_not_called()
    assert server.search.call_args.args[0] == [
        "UNSEEN", "FROM", audit.FROM_FILTER,
    ]
    out = capsys.readouterr().out
    assert "read-only audit" in out.lower()
    assert "auditor@example.invalid" not in out
    assert "5550102026" not in out
    assert "synthetic-vt-back" not in out


def test_unknown_messages_fail_without_acknowledgment():
    server = _fake_server({
        9: _mime("uva", "Unknown unapproved form", "unknown-id", "$12"),
    })
    report = audit.audit_unread(server)
    assert report["parsed"] == 0
    assert report["failed"] == 1
    assert report["errors"] == [{"uid": 9, "error_type": "ValueError"}]
    assert report["provisional_metrics"]["uva"]["total_amount"] == "0.00"
    server.add_flags.assert_not_called()


def test_owner_only_inventory_file_and_no_overwrite(tmp_path):
    report = audit.audit_unread(_fake_server())
    path = tmp_path / "private-audit.json"
    audit._write_private_json(path, report)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["unread_matching"] == 4
    with pytest.raises(FileExistsError):
        audit._write_private_json(path, report)


def test_independent_comparison_catches_a_regression(monkeypatch):
    from scraper.CalculateValues import CalculateValues

    monkeypatch.setattr(
        CalculateValues, "_total_raised", lambda self, df: 9999,
    )
    with pytest.raises(AssertionError, match="score mismatch"):
        audit.audit_unread(_fake_server())



def test_proposed_csv_preserves_schema_and_redacts_donor_names(tmp_path):
    import pandas as pd

    report = audit.audit_unread(_fake_server(), {
        "synthetic-uva-back", "synthetic-vt-back",
    })
    output = tmp_path / "proposed-results.csv"
    frame = audit.build_preview_csv(report, output)
    original = pd.read_csv("public/assets/csv/results.csv")
    assert output.exists()
    assert list(frame.columns) == list(original.columns)
    assert len(frame) == 1
    assert float(frame.at[0, "uva_total_amount"]) == 5.0
    assert float(frame.at[0, "vt_total_amount"]) == 5.0
    assert int(frame.at[0, "uva_most_individual_donors"]) == 1
    assert int(frame.at[0, "vt_most_first_time_donors"]) == 1
    assert int(frame.at[0, "uva_most_donors_class_2026"]) == 0
    assert int(frame.at[0, "uva_hanukkah_photos"]) == 0
    assert frame.at[0, "uva_donor_names"] == ""
    assert frame.at[0, "vt_donor_names"] == ""
    contents = output.read_text()
    assert "auditor@example.invalid" not in contents
    assert "5550102026" not in contents
    assert "Example" not in contents


def test_failing_audit_cannot_publish_even_a_preview(tmp_path):
    report = audit.audit_unread(_fake_server({
        5: _mime("uva", "Invalid form title", "wrong-form", "$3"),
    }))
    output = tmp_path / "preview.csv"
    with pytest.raises(ValueError, match="Incomplete audit"):
        audit.build_preview_csv(report, output)
    assert not output.exists()


def test_unmatched_exclusion_rejects_inaccurate_projection(tmp_path):
    report = audit.audit_unread(_fake_server(), {"not-in-inbox"})
    with pytest.raises(ValueError, match="Incomplete audit"):
        audit.build_preview_csv(report, tmp_path / "preview.csv")


def test_read_only_forms_option_uses_existing_updater_without_writing(
    tmp_path, monkeypatch,
):
    from scraper.getGoogleFormData import SubmissionUpdater

    report = audit.audit_unread(_fake_server(), {
        "synthetic-uva-back", "synthetic-vt-back",
    })
    called = []

    def fake_init(self, creds, results_csv_path):
        called.append(("init", creds, results_csv_path))
        import pandas as pd
        self.df = pd.read_csv("public/assets/csv/results.csv").astype(object)

    def fake_update(self, dry_run=False):
        called.append(("update", dry_run))
        assert dry_run is True
        self.df.at[0, "uva_alumni_gatherings"] = 4
        self.df.at[0, "vt_hanukkah_photos"] = 7

    monkeypatch.setattr(SubmissionUpdater, "__init__", fake_init)
    monkeypatch.setattr(SubmissionUpdater, "update_results", fake_update)
    frame = audit.build_preview_csv(
        report, tmp_path / "preview.csv",
        include_forms=True, credentials_file="synthetic-credentials",
    )
    assert frame.at[0, "uva_alumni_gatherings"] == 4
    assert frame.at[0, "vt_hanukkah_photos"] == 7
    assert frame.at[0, "uva_total_amount"] == "5.00"
    assert called[0][1] == "synthetic-credentials"
    assert called[1] == ("update", True)


def test_actions_summary_is_redacted(tmp_path, monkeypatch):
    report = audit.audit_unread(_fake_server())
    frame = audit.build_preview_csv(report, tmp_path / "preview.csv")
    summary_path = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))
    audit.write_action_summary(report, frame)
    contents = summary_path.read_text()
    assert "proposed" in contents.lower()
    assert "csv" in contents
    assert "auditor@example.invalid" not in contents
    assert "Example" not in contents
    assert "unreconciled" in contents



def test_public_github_actions_requires_private_output(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(SystemExit):
        audit.main([])


def test_private_workflow_logs_no_amounts_or_names(tmp_path, monkeypatch, capsys):
    server = _fake_server()
    client = MagicMock()
    client.__enter__.return_value = server
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    with patch.object(audit, "IMAPClient", return_value=client), \
         patch.object(audit, "EMAIL_ACCOUNT", "service@example.invalid"), \
         patch.object(audit, "EMAIL_PASSWORD", "fake-local-only"):
        audit.main([
            "--private-workflow", "--preview-csv",
            str(tmp_path / "preview.csv"),
        ])
    output = capsys.readouterr().out
    summary = (tmp_path / "summary.md").read_text()
    assert (tmp_path / "preview.csv").exists()
    assert "245.00" not in output + summary
    assert "7.06" not in output + summary
    assert "auditor@example.invalid" not in output + summary
    assert "Preview" in summary or "preview" in summary
    assert "encrypted" in summary
    server.add_flags.assert_not_called()



def test_identical_mime_notifications_are_projected_once():
    raw = MESSAGES[11]
    report = audit.audit_unread(_fake_server({51: raw, 52: raw}))
    assert report["unread_matching"] == 2
    assert report["parsed"] == 1
    assert report["identical_mime_skipped"] == 1
    assert report["provisional_metrics"]["uva"]["total_amount"] == "5.00"
    assert report["provisional_metrics"]["uva"]["most_individual_donors"] == 1
