"""Full production-function chain with no real donor data or external writes."""
import csv
import json
from pathlib import Path

import pytest

from scraper.tests import e2e_rehearsal as e2e
from scraper.donation_ledger import NORMALIZED_FIELDS, SubmissionLedger
from scraper.getLglFormData import process_messages


def test_ten_synthetic_notifications_write_sheet_and_generate_browser_csv(
    tmp_path, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_RUN_ID", "test")
    summary = e2e.run(mode="offline")
    assert summary["result"] == "passed"
    assert summary["inserted"] == 10
    assert summary["replay_duplicates"] == 10
    assert summary["fields_checked"] == len(e2e.EXPECTED)
    assert summary["csv_columns"] == 26
    assert Path(".cwkc-e2e-results.csv").exists()
    report = json.loads(Path(".cwkc-e2e-report.json").read_text())
    assert report["result"] == "passed"
    with Path(".cwkc-e2e-results.csv").open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    for key, value in e2e.EXPECTED.items():
        assert float(row[key]) == pytest.approx(value)
    assert "example.invalid" not in json.dumps(report)


def test_bad_email_remains_unacknowledged_in_rehearsal():
    client, key = e2e._client("offline", "E2E_demo")
    ledger = SubmissionLedger(
        client, key, "E2E_demo", NORMALIZED_FIELDS, sleeper=lambda _: None,
    )
    server = e2e.SimulatedIMAP()
    server.mail = {
        200: e2e._notification("vt-front", "$0", 200, [
            ("I am a/an...", "Current Parent"),
        ]),
    }
    summary = process_messages(server, [200], ledger)
    assert summary == {"new": 0, "already_stored": 0, "pending": 0, "failed": 1}
    assert server.flags == []
    assert len(ledger.ws.get_all_records()) == 0


def test_rehearsal_uses_all_four_actual_form_contracts():
    from scraper.EmailParser import determine_source
    from scraper.getLglFormData import parse_lgl_email
    sources = set()
    for raw in e2e.messages().values():
        sender, data = parse_lgl_email(raw)
        source = determine_source(sender, data["Form title"])
        assert data["Form title"] == e2e.FORM_TITLES[source]
        sources.add(source)
    assert sources == {"uva-front", "uva-back", "vt-front", "vt-back"}


def test_sandbox_refuses_to_use_real_production_spreadsheet(monkeypatch):
    monkeypatch.setenv("SPREADSHEET_KEY", "production-sheet-id-abcdefghijkl")
    monkeypatch.setenv("CWKC_E2E_SPREADSHEET_KEY", "production-sheet-id-abcdefghijkl")
    with pytest.raises(ValueError, match="distinct sandbox"):
        e2e._client("sandbox", "E2E_demo")


def test_sandbox_refuses_to_run_without_explicitly_designated_sheet(monkeypatch):
    monkeypatch.setenv("SPREADSHEET_KEY", "production-sheet-id-abcdefghijkl")
    monkeypatch.delenv("CWKC_E2E_SPREADSHEET_KEY", raising=False)
    with pytest.raises(ValueError, match="distinct sandbox"):
        e2e._client("sandbox", "E2E_demo")


def test_sandbox_refuses_wrong_spreadsheet_title(monkeypatch):
    key = "synthetic-sandbox-id-abcdefghijkl"
    production = "production-sheet-id-abcdefghijkl"
    monkeypatch.setenv("SPREADSHEET_KEY", production)
    monkeypatch.setenv("CWKC_E2E_SPREADSHEET_KEY", key)
    gc = e2e.MemoryClient({
        key: e2e.MemorySpreadsheet(title="NOT A SANDBOX"),
    })
    monkeypatch.setattr(e2e.gspread, "service_account", lambda **kwargs: gc)
    with pytest.raises(ValueError, match="named CWKC-E2E-SANDBOX"):
        e2e._client("sandbox", "E2E_demo")


def test_sandbox_refuses_existing_worksheet(monkeypatch):
    key = "synthetic-sandbox-id-abcdefghijkl"
    monkeypatch.setenv("SPREADSHEET_KEY", "production-sheet-id-abcdefghijkl")
    monkeypatch.setenv("CWKC_E2E_SPREADSHEET_KEY", key)
    gc = e2e.MemoryClient({
        key: e2e.MemorySpreadsheet(
            title=e2e.SANDBOX_TITLE,
            tabs={"E2E_demo": e2e.MemoryWorksheet()},
        )
    })
    monkeypatch.setattr(e2e.gspread, "service_account", lambda **kwargs: gc)
    with pytest.raises(ValueError, match="already exists"):
        e2e._client("sandbox", "E2E_demo")
