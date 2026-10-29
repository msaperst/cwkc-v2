# tests/test_calculate_values_offline.py
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from scraper.CalculateValues import CalculateValues


# -------------------- Fixtures --------------------

@pytest.fixture
def sample_df():
    """Sample data with multiple edge cases to test metrics calculations."""
    return pd.DataFrame([
        {
            "source": "uva-front",
            "total amount": 100,
            "recurring payment": "False",
            "first name": "Alex",
            "last name": "Green",
            "phone number": "555",
            "anonymous donation": "false",
            "first time giver": "true",
            "graduation year": 2026,
            "status": "Alumni, Current Student",
            "work referral": "false",
        },
        {
            "source": "vt-back",
            "total amount": 20,
            "recurring payment": "True",
            "first name": "Sam",
            "last name": "Blue",
            "phone number": "777",
            "anonymous donation": "true",
            "first time giver": "false",
            "graduation year": 2023,
            "status": "Current Parent",
            "work referral": "true",
        },
        {
            "source": "uva-front",
            "total amount": 50,
            "recurring payment": "True",
            "first name": "Jordan",
            "last name": "Smith",
            "phone number": "999",
            "anonymous donation": "false",
            "first time giver": "true",
            "graduation year": 2024,
            "status": "Parent of Alumni, Current Grandparent",
            "work referral": "false",
        }
    ])


@pytest.fixture
def mock_gspread(sample_df):
    """Patch gspread to return sample data instead of connecting to Google Sheets."""
    with patch("gspread.service_account") as mock_service:
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = sample_df.to_dict(orient="records")
        mock_sh = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_service.return_value.open_by_key.return_value = mock_sh
        yield mock_service


@pytest.fixture
def calc(mock_gspread):
    """Create a CalculateValues instance with the mocked spreadsheet."""
    return CalculateValues(spreadsheet_key="dummy_key")


# -------------------- Tests --------------------

def test_total_raised_includes_recurring(calc):
    """Recurring gifts should count as 12x the total amount."""
    total = calc._total_raised(calc.df)
    # totals: 100 + (20*12) + (50*12) = 100 + 240 + 600 = 940
    assert total == 940


def test_unique_donors_counts_by_phone(calc):
    """Unique donors should be counted by phone number."""
    count = calc._unique_donors_count(calc.df)
    # Phones: 555, 777, 999
    assert count == 3


def test_status_based_metrics_counts_multi_status(calc):
    """Rows with multiple statuses should count for all relevant metrics."""
    # Convert 'status' strings to list like production code does
    calc.df['status_list'] = calc.df['status'].fillna('').apply(
        lambda x: [s.strip() for s in str(x).split(',') if s.strip()]
    )
    # Check money by family statuses
    family_money = calc._money_by_statuses(calc.df, calc.FAMILY_STATUSES)
    # Sam(20*12=240) + Jordan(50*12=600) = 840
    assert family_money == 840

    # Check money by grandparents (Current Grandparent)
    grandparent_money = calc._money_by_statuses(calc.df, calc.GRANDPARENT_STATUS)
    # Only Jordan qualifies: 50*12=600
    assert grandparent_money == 600

    # Class of 2026 counts alumni even when they hold other affiliations.
    class_2026_count = calc._class_year_donors(calc.df, 2026)
    assert class_2026_count == 1


def test_zero_metrics_for_empty_df(calc):
    """Empty data should return 0 metrics."""
    empty_df = pd.DataFrame(columns=calc.df.columns)
    with patch.object(CalculateValues, "_load_data", return_value=empty_df):
        empty_calc = CalculateValues(spreadsheet_key="dummy")
        metrics = empty_calc._calculate_school_metrics("uva")
        for k, v in metrics.items():
            if k == 'donor_names':
                assert v == ''
            else:
                assert v == 0


def test_calculate_all_returns_metrics(calc):
    """calculate_all() returns metrics for both UVA and VT."""
    metrics = calc.calculate_all()
    assert "uva" in metrics
    assert "vt" in metrics
    # Basic sanity checks
    assert metrics['uva']['total_amount'] > 0
    assert metrics['vt']['total_amount'] > 0


def test_calculator_reads_only_configured_season_tab():
    """Keep prior-season gifts intact but exclude them from 2026 totals."""
    old_row = {
        "source": "uva-front",
        "total amount": 9999,
        "recurring payment": "false",
        "first name": "Archived",
        "last name": "Synthetic",
        "phone number": "old",
        "anonymous donation": "false",
        "first time giver": "false",
        "graduation year": 2025,
        "status": "Alumni",
        "work referral": "false",
    }
    new_row = {
        **old_row,
        "source": "vt-front",
        "total amount": 25,
        "first name": "Current",
        "phone number": "new",
        "graduation year": 2026,
    }

    with patch("gspread.service_account") as mock_service:
        spreadsheet = mock_service.return_value.open_by_key.return_value
        worksheets = {
            "entries": MagicMock(),
            "entries_2026": MagicMock(),
        }
        worksheets["entries"].get_all_records.return_value = [old_row]
        worksheets["entries_2026"].get_all_records.return_value = [new_row]
        spreadsheet.worksheet.side_effect = worksheets.__getitem__

        calculator = CalculateValues(
            spreadsheet_key="synthetic-key", worksheet_name="entries_2026",
        )
        totals = calculator.calculate_all()

    spreadsheet.worksheet.assert_called_once_with("entries_2026")
    assert totals["uva"]["total_amount"] == 0
    assert totals["vt"]["total_amount"] == 25
    assert worksheets["entries"].get_all_records.call_count == 0
    worksheets["entries_2026"].get_all_records.assert_called_once_with()


@pytest.mark.parametrize("grad_year,status,expected", [
    (2026, "Alumni", 1),
    ("2026", "Alumni, Current Parent", 1),
    (2026, "Current Student", 0),
    (2026, "Current Parent, Current Grandparent", 0),
    (2025, "Alumni", 0),
    ("unknown", "Alumni", 0),
])
def test_class_of_2026_counts_only_alumni_grad_year(
    calc, grad_year, status, expected,
):
    """Related students' graduation years are not donor-alumni class years."""
    calc.df = pd.DataFrame([{
        "source": "uva-front",
        "total amount": 10,
        "recurring payment": False,
        "first name": "Fixture",
        "last name": "Donor",
        "phone number": "fixture-phone",
        "anonymous donation": "false",
        "first time giver": "false",
        "graduation year": grad_year,
        "status": status,
        "work referral": "false",
    }])
    scores = calc._calculate_school_metrics("uva")
    assert scores["most_donors_class_2026"] == expected
    assert "most_undergraduates" not in scores
    assert "most_donors_class_2025" not in scores


def test_multiple_qualifying_categories_share_one_gift_and_donor(calc):
    """Alumni/grandparents earn category credit without duplicate dollars."""
    calc.df = pd.DataFrame([{
        "source": "vt-front",
        "total amount": 120,
        "recurring payment": False,
        "first name": "Synthetic",
        "last name": "Person",
        "phone number": "fixture-unique-1",
        "anonymous donation": "false",
        "first time giver": "true",
        "graduation year": 2026,
        "status": "Alumni, Current Parent, Current Grandparent",
        "work referral": "true",
    }])
    totals = calc.calculate_all()
    vt = totals["vt"]
    assert vt["total_amount"] == 120
    assert vt["most_individual_donors"] == 1
    assert vt["most_first_time_donors"] == 1
    assert vt["most_donors_class_2026"] == 1
    assert vt["most_money_families"] == 120
    assert vt["most_money_grandparents_current_students"] == 120
    assert vt["most_alum_work_matched"] == 1
    assert totals["uva"]["total_amount"] == 0
    assert "most_undergraduates" not in vt


def test_zero_and_populated_scores_have_identical_keys(calc):
    """An empty school must still provide every displayed 2026 metric."""
    scores = calc.calculate_all()
    assert scores["uva"].keys() == scores["vt"].keys()
    assert "most_donors_class_2026" in scores["uva"]
    assert "most_undergraduates" not in scores["uva"]
