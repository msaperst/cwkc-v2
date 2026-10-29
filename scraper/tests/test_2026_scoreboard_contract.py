"""Static 2026 scoring contract: browser rows, Python and CSV stay aligned."""
import csv
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.CalculateValues import CalculateValues

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "public" / "index.html"
RESULTS = ROOT / "public" / "assets" / "csv" / "results.csv"

RETIRED = (
    "most_undergraduates",
    "most_donors_class_2025",
    "mitzvah_memories",
)


def score_rows():
    soup = BeautifulSoup(SITE.read_text(encoding="utf-8"), "html.parser")
    return soup.select("#score-areas [data-points]")


def test_2026_scoreboard_has_15_points_and_no_retired_categories():
    rows = score_rows()
    assert len(rows) == 12
    assert sum(int(row["data-points"]) for row in rows) == 15
    ids = {row["id"] for row in rows}
    assert "most_donors_class_2026" in ids
    assert "hanukkah_photos" in ids
    for category in RETIRED:
        assert category not in ids
    assert len(ids) == len(rows)


def test_all_score_rows_are_backed_by_a_pair_of_csv_columns():
    with RESULTS.open(newline="", encoding="utf-8") as infile:
        records = list(csv.DictReader(infile))
    assert len(records) == 1
    headers = set(records[0])
    for row in score_rows():
        category = row["id"]
        for school in ("uva", "vt"):
            field = f"{school}_{category}"
            assert field in headers
            assert row.select_one(f"#{field}") is not None

    for retired in RETIRED:
        assert not any(retired in field for field in headers)
    # Keep donor-name columns for the existing ticker, and do not expose
    # a previous year's participation metric in the public data.
    assert {"uva_donor_names", "vt_donor_names"} <= headers


def test_photo_row_uses_current_form_and_no_bnai_photo_link():
    html = SITE.read_text(encoding="utf-8")
    photo = next(row for row in score_rows() if row["id"] == "hanukkah_photos")
    link = photo.select_one("a.enable-during-contest")
    assert link is not None
    assert link["href"] == (
        "https://docs.google.com/forms/d/e/"
        "1FAIpQLSeX0-H3rkiAXy3xpdOYIDuAEYM8BI7tgmgBrPFIryS4Q7_Jbg/viewform"
    )
    assert "Hanukkah" in link.get_text()
    assert "B’nai Mitzvah Photos" not in html
    assert "Most Undergraduates Who Donate" not in html


def test_python_calculator_metric_keys_match_2026_csv_donation_contract():
    # Avoid Google API calls: inspect zero-case metric schema via an
    # uninitialized calculator object with an empty normalized DataFrame.
    import pandas as pd

    calculator = CalculateValues.__new__(CalculateValues)
    calculator.df = pd.DataFrame({
        "source": pd.Series(dtype="str"),
        "total amount": pd.Series(dtype="float"),
        "recurring payment": pd.Series(dtype="bool"),
        "status": pd.Series(dtype="str"),
    })
    metric_keys = set(calculator.calculate_all()["uva"])
    csv_fields = RESULTS.read_text(encoding="utf-8").splitlines()[0].split(",")
    for school in ("uva", "vt"):
        assert {f"{school}_{metric}" for metric in metric_keys} <= set(csv_fields)
