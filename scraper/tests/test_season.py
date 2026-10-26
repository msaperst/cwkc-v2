"""Production season cutoff tests. Never connects to external services."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import subprocess
import textwrap

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
        ("repository_dispatch", "sheet-change", (True, True)),
        ("repository_dispatch", "lgl-form-submission", (True, True)),
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
    monkeypatch.setattr(season, "allowed_sources", lambda e, a: (True, True))
    assert season.main() == 0
    assert output.read_text() == "in_range=true\nlgl=true\ngoogle=true\n"
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
    assert "needs.check_date.outputs.in_range == 'true'" in workflow
    assert "git diff --quiet -- public/assets/csv/results.csv" in workflow
    assert "needs.update_results.outputs.changed == 'true'" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "2025-11-01" not in workflow
    assert "2025-12-10" not in workflow
    assert "action-update-file" not in workflow
    assert "always()" not in workflow
    assert "name: results-csv-" in workflow


def _change_step_shell() -> str:
    """Execute the real workflow shell instead of a reimplementation."""
    yaml = (Path(__file__).resolve().parents[2] / ".github/workflows/update.yml").read_text()
    section = yaml.split("      - name: Detect changed scoreboard\n", 1)[1]
    body = section.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
    return textwrap.dedent(body)


def _git(tmp_path, *args):
    return subprocess.run(["git", *args], cwd=tmp_path, check=True,
                          text=True, capture_output=True)


@pytest.mark.parametrize("new_data,expected", [
    (None, "false"),
    ("updated scoring data\n", "true"),
])
def test_actual_workflow_diff_command(tmp_path, new_data, expected):
    _git(tmp_path, "init", "-q")
    path = tmp_path / "public/assets/csv/results.csv"
    path.parent.mkdir(parents=True)
    path.write_text("original scoring data\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.email=ci@example.invalid",
         "-c", "user.name=CI", "commit", "-qm", "baseline")
    if new_data is not None:
        path.write_text(new_data)
    output = tmp_path / "outputs"
    env = {**os.environ, "GITHUB_OUTPUT": str(output)}
    result = subprocess.run(["bash", "-c", _change_step_shell()],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.read_text() == f"changed={expected}\n"


def test_diff_step_fails_closed_outside_git_repository(tmp_path):
    path = tmp_path / "public/assets/csv/results.csv"
    path.parent.mkdir(parents=True)
    path.write_text("untracked\n")
    env = {**os.environ, "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    result = subprocess.run(["bash", "-c", _change_step_shell()],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (tmp_path / "outputs").exists()


def test_workflow_cannot_publish_when_import_fails():
    yaml = (Path(__file__).resolve().parents[2] / ".github/workflows/update.yml").read_text()
    # Every successful event refreshes BOTH sources in a single ordered job.
    assert yaml.count("      - name: Process unread LGL emails") == 1
    assert yaml.count("      - name: Update Google Forms participation scores") == 1
    assert yaml.index("Process unread LGL emails") < yaml.index(
        "Update Google Forms participation scores") < yaml.index(
        "Check cutoff again before publishing") < yaml.index(
        "Detect changed scoreboard") < yaml.index("Commit and publish changed results")
    assert "needs.update_results.result == 'success'" in yaml
    assert "contents: write" in yaml
    assert "id-token: write" in yaml
    assert yaml.count("      - name: Commit and publish changed results") == 1
