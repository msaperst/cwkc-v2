"""Read the one CWKC season configuration and render its browser copy.

Edit public/assets/config/season.json (not JavaScript or GitHub workflow dates)
and run: python -m scraper.season_config --write
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "public/assets/config/season.json"
BROWSER_PATH = ROOT / "public/assets/js/season-config.js"


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Validate timestamps, year, ordering and actual Eastern offset."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"year", "timezone", "start", "end"}:
        raise ValueError("Season config must have year, timezone, start and end")
    if type(data["year"]) is not int or not (2000 <= data["year"] <= 2100):
        raise ValueError("Invalid competition year")
    zone = ZoneInfo(data["timezone"])
    start, end = (datetime.fromisoformat(data[key]) for key in ("start", "end"))
    for instant in (start, end):
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Season dates must include a timezone offset")
        if instant.astimezone(zone).replace(tzinfo=None) != instant.replace(tzinfo=None):
            raise ValueError("Season date/offset does not match configured timezone")
    if start >= end or start.year != data["year"] or end.year != data["year"]:
        raise ValueError("Season year or start/end ordering invalid")
    return data


def render_browser_config(config: dict) -> str:
    """Generated script loads synchronously before main.js; no network request."""
    serialized = json.dumps(
        {key: config[key] for key in ("year", "timezone", "start", "end")},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return (
        "// Generated from public/assets/config/season.json. Do not edit manually.\n"
        f"globalThis.CWKC_SEASON = Object.freeze({serialized});\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Regenerate browser configuration")
    parser.add_argument("--check", action="store_true", help="Check generated config is current")
    args = parser.parse_args()
    expected = render_browser_config(load_config())
    if args.write:
        BROWSER_PATH.write_text(expected, encoding="utf-8")
        print(f"Updated {BROWSER_PATH.relative_to(ROOT)}")
        return 0
    if args.check:
        if not BROWSER_PATH.exists() or BROWSER_PATH.read_text(encoding="utf-8") != expected:
            raise SystemExit("Generated season-config.js is stale. Run python -m scraper.season_config --write")
        print("Browser season config matches canonical JSON")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
