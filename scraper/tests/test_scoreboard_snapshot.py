"""Synthetic-only tests for the separate-results-branch publishing contract."""
from datetime import timedelta
from pathlib import Path
import subprocess

import pytest

from scraper import contest_window, scoreboard_snapshot

MAIN = b"uva_total,vt_total\n0,0\n"
PUBLISHED = b"uva_total,vt_total\n12,9\n"


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)


@pytest.fixture
def two_branch_repo(tmp_path, monkeypatch):
    """Local git simulation; neither GitHub nor donor resources are accessed."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "Synthetic Test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    target = tmp_path / scoreboard_snapshot.RESULTS_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(MAIN)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "static placeholder")
    _git(tmp_path, "checkout", "-qb", "cwkc-results")
    target.write_bytes(PUBLISHED)
    _git(tmp_path, "commit", "-qam", "generated result")
    _git(tmp_path, "checkout", "-q", "main")
    _git(tmp_path, "fetch", "-q", ".", "cwkc-results:refs/remotes/origin/cwkc-results")
    monkeypatch.chdir(tmp_path)
    return target


def test_restore_published_data_without_modifying_static_main(two_branch_repo, tmp_path):
    scoreboard_snapshot.restore_snapshot(backup=True)
    assert two_branch_repo.read_bytes() == PUBLISHED
    assert (tmp_path / ".cwkc-previous-results.csv").read_bytes() == PUBLISHED
    assert subprocess.run(["git", "show", "HEAD:public/assets/csv/results.csv"],
                          capture_output=True, check=True).stdout == MAIN



def test_synthetic_worktree_publishes_only_csv_to_data_branch(two_branch_repo, tmp_path):
    """Rehearse the git worktree/commit/push mechanics without GitHub."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", str(remote))
    _git(tmp_path, "remote", "add", "origin", str(remote))
    _git(tmp_path, "push", "-q", "origin", "cwkc-results")
    worktree = tmp_path / "published"
    _git(tmp_path, "worktree", "add", "--detach", str(worktree), "origin/cwkc-results")
    (worktree / scoreboard_snapshot.RESULTS_PATH).write_bytes(b"uva_total,vt_total\n50,10\n")
    _git(worktree, "add", "--", str(scoreboard_snapshot.RESULTS_PATH))
    _git(worktree, "commit", "-qm", "Update CWKC results")
    _git(worktree, "push", "-q", "origin", "HEAD:cwkc-results")

    result = subprocess.run(["git", "--git-dir", str(remote), "show",
                             "cwkc-results:public/assets/csv/results.csv"],
                            capture_output=True, check=True)
    assert result.stdout == b"uva_total,vt_total\n50,10\n"
    main = subprocess.run(["git", "show", "HEAD:public/assets/csv/results.csv"],
                          capture_output=True, check=True)
    assert main.stdout == MAIN

def test_restore_refuses_schema_drift_without_changing_file(two_branch_repo):
    old = b"uva_total,vt_total,new_category\n0,0,0\n"
    two_branch_repo.write_bytes(old)
    with pytest.raises(ValueError, match="schema differs"):
        scoreboard_snapshot.restore_snapshot()
    assert two_branch_repo.read_bytes() == old


def test_restore_refuses_missing_published_file(two_branch_repo, monkeypatch):
    monkeypatch.setattr(scoreboard_snapshot, "DATA_REF", "refs/remotes/origin/nonexistent")
    with pytest.raises(RuntimeError, match="missing its scoreboard"):
        scoreboard_snapshot.restore_snapshot()
    assert two_branch_repo.read_bytes() == MAIN


@pytest.mark.parametrize("invalid", [
    b"",
    b"uva,vt\n",
    b"uva,vt\n1\n",
    b"uva,uva\n1,2\n",
    b"uva,vt\n1,2\n3,4\n",
    b"\xff",
])
def test_reject_malformed_scoreboard(invalid):
    with pytest.raises(ValueError):
        scoreboard_snapshot._header(invalid)


@pytest.mark.parametrize("when", [
    contest_window.START,
    contest_window.START + timedelta(days=1),
    contest_window.END,
    contest_window.END + timedelta(seconds=1),
])
def test_missing_data_branch_refuses_from_start_onward(when):
    with pytest.raises(RuntimeError, match="missing after kickoff"):
        scoreboard_snapshot.require_prelaunch(when)


def test_missing_data_branch_allowed_only_before_kickoff():
    scoreboard_snapshot.require_prelaunch(contest_window.START - timedelta(seconds=1))


def test_prelaunch_check_rejects_naive_datetime():
    naive_datetime = contest_window.START.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        scoreboard_snapshot.require_prelaunch(naive_datetime)



def test_cli_restore_uses_optional_backup(monkeypatch, tmp_path):
    import sys
    called = []
    monkeypatch.setattr(scoreboard_snapshot, "restore_snapshot",
                        lambda backup=False: called.append(backup))
    monkeypatch.setattr(sys, "argv", ["scoreboard_snapshot", "restore", "--backup"])
    scoreboard_snapshot.main()
    assert called == [True]


def test_cli_prelaunch_gate(monkeypatch):
    import sys
    called = []
    monkeypatch.setattr(scoreboard_snapshot, "require_prelaunch",
                        lambda: called.append(True))
    monkeypatch.setattr(sys, "argv", ["scoreboard_snapshot", "require-prelaunch"])
    scoreboard_snapshot.main()
    assert called == [True]


def test_cli_requires_action(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "argv", ["scoreboard_snapshot"])
    with pytest.raises(SystemExit) as exc:
        scoreboard_snapshot.main()
    assert exc.value.code == 2

def test_deploy_never_replaces_active_scoreboard_with_main():
    deploy = (Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml").read_text()
    assert "ref: main" in deploy
    assert "if: github.ref == 'refs/heads/main'" in deploy
    assert "python -m scraper.scoreboard_snapshot restore" in deploy
    assert "python -m scraper.scoreboard_snapshot require-prelaunch" in deploy
    assert deploy.index("scoreboard_snapshot restore") < deploy.index("Upload artifact")
    assert "cwkc-results" in deploy


def test_schedules_are_gate_protected_and_aligned_with_utc_cutoff():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/update.yml").read_text()
    assert "schedule:" in workflow
    assert "cron: '2-59/5 * 30 11 *'" in workflow
    assert "cron: '2-59/5 * 1-8 12 *'" in workflow
    assert "cron: '59 0 8 12 *'" in workflow
    assert workflow.index("scoreboard_snapshot restore") < workflow.index("getLglFormData")
    assert workflow.index("Reject ingestion after cutoff") < workflow.index("scoreboard_snapshot restore")
    assert workflow.index("Reject publication after cutoff") < workflow.index("push origin HEAD:cwkc-results")
    assert "push origin HEAD:main" not in workflow
