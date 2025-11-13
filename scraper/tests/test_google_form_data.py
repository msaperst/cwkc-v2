from unittest.mock import MagicMock

import pandas as pd
import pytest

from scraper import getGoogleFormData


# ---------- Helper Fixtures ---------- #

@pytest.fixture
def fake_df():
    # Mock dataframe similar to results.csv
    return pd.DataFrame([{
        "uva_alumni_gatherings": 0,
        "vt_alumni_gatherings": 0,
        "uva_mitzvah_memories": 0,
        "vt_mitzvah_memories": 0,
    }])


@pytest.fixture
def updater(monkeypatch, fake_df):
    # Patch gspread.service_account to return a mock client
    mock_gc = MagicMock()
    monkeypatch.setattr(getGoogleFormData.gspread, "service_account", lambda filename: mock_gc)

    # Patch pandas read_csv to return our fake dataframe
    monkeypatch.setattr(getGoogleFormData.pd, "read_csv", lambda path: fake_df.copy())
    # Patch to_csv to just return None
    monkeypatch.setattr(getGoogleFormData.pd.DataFrame, "to_csv", lambda self, path, index: None)

    return getGoogleFormData.SubmissionUpdater(
        credentials_path="fake.json",
        results_csv_path="fake.csv",
    )


# ---------- Test Data Retrieval Methods ---------- #

def test_get_alumni_gatherings(monkeypatch, updater):
    # Fake sheet data
    sheet_mock = MagicMock()
    sheet_mock.sheet1.get_all_values.return_value = [
        ["Header1", "Header2", "Header3", "Header4", "Header5"],
        ["", "", "Brody", "", "a,b,c,d"],  # enough people -> UVA
        ["", "", "Tech", "", "a,b,c,d"],  # enough people -> VT
        ["", "", "Brody", "", "a,b"]  # not enough people
    ]
    updater.gc.open_by_key.return_value = sheet_mock

    result = updater.get_alumni_gatherings()
    assert result.hoos == 1
    assert result.hokies == 1


def test_get_alumni_memories(monkeypatch, updater):
    # Create a fake Google Sheet
    sheet_mock = MagicMock()
    sheet_mock.sheet1.get_all_values.return_value = [
        ["Header1", "Header2", "Header3", "Header4", "Header5"],  # header
        ["", "", "", "University", "Yes"],  # counts as UVA
        ["", "", "", "Tech", "Yes"],  # counts as VT
        ["", "", "", "University", "No"],  # should be ignored
        ["", "", "", "Tech", "No"]  # should be ignored
    ]

    # Patch open_by_key to return the fake sheet
    updater.gc.open_by_key.return_value = sheet_mock

    # Call the method
    result = updater.get_alumni_memories()

    # Assert counts
    assert result.hoos == 1  # one University/young_alumni
    assert result.hokies == 1  # one Tech/young_alumni


def test_get_mitzvah_memories(monkeypatch, updater):
    sheet_mock = MagicMock()
    sheet_mock.sheet1.get_all_values.return_value = [
        ["Header1", "Header2", "Header3", "Header4", "Header5"],
        ["", "", "", "University", "Yes"],
        ["", "", "", "Tech", "Yes"],
        ["", "", "", "University", "No"]
    ]
    updater.gc.open_by_key.return_value = sheet_mock

    result = updater.get_mitzvah_memories()
    assert result.hoos == 1
    assert result.hokies == 1


def test_update_results(monkeypatch, updater):
    # Patch the three data methods
    monkeypatch.setattr(updater, "get_alumni_gatherings", lambda: getGoogleFormData.SubmittedData(hokies=2, hoos=3))
    monkeypatch.setattr(updater, "get_mitzvah_memories", lambda: getGoogleFormData.SubmittedData(hokies=5, hoos=7))

    updater.update_results()

    df = updater.df
    assert df.loc[0, "uva_alumni_gatherings"] == 3
    assert df.loc[0, "vt_alumni_gatherings"] == 2
    assert df.loc[0, "uva_mitzvah_memories"] == 7
    assert df.loc[0, "vt_mitzvah_memories"] == 5
