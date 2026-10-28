"""Offline CWKC watchdog contract tests. No network, donations, or Sheets."""
from datetime import timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import re

import pytest

from scraper import workflow_health as monitor
from scraper.contest_window import START, END

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = START - timedelta(minutes=30)


def run(created_at, *, conclusion="success", status="completed", run_id=101,
        completed_at=None):
    return {
        "id": run_id,
        "created_at": created_at.isoformat(),
        "updated_at": (completed_at or created_at).isoformat(),
        "status": status,
        "conclusion": conclusion,
    }


def test_fresh_success_is_healthy_even_if_results_branch_is_unchanged():
    now = START + timedelta(hours=2)
    earlier = now - timedelta(minutes=12)
    result = monitor.assess(now, [run(earlier)], PUBLISHED)
    assert result.healthy
    assert result.last_success == earlier
    assert result.published_at == PUBLISHED
    assert "Recent ingestion run succeeded" in result.reason


def test_failure_after_last_success_triggers_alarm():
    now = START + timedelta(hours=3)
    runs = [
        run(now - timedelta(minutes=2), conclusion="failure", run_id=2),
        run(now - timedelta(minutes=20), run_id=1),
    ]
    result = monitor.assess(now, runs, PUBLISHED)
    assert not result.healthy
    assert result.latest_run_id == 2
    assert "failed" in result.reason


@pytest.mark.parametrize("conclusion", [
    "failure", "timed_out", "cancelled", "action_required",
])
def test_terminal_non_success_run_raises_alarm(conclusion):
    now = START + timedelta(hours=2)
    result = monitor.assess(
        now, [run(now - timedelta(minutes=3), conclusion=conclusion)], PUBLISHED,
    )
    assert not result.healthy


def test_subsequent_success_recovers_from_earlier_failure():
    now = START + timedelta(hours=2)
    runs = [
        run(now - timedelta(minutes=17), conclusion="failure", run_id=2),
        run(now - timedelta(minutes=5), run_id=3),
    ]
    result = monitor.assess(now, runs, PUBLISHED)
    assert result.healthy
    assert result.latest_run_id == 3


def test_stale_success_is_alarm_even_with_recent_queued_run():
    now = START + timedelta(hours=2)
    runs = [
        run(now - timedelta(minutes=2), conclusion=None,
            status="queued", run_id=2),
        run(now - timedelta(minutes=46), run_id=1),
    ]
    result = monitor.assess(now, runs, PUBLISHED)
    assert not result.healthy
    assert "45 minutes" in result.reason


def test_scheduled_run_grace_and_missing_heartbeat_after_grace():
    during = START + timedelta(minutes=30)
    after = START + timedelta(minutes=46)
    assert monitor.assess(during, [], PUBLISHED).healthy
    result = monitor.assess(after, [], PUBLISHED)
    assert not result.healthy
    assert "No successful" in result.reason


def test_missing_data_branch_is_blocker_even_during_grace():
    result = monitor.assess(START + timedelta(minutes=5), [], None)
    assert not result.healthy
    assert "cwkc-results" in result.reason


def test_missing_or_naive_timestamps_fail_closed():
    with pytest.raises(ValueError, match="timezone"):
        monitor.parse_time("2026-12-01T10:00:00")
    with pytest.raises(ValueError, match="timezone-aware"):
        monitor.assess(START.replace(tzinfo=None), [], PUBLISHED)


def test_read_snapshot_uses_only_actions_and_branch_metadata(monkeypatch):
    paths = []
    def fake_get(path, _token, *, allow_missing=False):
        paths.append((path, allow_missing))
        if path.endswith("/branches/cwkc-results"):
            return {"commit": {"commit": {"committer": {"date": PUBLISHED.isoformat()}}}}
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": [{"name": "recompute", "conclusion": "success"}]}
        return {"workflow_runs": [run(START)]}
    monkeypatch.setattr(monitor, "_get_json", fake_get)

    runs, published = monitor.read_snapshot("example/cwkc", "synthetic-token")

    assert len(runs) == 1
    assert published == PUBLISHED
    assert paths == [
        ("/repos/example/cwkc/actions/workflows/update.yml/runs?branch=main&per_page=30", False),
        ("/repos/example/cwkc/actions/runs/101/jobs?per_page=100", False),
        ("/repos/example/cwkc/branches/cwkc-results", True),
    ]




def test_skipped_recompute_is_not_a_successful_heartbeat(monkeypatch):
    now = START + timedelta(hours=2)
    def fake_get(path, _token, **_kwargs):
        if path.endswith("/branches/cwkc-results"):
            return {"commit": {"commit": {"committer": {"date": PUBLISHED.isoformat()}}}}
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": [
                {"name": "check-window", "conclusion": "success"},
                {"name": "recompute", "conclusion": "skipped"},
            ]}
        return {"workflow_runs": [run(now - timedelta(minutes=5))]}

    monkeypatch.setattr(monitor, "_get_json", fake_get)
    runs, branch = monitor.read_snapshot("example/cwkc", "synthetic-token")
    assert runs[0]["conclusion"] == "skipped"
    result = monitor.assess(now, runs, branch)
    assert not result.healthy
    assert result.last_success is None


def test_missing_recompute_job_is_not_treated_as_success(monkeypatch):
    now = START + timedelta(hours=2)
    def fake_get(path, _token, **_kwargs):
        if path.endswith("/branches/cwkc-results"):
            return {"commit": {"commit": {"committer": {"date": PUBLISHED.isoformat()}}}}
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": [{"name": "check-window", "conclusion": "success"}]}
        return {"workflow_runs": [run(now - timedelta(minutes=5))]}
    monkeypatch.setattr(monitor, "_get_json", fake_get)
    runs, _ = monitor.read_snapshot("example/cwkc", "synthetic-token")
    assert runs[0]["conclusion"] == "skipped"

def test_branch_404_representation_is_unhealthy(monkeypatch):
    monkeypatch.setattr(
        monitor, "_get_json",
        lambda path, _token, **kwargs: (None if "branches/" in path
                                       else {"workflow_runs": []}),
    )
    _, published = monitor.read_snapshot("example/cwkc", "synthetic-token")
    assert published is None


def test_read_snapshot_rejects_invalid_repository(monkeypatch):
    monkeypatch.setattr(
        monitor, "_get_json",
        lambda *_args, **_kwargs: pytest.fail("No network calls expected"),
    )
    with pytest.raises(ValueError, match="Invalid GitHub repository"):
        monitor.read_snapshot("https://bad.example/", "synthetic-token")


def test_watchdog_never_queries_api_when_collection_disabled(monkeypatch, capsys):
    monkeypatch.delenv("CWKC_INGESTION_ENABLED", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        monitor, "read_snapshot",
        lambda *_args: pytest.fail("No private/public API reads before launch"),
    )
    monitor.main()
    assert "inactive" in capsys.readouterr().out


def test_watchdog_ignores_out_of_season_even_when_switch_enabled(monkeypatch):
    monkeypatch.setenv("CWKC_INGESTION_ENABLED", "true")
    monkeypatch.setattr(monitor, "is_active", lambda _now: False)
    monkeypatch.setattr(
        monitor, "read_snapshot",
        lambda *_args: pytest.fail("No API reads after cutoff"),
    )
    monitor.main()


def test_unhealthy_run_writes_safe_job_summary_and_exits(monkeypatch, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("CWKC_INGESTION_ENABLED", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/cwkc")
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-secret")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(monitor, "is_active", lambda _now: True)
    monkeypatch.setattr(monitor, "read_snapshot", lambda *_args: ([], PUBLISHED))
    monkeypatch.setattr(monitor, "START", START - timedelta(days=50))
    with pytest.raises(SystemExit, match="watchdog detected"):
        monitor.main()
    output = summary.read_text(encoding="utf-8")
    assert "ACTION REQUIRED" in output
    assert "synthetic-secret" not in output
    assert "example/cwkc" in output or "No recorded run" in output
    assert "No successful" in output
    assert "ACTION REQUIRED" in capsys.readouterr().out




def test_github_cli_json_read_is_shell_free_and_secret_safe(monkeypatch):
    commands = []
    def fake_run(argv, **kwargs):
        commands.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"workflow_runs": []}),
                               stderr="")
    monkeypatch.setattr(monitor.subprocess, "run", fake_run)
    output = monitor._get_json("/repos/example/cwkc/actions/workflows/update.yml/runs",
                               "synthetic-private-token")
    assert output == {"workflow_runs": []}
    argv, kwargs = commands[0]
    assert argv == [
        "gh", "api", "--method", "GET",
        "/repos/example/cwkc/actions/workflows/update.yml/runs",
    ]
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
    assert "shell" not in kwargs
    assert kwargs["env"]["GH_TOKEN"] == "synthetic-private-token"
    assert "synthetic-private-token" not in " ".join(argv)


def test_missing_branch_returns_none_but_other_api_errors_fail_closed(monkeypatch):
    def missing(_argv, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404 Not Found")
    monkeypatch.setattr(monitor.subprocess, "run", missing)
    assert monitor._get_json("/repos/example/cwkc/branches/cwkc-results", "dummy",
                             allow_missing=True) is None
    with pytest.raises(RuntimeError, match="monitoring API request failed"):
        monitor._get_json("/repos/example/cwkc/branches/cwkc-results", "dummy")

    def forbidden(_argv, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="private donor information",
                               stderr="HTTP 403 details")
    monkeypatch.setattr(monitor.subprocess, "run", forbidden)
    with pytest.raises(RuntimeError, match="GitHub monitoring API request failed") as error:
        monitor._get_json("/repos/example/cwkc/actions/workflows/update.yml/runs",
                          "synthetic-private-token", allow_missing=True)
    assert "private donor information" not in str(error.value)
    assert "synthetic-private-token" not in str(error.value)


def test_invalid_github_api_json_stops_monitoring(monkeypatch):
    monkeypatch.setattr(
        monitor.subprocess, "run",
        lambda _argv, **_kwargs: SimpleNamespace(
            returncode=0, stdout="{invalid", stderr="",
        ),
    )
    with pytest.raises(json.JSONDecodeError):
        monitor._get_json("/repos/example/cwkc/branches/cwkc-results", "dummy")


def test_watchdog_workflow_contract():
    workflow = (ROOT / ".github/workflows/watchdog.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    assert 'workflows: ["Update results from multiple locations"]' in workflow
    assert "CWKC_INGESTION_ENABLED == 'true'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "python -m scraper.workflow_health" in workflow
    assert "group: cwkc-watchdog" in workflow
    assert "issues: write" in workflow
    assert "if: failure()" in workflow
    assert "gh issue list" in workflow and "if [ -z \"$existing\" ]" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "lgl-form-submission" not in workflow
    assert "scraper.getLglFormData" not in workflow
    refs = re.findall(r"^\s*uses:\s+(\S+)", workflow, flags=re.MULTILINE)
    assert refs and all(re.search(r"@[0-9a-f]{40}$", ref) for ref in refs)


def test_watchdog_schedule_contained_by_backend_season_gate():
    workflow = (ROOT / ".github/workflows/watchdog.yml").read_text(encoding="utf-8")
    assert "17,47 * 30 11 *" in workflow
    assert "17,47 * 1-8 12 *" in workflow
    assert END > START
