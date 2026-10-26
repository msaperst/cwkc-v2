"""Fail-closed CWKC season gate for production GitHub Actions.

The official start hour is currently assumed to be midnight Eastern; update
these dates together with the frontend after organizer confirmation.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
START = datetime(2026, 11, 30, 0, 0, tzinfo=EASTERN)
END = datetime(2026, 12, 7, 20, 0, tzinfo=EASTERN)


def allowed_sources(event_name: str, action: str = "", now: datetime | None = None) -> tuple[bool, bool]:
    """Return (run LGL, run Google Forms), or (False, False) outside season.

    Both dispatch and manual events must honor the exact same season window.
    Unknown events and actions are rejected rather than treated as a manual run.
    """
    instant = now if now is not None else datetime.now(tz=EASTERN)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Contest gate needs a timezone-aware datetime")
    if not START <= instant < END:
        return False, False
    # Recompute BOTH sources for every accepted event. GitHub concurrency can
    # coalesce queued dispatches; one successful run must refresh all sources.
    if event_name == "workflow_dispatch":
        return True, True
    if event_name == "repository_dispatch" and action in (
        "lgl-form-submission", "sheet-change"
    ):
        return True, True
    return False, False


def main() -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    action = os.environ.get("GITHUB_EVENT_ACTION", "")
    lgl, google = allowed_sources(event, action)
    in_range = lgl or google
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"in_range={str(in_range).lower()}\n")
            stream.write(f"lgl={str(lgl).lower()}\n")
            stream.write(f"google={str(google).lower()}\n")
    print("CWKC season gate:", "allowed" if in_range else "blocked",
          f"(event={event}, action={action or 'none'})")
    # Verify-only is used again just before results publication to prevent an
    # update started before closing from being published after the deadline.
    if "--verify-only" in __import__("sys").argv and not in_range:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
