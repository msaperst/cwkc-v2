#!/usr/bin/env python3
"""
update_submissions.py
---------------------

Pulls data from multiple Google Sheets and updates results.csv accordingly.

Usage:
    python update_submissions.py
"""

from dataclasses import dataclass

import gspread
import pandas as pd


@dataclass
class SubmittedData:
    """Tracks score data for both schools."""
    hokies: int = 0
    hoos: int = 0


class SubmissionUpdater:
    """Main class that retrieves, processes, and updates submission data."""

    def __init__(self, credentials_path: str, results_csv_path: str):
        self.gc = gspread.service_account(filename=credentials_path)
        self.results_csv_path = results_csv_path
        self.df = pd.read_csv(results_csv_path)

    # ---------- Data Retrieval Methods ---------- #

    def get_alumni_gatherings(self) -> SubmittedData:
        """Gets alumni gathering information."""
        sh = self.gc.open_by_key("1EOURh5B5mKy0AjAgTKMObYtdmvZGI8txVC18DCmlA5o")
        rows = sh.sheet1.get_all_values()
        rows.pop(0)  # remove header

        data = SubmittedData()
        for row in rows:
            raw_names = row[4]

            # Normalize separators: treat commas and newlines as equivalent
            # Replace newlines with commas, then split
            normalized = raw_names.replace("\r\n", "\n").replace("\r", "\n")
            normalized = normalized.replace("\n", ",")  # unify separators

            # Split into individual names, strip whitespace, and remove empty entries
            names = [n.strip() for n in normalized.split(",") if n.strip()]

            # Check if we have at least 4 names
            enough_people = len(names) >= 4

            if "Brody" in row[2] and enough_people:
                data.hoos += 1
            if "Tech" in row[2] and enough_people:
                data.hokies += 1

        return data

    def get_alumni_memories(self) -> SubmittedData:
        """Gets alumni hillel memory information."""
        sh = self.gc.open_by_key("128regkVYg_RqRyZszxBHpIv1z7RkM0_HQlDBr58xkCc")
        rows = sh.sheet1.get_all_values()
        rows.pop(0)

        data = SubmittedData()
        for row in rows:
            young_alumni = row[4] == "Yes"

            if "University" in row[3] and young_alumni:
                data.hoos += 1
            if "Tech" in row[3] and young_alumni:
                data.hokies += 1

        return data

    def get_mitzvah_memories(self) -> SubmittedData:
        """Gets mitzvah memory information."""
        sh = self.gc.open_by_key("1odvHzGY6O6buqlKSuFWx5WMfh0M2PGPCCJOVvXD8pko")
        rows = sh.sheet1.get_all_values()
        rows.pop(0)

        data = SubmittedData()
        for row in rows:
            alumni = row[4] == "Yes"

            if "University" in row[3] and alumni:
                data.hoos += 1
            if "Tech" in row[3] and alumni:
                data.hokies += 1

        return data

    # ---------- Data Update ---------- #

    def update_results(self):
        """Fetches all data sources and updates the results CSV."""
        print("📊 Updating alumni gatherings...")
        alumni_gatherings_score = self.get_alumni_gatherings()
        print("    ", alumni_gatherings_score)
        self.df.loc[0, "uva_alumni_gatherings"] = int(alumni_gatherings_score.hoos)
        self.df.loc[0, "vt_alumni_gatherings"] = int(alumni_gatherings_score.hokies)

        print("📸 Updating mitzvah memories...")
        mitzvah_memories_score = self.get_mitzvah_memories()
        print("    ", mitzvah_memories_score)
        self.df.loc[0, "uva_mitzvah_memories"] = int(mitzvah_memories_score.hoos)
        self.df.loc[0, "vt_mitzvah_memories"] = int(mitzvah_memories_score.hokies)

        # Uncomment if/when alumni memories are used
        # print("🎞️ Updating alumni memories...")
        # alumni_memories_score = self.get_alumni_memories()
        # self.df.loc[0, "alumniMemoriesUVA"] = int(alumni_memories_score.hoos)
        # self.df.loc[0, "alumniMemoriesTech"] = int(alumni_memories_score.hokies)

        # Save updated CSV
        self.df.to_csv(self.results_csv_path, index=False)
        print("✅ Results CSV updated successfully!")


# ---------- Script Entrypoint ---------- #

def main():
    updater = SubmissionUpdater(
        credentials_path="spreadsheet_credentials.json",
        results_csv_path="../public/assets/csv/results.csv",
    )
    updater.update_results()


if __name__ == "__main__":
    main()
