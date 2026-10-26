"""Production season cutoff tests. Never connects to external services."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scraper import season


START_UTC = datetime(2026, 11, 30, 5, 0, tzinfo=timezone.utc)
END_UTC = datetime(2026, 12, 8, 1, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("instant", "allowed"),
    [
        (START_UTC - timedelta(microseconds=1), False),
        (START_UTC, True),
        (START_UTC + timedelta(seconds=1), True),
        (datetime(2026, 12, 5, 12, tzinfo=timezone.utc), True),
        (END_UTC - timedelta(microseconds=1), True),
        (END_UTC, False),
        (END_UTC + timedelta(seconds=1), False),
    ],
)
@pytest.mark.parametrize(
    ("event", "action", "expected"),
    [
        ("repository_dispatch", "sheet-change", (False, True)),
        ("repository_dispatch", "lgl-form-submission", (True, False)),
        ("workflow_dispatch", "", (True, True)),
    ],
)
def test_approved_events_enforce_exact_utc_boundaries(instant, allowed, event, action, expected):
    assert season.allowed_sources(event, action, instant) == (
        expected if allowed else (False, False)
    )


@pytest.mark.parametrize(
    ("event", "action"),
    [
        ("push", ""),
        ("pull_request", ""),
        ("schedule", ""),
        ("repository_dispatch", "unknown-event"),
        ("repository_dispatch", ""),
        ("workflow_dispatch_typo", ""),
    ],
)
def test_unknown_events_are_rejected(event, action):
    assert season.allowed_sources(event, action, START_UTC) == (False, False)


def test_timezone_conversion_and_frontend_dates_match():
    assert season.START.astimezone(timezone.utc) == START_UTC
    assert season.END.astimezone(timezone.utc) == END_UTC
    js = (Path(__file__).resolve().parents[2] / "public/assets/js/main.js").read_text()
    assert "2026-11-30T00:00:00-05:00" in js
    assert "2026-12-07T20:00:00-05:00" in js


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        season.allowed_sources("workflow_dispatch", now=datetime(2026, 11, 30))


def test_command_emits_all_gate_outputs(monkeypatch, tmp_path, capsys):
    from io import StringIO

    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "repository_dispatch")
    monkeypatch.setenv("GITHUB_EVENT_ACTION", "sheet-change")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(season, "allowed_sources", lambda e, a: (False, True))
    assert season.main() == 0
    assert output.read_text() == "in_range=true\nlgl=false\ngoogle=true\n"
    assert "allowed" in capsys.readouterr().out


def test_verification_rejects_closed_window(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_EVENT_ACTION", "")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(season, "allowed_sources", lambda e, a: (False, False))
    monkeypatch.setattr("sys.argv", ["season", "--verify-only"])
    assert season.main() == 1


def test_gate_is_used_by_workflow_before_and_after_processing():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/update.yml").read_text()
    assert "python -m scraper.season" in workflow
    assert "python -m scraper.season --verify-only" in workflow
    assert "needs.check-date.outputs.in_range == 'true'" in workflow
    assert "git diff --quiet -- public/assets/csv/results.csv" in workflow
    assert "needs.update-results.outputs.changed == 'true'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "2025-11-01" not in workflow
    assert "2025-12-10" not in workflow
    assert "action-update-file" not in workflow
    assert "always()" not in workflow
    assert "name: results-csv-" in workflow
