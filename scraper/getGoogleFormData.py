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
            # check number of attendees (3 commas = 4 names)
            enough_people = row[4].count(",") >= 3

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
        self.df.loc[0, "alumniGatheringsUVA"] = int(alumni_gatherings_score.hoos)
        self.df.loc[0, "alumniGatheringsTech"] = int(alumni_gatherings_score.hokies)

        print("📸 Updating mitzvah memories...")
        mitzvah_memories_score = self.get_mitzvah_memories()
        self.df.loc[0, "mitzvahMemoriesUVA"] = int(mitzvah_memories_score.hoos)
        self.df.loc[0, "mitzvahMemoriesTech"] = int(mitzvah_memories_score.hokies)

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
