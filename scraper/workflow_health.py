"""Read-only GitHub Actions watchdog for CWKC event-week ingestion.

Requires only repository Actions metadata and the results branch commit date.
It never connects to Gmail, LGL or Sheets, and never changes published scores.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re
import subprocess

from .contest_window import START, is_active

MAX_SUCCESS_AGE = timedelta(minutes=45)
STARTUP_GRACE = timedelta(minutes=45)
BAD_CONCLUSIONS = frozenset({"failure", "timed_out", "cancelled", "action_required"})


def parse_time(value: str) -> datetime:
    """GitHub dates are UTC ISO 8601 timestamps."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("GitHub timestamp must include a timezone")
    return result


@dataclass(frozen=True)
class Health:
    healthy: bool
    reason: str
    last_success: datetime | None = None
    latest_run_id: int | None = None
    published_at: datetime | None = None


def assess(now: datetime, runs: list[dict], published_at: datetime | None) -> Health:
    """Evaluate a synthetic or real workflow snapshot without any API writes."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Watchdog requires timezone-aware current time")
    ordered = sorted(runs, key=lambda run: parse_time(run["created_at"]), reverse=True)
    latest = ordered[0] if ordered else None
    latest_id = latest.get("id") if latest else None
    successes = [r for r in ordered if r.get("status") == "completed"
                 and r.get("conclusion") == "success"]
    last = successes[0] if successes else None
    last_at = parse_time(last.get("updated_at", last["created_at"])) if last else None
    terminal = next((r for r in ordered if r.get("status") == "completed"), None)
    failed = (terminal is not None and terminal.get("conclusion") in BAD_CONCLUSIONS
              and (last is None or parse_time(terminal["created_at"]) >
                   parse_time(last["created_at"])))
    fields = {"last_success": last_at, "latest_run_id": latest_id,
              "published_at": published_at}
    if published_at is None:
        return Health(False, "The cwkc-results publishing branch is missing", **fields)
    if failed:
        return Health(False, "The most recent completed ingestion run failed", **fields)
    if last_at is None:
        if now < START + STARTUP_GRACE:
            return Health(True, "Within kickoff grace period; awaiting the first run", **fields)
        return Health(False, "No successful ingestion run since kickoff", **fields)
    if now - last_at > MAX_SUCCESS_AGE:
        return Health(False, "No successful ingestion run in the last 45 minutes", **fields)
    return Health(True, "Recent ingestion run succeeded", **fields)


def _get_json(path: str, token: str, *, allow_missing: bool = False):
    """Read a fixed GitHub metadata path via gh; never print API errors/tokens."""
    # gh is installed on GitHub-hosted Actions runners. A positional argument
    # list (no shell) keeps API paths and credentials out of command parsing.
    result = subprocess.run(
        ["gh", "api", "--method", "GET", path],
        env={**os.environ, "GH_TOKEN": token},
        capture_output=True, text=True, check=False, timeout=20,
    )
    if result.returncode != 0:
        if allow_missing and "HTTP 404" in result.stderr:
            return None
        raise RuntimeError("GitHub monitoring API request failed")
    return json.loads(result.stdout)


def read_snapshot(repo: str, token: str) -> tuple[list[dict], datetime | None]:
    """Read recent main-branch update runs and latest data-branch commit."""
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is None:
        raise ValueError("Invalid GitHub repository identity")
    raw_runs = _get_json(
        f"/repos/{repo}/actions/workflows/update.yml/runs?branch=main&per_page=30",
        token,
    )["workflow_runs"]
    # GitHub reports overall workflow success even when check-window succeeded
    # but recompute was SKIPPED (e.g. collection was previously switched off).
    # Only an actual successful recompute is a healthy ingestion heartbeat.
    runs = []
    for item in raw_runs:
        if item.get("status") == "completed" and item.get("conclusion") == "success":
            job_data = _get_json(
                f"/repos/{repo}/actions/runs/{int(item['id'])}/jobs?per_page=100",
                token,
            )
            recomputed = any(
                job.get("name") == "recompute" and job.get("conclusion") == "success"
                for job in job_data["jobs"]
            )
            if not recomputed:
                item = {**item, "conclusion": "skipped"}
        runs.append(item)
    branch = _get_json(f"/repos/{repo}/branches/cwkc-results", token,
                       allow_missing=True)
    if branch is None:
        return runs, None
    published_at = parse_time(branch["commit"]["commit"]["committer"]["date"])
    return runs, published_at


def render_summary(health: Health, repo: str) -> str:
    """Expose only workflow-run and CSV publication metadata, never donor fields."""
    state = "HEALTHY" if health.healthy else "ACTION REQUIRED"
    latest_url = (f"https://github.com/{repo}/actions/runs/{health.latest_run_id}"
                  if health.latest_run_id is not None else "No recorded run")
    last_success = (health.last_success.isoformat()
                    if health.last_success else "None")
    last_published = (health.published_at.isoformat()
                      if health.published_at else "No data branch")
    return (
        f"## CWKC ingestion watchdog: {state}\n\n"
        f"{health.reason}.\n\n"
        f"- Last successful ingestion completion (UTC): {last_success}\n"
        f"- Latest update run: {latest_url}\n"
        f"- Latest results-branch commit (UTC): {last_published}\n\n"
        "An unchanged CSV is not an outage. The results-branch timestamp "
        "is publication metadata, not evidence that every LGL gift was processed.\n"
    )


def main() -> None:
    now = datetime.now(timezone.utc)
    # Never touch other systems or alert while collection is intentionally off.
    if os.getenv("CWKC_INGESTION_ENABLED") != "true" or not is_active(now):
        print("CWKC watchdog inactive: outside the authorized collection window or disabled.")
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    runs, published_at = read_snapshot(repo, token)
    health = assess(now, runs, published_at)
    summary = render_summary(health, repo)
    print(summary)
    # The workflow shell handles GITHUB_STEP_SUMMARY; never open a path
    # provided through the environment from this monitoring process.
    if not health.healthy:
        raise SystemExit("CWKC ingestion watchdog detected a problem")


if __name__ == "__main__":
    main()
