"""Offline full publishing/restart drill: synthetic Git branches, never GitHub.

Covers the real sequence of restoring the last CSV, committing only changed
results, and overlaying the published snapshot during a clean Pages deployment.
"""
from pathlib import Path
import subprocess

import pytest

from scraper import scoreboard_snapshot

RESULTS = scoreboard_snapshot.RESULTS_PATH
ZERO = b"uva_total,vt_total\n0,0\n"
FIRST = b"uva_total,vt_total\n12,9\n"
SECOND = b"uva_total,vt_total\n30,14\n"


def git(folder: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=folder, check=True, capture_output=True, text=True,
    ).stdout.strip()


def write_result(folder: Path, data: bytes) -> None:
    target = folder / RESULTS
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def branch_result(remote: Path) -> bytes:
    result = subprocess.run(
        ["git", "--git-dir", str(remote), "show",
         f"cwkc-results:{RESULTS.as_posix()}"],
        check=True, capture_output=True,
    )
    return result.stdout


@pytest.fixture
def rehearsal(tmp_path):
    """Create disposable main/data branches in a local bare remote."""
    remote = tmp_path / "origin.git"
    source = tmp_path / "source"
    source.mkdir()
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(source, "init", "-q", "-b", "main")
    git(source, "config", "user.name", "CWKC Offline Drill")
    git(source, "config", "user.email", "synthetic@example.invalid")
    write_result(source, ZERO)
    (source / "public" / "index.html").write_text("synthetic website v1", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "Initial public placeholder")
    git(source, "remote", "add", "origin", str(remote))
    git(source, "push", "-q", "origin", "main")
    git(source, "switch", "-qc", "cwkc-results")
    git(source, "push", "-q", "origin", "cwkc-results")
    git(source, "switch", "-q", "main")
    return {"remote": remote, "source": source, "root": tmp_path}


def restore_for_update(rehearsal, monkeypatch) -> bytes:
    """Simulate the gate-approved restore step, not the live importer."""
    source = rehearsal["source"]
    git(source, "fetch", "-q", "origin",
        "refs/heads/cwkc-results:refs/remotes/origin/cwkc-results")
    monkeypatch.chdir(source)
    scoreboard_snapshot.restore_snapshot(backup=True)
    return (source / scoreboard_snapshot.BACKUP_PATH).read_bytes()


def publish_recomputed_csv(rehearsal, monkeypatch, payload: bytes) -> bool:
    """Simulate the worktree stage of update.yml using ONLY synthetic CSV."""
    source = rehearsal["source"]
    previous = restore_for_update(rehearsal, monkeypatch)
    write_result(source, payload)
    if previous == payload:
        return False
    worktree = rehearsal["root"] / "published-worktree"
    git(source, "worktree", "add", "-q", "--detach", str(worktree),
        "origin/cwkc-results")
    try:
        write_result(worktree, payload)
        git(worktree, "config", "user.name", "CWKC Offline Drill")
        git(worktree, "config", "user.email", "synthetic@example.invalid")
        git(worktree, "add", "--", str(RESULTS))
        git(worktree, "diff", "--cached", "--check")
        git(worktree, "commit", "-qm", "Update CWKC results")
        git(worktree, "push", "-q", "origin", "HEAD:cwkc-results")
    finally:
        git(source, "worktree", "remove", "--force", str(worktree))
    return True


def fresh_pages_checkout(rehearsal, monkeypatch, name: str) -> Path:
    """A new main checkout performs the same safe overlay as deploy.yml."""
    destination = rehearsal["root"] / name
    git(rehearsal["root"], "clone", "-q", "--branch", "main",
        str(rehearsal["remote"]), str(destination))
    git(destination, "fetch", "-q", "origin",
        "refs/heads/cwkc-results:refs/remotes/origin/cwkc-results")
    monkeypatch.chdir(destination)
    scoreboard_snapshot.restore_snapshot()
    return destination


def test_fresh_deploy_survives_result_branch_commit_and_skips_unchanged(
    rehearsal, monkeypatch,
):
    remote = rehearsal["remote"]
    source = rehearsal["source"]
    initial_sha = git(source, "ls-remote", "origin", "refs/heads/cwkc-results").split()[0]

    assert not publish_recomputed_csv(rehearsal, monkeypatch, ZERO)
    assert git(source, "ls-remote", "origin", "refs/heads/cwkc-results").split()[0] == initial_sha

    assert publish_recomputed_csv(rehearsal, monkeypatch, FIRST)
    changed_sha = git(source, "ls-remote", "origin", "refs/heads/cwkc-results").split()[0]
    assert changed_sha != initial_sha
    assert branch_result(remote) == FIRST
    git(source, "fetch", "-q", "origin",
        "refs/heads/cwkc-results:refs/remotes/origin/cwkc-results")
    assert git(source, "diff", "--name-only", "main", "origin/cwkc-results") == RESULTS.as_posix()

    site = fresh_pages_checkout(rehearsal, monkeypatch, "fresh-pages")
    assert (site / RESULTS).read_bytes() == FIRST
    assert (site / "public/index.html").read_text(encoding="utf-8") == "synthetic website v1"
    assert git(site, "show", f"main:{RESULTS.as_posix()}") == ZERO.decode().strip()

    assert not publish_recomputed_csv(rehearsal, monkeypatch, FIRST)
    assert git(source, "ls-remote", "origin", "refs/heads/cwkc-results").split()[0] == changed_sha


def test_deployment_failure_after_results_push_can_recover_from_remote(
    rehearsal, monkeypatch,
):
    assert publish_recomputed_csv(rehearsal, monkeypatch, FIRST)
    # Simulate a second import succeeding locally, then failing BEFORE its
    # results-branch push. It must not change what a new deployment restores.
    write_result(rehearsal["source"], SECOND)
    assert branch_result(rehearsal["remote"]) == FIRST

    recovered = fresh_pages_checkout(rehearsal, monkeypatch, "recovered")
    assert (recovered / RESULTS).read_bytes() == FIRST
    # Later successful replay publishes the new snapshot exactly once.
    assert publish_recomputed_csv(rehearsal, monkeypatch, SECOND)
    latest = fresh_pages_checkout(rehearsal, monkeypatch, "later")
    assert (latest / RESULTS).read_bytes() == SECOND


def test_code_merge_cannot_replace_published_results_with_placeholder(
    rehearsal, monkeypatch,
):
    assert publish_recomputed_csv(rehearsal, monkeypatch, FIRST)
    source = rehearsal["source"]
    (source / "public/index.html").write_text("synthetic website v2", encoding="utf-8")
    git(source, "add", "--", "public/index.html")
    git(source, "commit", "-qm", "Approved code-only change")
    git(source, "push", "-q", "origin", "main")

    deployed = fresh_pages_checkout(rehearsal, monkeypatch, "code-update")
    assert (deployed / "public/index.html").read_text(encoding="utf-8") == "synthetic website v2"
    assert (deployed / RESULTS).read_bytes() == FIRST
    assert git(deployed, "show", f"main:{RESULTS.as_posix()}") == ZERO.decode().strip()


def test_schema_drift_refuses_deploy_without_altering_snapshot(
    rehearsal, monkeypatch,
):
    assert publish_recomputed_csv(rehearsal, monkeypatch, FIRST)
    source = rehearsal["source"]
    new_schema = b"uva_total,vt_total,unapproved_category\n0,0,0\n"
    write_result(source, new_schema)
    with pytest.raises(ValueError, match="schema differs"):
        restore_for_update(rehearsal, monkeypatch)
    assert (source / RESULTS).read_bytes() == new_schema
    assert branch_result(rehearsal["remote"]) == FIRST
