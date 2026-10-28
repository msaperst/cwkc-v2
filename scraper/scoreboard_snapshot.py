"""Fail-closed public scoreboard snapshot handling for GitHub Pages.

CWKC code lives on protected main. Generated results live on cwkc-results,
a separate data branch so automated results never require bypassing code PRs.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
import subprocess

from .contest_window import START

RESULTS_PATH = Path("public/assets/csv/results.csv")
DATA_REF = "refs/remotes/origin/cwkc-results"
BACKUP_PATH = Path(".cwkc-previous-results.csv")


def _header(payload: bytes) -> list[str]:
    """Validate the single-row scoreboard before publication or restoration."""
    try:
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Invalid scoreboard CSV encoding") from exc
    if len(rows) != 2 or not rows[0] or not all(rows[0]):
        raise ValueError("Expected scoreboard header and exactly one result row")
    if len(set(rows[0])) != len(rows[0]) or len(rows[0]) != len(rows[1]):
        raise ValueError("Invalid scoreboard columns")
    return rows[0]


def restore_snapshot(*, backup: bool = False) -> None:
    """Restore only the hard-coded scoreboard path from the fixed data ref.

    No user-controlled filenames or Git refs are accepted by the CLI.
    """
    result = subprocess.run(
        ["git", "show", f"{DATA_REF}:{RESULTS_PATH.as_posix()}"],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError("Results branch is missing its scoreboard CSV")
    previous = result.stdout
    if _header(RESULTS_PATH.read_bytes()) != _header(previous):
        raise ValueError("Published CSV schema differs from main; migrate data branch before deployment")
    if backup:
        # Fixed local file, outside public/. Never accepts user or workflow paths.
        BACKUP_PATH.write_bytes(previous)
    RESULTS_PATH.write_bytes(previous)


def require_prelaunch(now: datetime | None = None) -> None:
    """A missing data branch is acceptable *only before* the season begins."""
    when = now if now is not None else datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Current time must be timezone-aware")
    if when >= START:
        raise RuntimeError("Results branch missing after kickoff; refusing to deploy stale main CSV")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the public CWKC scoreboard snapshot")
    subcommands = parser.add_subparsers(dest="command", required=True)
    restore = subcommands.add_parser("restore")
    restore.add_argument("--backup", action="store_true")
    subcommands.add_parser("require-prelaunch")
    args = parser.parse_args()
    if args.command == "restore":
        restore_snapshot(backup=args.backup)
    else:
        require_prelaunch()


if __name__ == "__main__":
    main()
