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
            "graduation year": 2025,
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

    # Check class year donors for 2025
    class_2025_count = calc._class_year_donors(calc.df, 2025)
    # Alex is Alumni + Current Student, grad_year 2025 => counts once
    assert class_2025_count == 1


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
