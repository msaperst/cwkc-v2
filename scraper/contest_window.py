"""2026 CWKC collection window. Keep these instants synchronized with public/assets/js/main.js.

The window is [start, end): kickoff is allowed; at exactly 8 PM Eastern,
new runs must not begin. These November/December dates are both EST (UTC-05).
"""
from datetime import datetime, timezone
from pathlib import Path
import os

START = datetime.fromisoformat("2026-11-30T00:00:00-05:00")
END = datetime.fromisoformat("2026-12-07T20:00:00-05:00")


def is_active(now: datetime | None = None) -> bool:
    """Return whether new ingestion may start at this instant."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required")
    return START <= now < END


def main() -> None:
    """Write the GitHub Actions step output; no credentials or data read."""
    active = is_active()
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with Path(output_file).open("a", encoding="utf-8") as output:
            output.write(f"active={str(active).lower()}\n")
    print("CWKC 2026 data collection is " + ("enabled" if active else "disabled"))


if __name__ == "__main__":
    main()
