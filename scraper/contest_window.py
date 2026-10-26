"""CWKC collection window loaded from the shared season JSON configuration.

Window is [start, end): allow kickoff, reject ingestion at the exact end.
"""
from datetime import datetime, timezone
import sys
from pathlib import Path
import os

from .season_config import load_config

_config = load_config()
START = datetime.fromisoformat(_config["start"])
END = datetime.fromisoformat(_config["end"])


def is_active(now: datetime | None = None) -> bool:
    """Return whether new ingestion may start at this instant."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required")
    return START <= now < END


def main() -> None:
    """Write the GitHub Actions step output; no credentials or data read."""
    # A missing or non-true repo variable is a deliberate production kill switch.
    active = is_active() and os.getenv("CWKC_INGESTION_ENABLED") == "true"
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with Path(output_file).open("a", encoding="utf-8") as output:
            output.write(f"active={str(active).lower()}\n")
    print(f"CWKC {_config['year']} data collection is " + ("enabled" if active else "disabled"))
    if "--require-active" in sys.argv[1:] and not active:
        raise SystemExit("Outside approved collection window; refusing to process data")


if __name__ == "__main__":
    main()
