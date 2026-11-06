#!/usr/bin/env python3
"""Read the current Forms response tabs and update participation score columns.

The public scoreboard only receives aggregate counts. Photo-release consent
is deliberately NOT a condition for Hanukkah scoring or used for publication.
"""
import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import gspread
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SEASON_CONFIG = ROOT / "public/assets/config/season.json"

# The 2022 gathering workbook is reused, but its 'Form Responses 1' tab is
# the current responses tab. Archived year-named tabs must never be counted.
GATHERING_SHEET_ID = "1EOURh5B5mKy0AjAgTKMObYtdmvZGI8txVC18DCmlA5o"
HANUKKAH_SHEET_ID = "1WwpnVdW94jdvtyxVhNxNk2zz120Z57xu_2OkjcoVs2M"
CURRENT_TAB = "Form Responses 1"

# These prefix matches are grounded in the actual final 2026 Sheets' headers.
# They tolerate trailing spaces and punctuation, but reject missing or
# duplicate/ambiguous required questions rather than silently publishing 0.
GATHERING_FIELDS = {
    "timestamp": "timestamp",
    "host": "name",
    "school": "which school are you supporting?",
    "affiliation": "affiliation",
    "attendees": "who was in attendance at your event?",
    "venue": "where was your event?",
    "photo": "please submit photos of your event!",
}
HANUKKAH_FIELDS = {
    "timestamp": "timestamp",
    "name": "name",
    "email": "non-school affiliated email",
    "school": "which school are you supporting?",
    "qualifies": "are you an alumni that graduated in the past 15 years, or a parent of one?",
    "graduation_year": "graduation year (if applicable)",
    "photo": "submit your photo here!",
    "photo_release": "photo release:",
}


@dataclass
class SubmittedData:
    """Aggregated participation counts for both sides."""

    hokies: int = 0
    hoos: int = 0

    def increment(self, school: str) -> None:
        if school == "uva":
            self.hoos += 1
        elif school == "vt":
            self.hokies += 1
        else:
            raise ValueError("Unsupported school in participation response")


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip().casefold()


def _school(value: str) -> str:
    school = _normalize(value)
    if school in {"brody", "uva", "university of virginia", "brody jewish center",
                  "hillel at uva", "university"} or "brody" in school or re.search(r"\buva\b", school):
        return "uva"
    if school in {"vt", "hillel at vt", "virginia tech", "hillel at virginia tech"} or "tech" in school:
        return "vt"
    # Unknown non-empty school names must not silently turn into zero counts.
    raise ValueError("Unrecognized school in participation response")


def _in_season(value: str, season_year: int) -> bool:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError("Invalid response timestamp")
    return timestamp.year == season_year


def _attendance_names(value: str) -> set[str]:
    """Count participants, not affiliation descriptions or blank delimiters."""
    return {_normalize(name) for name in re.split(r"[,;\n\r]+", value)
            if _normalize(name)}


class SubmissionUpdater:
    """Read current Forms response tabs, validate and update the result CSV."""

    def __init__(self, credentials_path: str, results_csv_path: str,
                 season_year: int | None = None):
        self.gc = gspread.service_account(filename=credentials_path)
        self.results_csv_path = results_csv_path
        self.df = pd.read_csv(results_csv_path)
        if season_year is None:
            season_year = int(json.loads(SEASON_CONFIG.read_text(encoding="utf-8"))["year"])
        self.season_year = season_year

    def _response_rows(self, sheet_id: str, fields: dict[str, str]) -> list[dict[str, str]]:
        rows = self.gc.open_by_key(sheet_id).worksheet(CURRENT_TAB).get_all_values()
        if not rows:
            raise ValueError("Response Sheet has no header row")
        headers = [_normalize(h) for h in rows[0]]
        column_indexes = {}
        for name, prefix in fields.items():
            matches = [index for index, header in enumerate(headers)
                       if header == prefix or header.startswith(prefix + " ")]
            if not matches and prefix.endswith(":"):
                matches = [index for index, header in enumerate(headers)
                           if header.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError(f"Response Sheet column missing or ambiguous: {name}")
            column_indexes[name] = matches[0]
        output = []
        for row in rows[1:]:
            if not any(str(cell).strip() for cell in row):
                continue
            output.append({name: str(row[index]).strip() if index < len(row) else ""
                           for name, index in column_indexes.items()})
        return output

    def get_alumni_gatherings(self) -> SubmittedData:
        """Count distinct qualifying in-person gatherings of >=4 including host."""
        data = SubmittedData()
        seen = set()
        for record in self._response_rows(GATHERING_SHEET_ID, GATHERING_FIELDS):
            if not _in_season(record["timestamp"], self.season_year):
                continue
            school = _school(record["school"])
            affiliation = _normalize(record["affiliation"])
            # The scoreboard category is alumni or current-parent gatherings;
            # a community-only or student-only host does not qualify.
            if not ("alum" in affiliation or "current parent" in affiliation):
                continue
            venue = _normalize(record["venue"])
            if not venue or any(token in venue for token in
                                ("virtual", "zoom", "online", "google meet", "teams meeting")):
                continue
            # Names field can include the host; include them exactly once.
            attendees = _attendance_names(record["attendees"])
            host = _normalize(record["host"])
            if host:
                attendees.add(host)
            if len(attendees) < 4 or not record["photo"]:
                continue
            identity = (school, _normalize(record["timestamp"]), host, venue,
                        tuple(sorted(attendees)))
            if identity in seen:
                continue
            seen.add(identity)
            data.increment(school)
        return data

    def get_hanukkah_photos(self) -> SubmittedData:
        """Count unique qualifying photo submitters, regardless of release answer."""
        data = SubmittedData()
        seen_emails = set()
        seen_names = set()
        for record in self._response_rows(HANUKKAH_SHEET_ID, HANUKKAH_FIELDS):
            if not _in_season(record["timestamp"], self.season_year):
                continue
            school = _school(record["school"])
            eligibility = _normalize(record["qualifies"])
            if eligibility in {"no", "false"}:
                continue
            if not eligibility.startswith("yes"):
                raise ValueError("Unrecognized Hanukkah eligibility answer")
            if not record["photo"]:
                continue
            name = _normalize(record["name"])
            email = _normalize(record["email"])
            if not name and not email:
                raise ValueError("Hanukkah response missing participant identity")
            email_key = (school, email) if email else None
            name_key = (school, name) if name else None
            if email_key in seen_emails or name_key in seen_names:
                continue
            if email_key is not None:
                seen_emails.add(email_key)
            if name_key is not None:
                seen_names.add(name_key)
            # PHOTO RELEASE: Yes/No is intentionally NOT checked here.
            # It controls optional public display, not scoring.
            data.increment(school)
        return data

    def update_results(self, dry_run: bool = False) -> SubmittedData:
        """Validate both inputs before writing the existing scoreboard schema."""
        gatherings = self.get_alumni_gatherings()
        photos = self.get_hanukkah_photos()
        columns = ("uva_alumni_gatherings", "vt_alumni_gatherings",
                   "uva_hanukkah_photos", "vt_hanukkah_photos")
        if len(self.df) != 1 or any(column not in self.df.columns for column in columns):
            raise ValueError("Results CSV does not match the 2026 participation schema")
        self.df.loc[0, "uva_alumni_gatherings"] = gatherings.hoos
        self.df.loc[0, "vt_alumni_gatherings"] = gatherings.hokies
        self.df.loc[0, "uva_hanukkah_photos"] = photos.hoos
        self.df.loc[0, "vt_hanukkah_photos"] = photos.hokies
        print(f"Gatherings: UVA={gatherings.hoos}, VT={gatherings.hokies}")
        print(f"Hanukkah submitters: UVA={photos.hoos}, VT={photos.hokies}")
        if dry_run:
            print("Read-only preview: results CSV was not written")
        else:
            self.df.to_csv(self.results_csv_path, index=False)
            print("Results CSV updated")
        return photos


def main() -> None:
    parser = argparse.ArgumentParser(description="Import aggregate CWKC participation scores")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read both Sheets and preview counts; do not modify CSV")
    parser.add_argument("--credentials-file", default="spreadsheet_credentials.json")
    parser.add_argument("--results-csv", default="../public/assets/csv/results.csv")
    args = parser.parse_args()
    updater = SubmissionUpdater(args.credentials_file, args.results_csv)
    updater.update_results(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
