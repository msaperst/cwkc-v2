"""Contract tests for finalized 2026 gathering and Hanukkah response Sheets.

All rows and email/photo identifiers here are synthetic. No Google API is called.
"""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from scraper import getGoogleFormData as forms


GATHERING_HEADER = [
    "Timestamp", "Name", "Which school are you supporting? ",
    "Affiliation",
    "Who was in attendance at your event? Please include full names and affiliations/class years wherever possible ",
    "Where was your event?", "Please submit photos of your event! ",
]
HANUKKAH_HEADER = [
    "Timestamp", "Name", "Non-school affiliated email ",
    "Which school are you supporting?",
    "Are you an alumni that graduated in the past 15 years, or a parent of one? (If yes, this'll count towards a CWKC point!)",
    "Graduation Year (if applicable) ", "Submit your photo here! ",
    "PHOTO RELEASE: The CWKC website this year is featuring the photos submitted through this form to celebrate our communities! Please let us know if you are comfortable with having your photo shared. ",
]
DATE = "11/06/2026 10:25:00"


def gathering(school="Brody", host="Alice Example", people="Bob, Carol, Dave",
              venue="Coffee Shop", photo="fixture-photo", date=DATE):
    return [date, host, school, "Alumni", people, venue, photo]


def hanukkah(school="Tech", name="Person One", email="one@example.invalid",
             eligible="Yes", consent="No", photo="fixture-photo", date=DATE):
    return [date, name, email, school, eligible, "2016", photo, consent]


@pytest.fixture
def harness(monkeypatch, tmp_path):
    csv = tmp_path / "results.csv"
    pd.DataFrame([{
        "uva_alumni_gatherings": 0, "vt_alumni_gatherings": 0,
        "uva_hanukkah_photos": 0, "vt_hanukkah_photos": 0,
        "uva_donor_names": "leave-unmodified",
    }]).to_csv(csv, index=False)
    gathering_ws = MagicMock()
    gathering_ws.get_all_values.return_value = [GATHERING_HEADER]
    photo_ws = MagicMock()
    photo_ws.get_all_values.return_value = [HANUKKAH_HEADER]

    def open_by_key(key):
        sheet = MagicMock()
        sheet.worksheet.return_value = (
            gathering_ws if key == forms.GATHERING_SHEET_ID else photo_ws
        )
        if key not in (forms.GATHERING_SHEET_ID, forms.HANUKKAH_SHEET_ID):
            raise AssertionError("Unexpected or historical response workbook")
        return sheet

    client = MagicMock()
    client.open_by_key.side_effect = open_by_key
    monkeypatch.setattr(forms.gspread, "service_account", lambda filename: client)
    updater = forms.SubmissionUpdater("fake-credentials.json", str(csv), season_year=2026)
    return updater, gathering_ws, photo_ws, csv, client


def test_reads_only_current_response_tab_and_preserves_unrelated_csv_fields(harness):
    updater, gatherings, photos, csv, client = harness
    gatherings.get_all_values.return_value += [gathering()]
    photos.get_all_values.return_value += [hanukkah()]
    updater.update_results()

    output = pd.read_csv(csv).iloc[0]
    assert output["uva_alumni_gatherings"] == 1
    assert output["vt_alumni_gatherings"] == 0
    assert output["uva_hanukkah_photos"] == 0
    assert output["vt_hanukkah_photos"] == 1
    assert output["uva_donor_names"] == "leave-unmodified"
    assert client.open_by_key.call_count == 2


def test_dry_run_reads_both_sources_but_does_not_write_csv(harness, capsys):
    updater, gatherings, photos, csv, _ = harness
    gatherings.get_all_values.return_value += [gathering()]
    photos.get_all_values.return_value += [hanukkah(consent="No")]
    before = csv.read_bytes()

    updater.update_results(dry_run=True)

    assert csv.read_bytes() == before
    output = capsys.readouterr().out
    assert "Gatherings: UVA=1, VT=0" in output
    assert "Hanukkah submitters: UVA=0, VT=1" in output
    assert "Person One" not in output
    assert "one@example.invalid" not in output


@pytest.mark.parametrize("consent", ["Yes", "No", "", "I do not consent"])
def test_photo_consent_does_not_affect_eligible_scoring(harness, consent):
    updater, _, photos, _, _ = harness
    photos.get_all_values.return_value += [hanukkah(consent=consent)]
    counts = updater.get_hanukkah_photos()
    assert counts.hokies == 1
    assert counts.hoos == 0


def test_duplicate_photo_submissions_count_once_even_if_release_changes(harness):
    updater, _, photos, _, _ = harness
    photos.get_all_values.return_value += [
        hanukkah(name="Alumnus", email="one@example.invalid", consent="No"),
        hanukkah(name="  ALUMNUS  ", email="other@example.invalid", consent="Yes"),
        hanukkah(name="Another Person", email="ONE@example.invalid", consent="Yes"),
        hanukkah(name="Person Two", email="two@example.invalid", consent="Yes"),
        hanukkah(school="Brody", name="UVA Person", email="uva@example.invalid"),
    ]
    scores = updater.get_hanukkah_photos()
    assert scores.hokies == 2
    assert scores.hoos == 1


def test_photos_ignore_no_eligibility_missing_upload_and_old_year(harness):
    updater, _, photos, _, _ = harness
    photos.get_all_values.return_value += [
        hanukkah(eligible="No"),
        hanukkah(name="No Photo", email="no@example.invalid", photo=""),
        hanukkah(name="Old Entry", email="old@example.invalid",
                 date="12/05/2025 10:00:00"),
        hanukkah(school="University of Virginia", name="Eligible Parent",
                 email="parent@example.invalid", eligible="Yes",
                 consent="No"),
    ]
    scores = updater.get_hanukkah_photos()
    # The current finalized Form's Yes option includes parents of alumni.
    assert scores.hoos == 1
    assert scores.hokies == 0


@pytest.mark.parametrize("bad_row,error", [
    (hanukkah(eligible="Maybe"), "eligibility"),
    (hanukkah(school="Undecided"), "Unrecognized school"),
    (hanukkah(name="", email=""), "participant identity"),
    (hanukkah(date="not a date"), "timestamp"),
])
def test_invalid_photo_response_fails_closed(harness, bad_row, error):
    updater, _, photos, _, _ = harness
    photos.get_all_values.return_value += [bad_row]
    with pytest.raises(ValueError, match=error):
        updater.get_hanukkah_photos()


@pytest.mark.parametrize("bad_header", [
    HANUKKAH_HEADER[:4] + HANUKKAH_HEADER[5:],  # missing eligibility
    HANUKKAH_HEADER + [HANUKKAH_HEADER[4]],     # duplicated eligibility
    HANUKKAH_HEADER[:7],                        # missing photo-release column
])
def test_renamed_missing_or_duplicate_photo_header_rejected(harness, bad_header):
    updater, _, photos, _, _ = harness
    photos.get_all_values.return_value = [bad_header]
    with pytest.raises(ValueError, match="missing or ambiguous"):
        updater.get_hanukkah_photos()


def test_in_person_gatherings_include_host_and_require_four_unique_people(harness):
    updater, gatherings, _, _, _ = harness
    gatherings.get_all_values.return_value += [
        gathering(),  # Host Alice + 3 people
        gathering(host="Ed", people="Ed, Frank, Gail, Harry", school="Tech",
                  venue="Library", date="11/07/2026 10:25:00"),
        gathering(host="Alice", people="Alice, Bob, Carol"),  # 3 distinct
        gathering(host="Zoe", people="A, B, C", venue="Virtual Zoom"),
        gathering(host="Wes", people="A, B, C", photo=""),  # no proof photo
        gathering(host="Prior", people="A, B, C", date="11/07/2025 12:00:00"),
    ]
    counts = updater.get_alumni_gatherings()
    assert counts.hoos == 1
    assert counts.hokies == 1


def test_duplicate_identical_gathering_row_is_not_counted_twice(harness):
    updater, gatherings, _, _, _ = harness
    row = gathering()
    gatherings.get_all_values.return_value += [row, row[:]]
    assert updater.get_alumni_gatherings().hoos == 1


@pytest.mark.parametrize("bad_header", [
    GATHERING_HEADER[:4] + GATHERING_HEADER[5:],
    GATHERING_HEADER + [GATHERING_HEADER[4]],
])
def test_gathering_header_mismatch_fails_closed(harness, bad_header):
    updater, gatherings, _, _, _ = harness
    gatherings.get_all_values.return_value = [bad_header]
    with pytest.raises(ValueError, match="missing or ambiguous"):
        updater.get_alumni_gatherings()


def test_second_sheet_failure_prevents_partial_csv_write(harness):
    updater, gatherings, photos, csv, _ = harness
    gatherings.get_all_values.return_value += [gathering()]
    photos.get_all_values.return_value = [["Unrelated", "changed header"]]
    before = csv.read_bytes()
    with pytest.raises(ValueError, match="missing or ambiguous"):
        updater.update_results()
    assert csv.read_bytes() == before


def test_empty_sheets_score_zero_without_crashing(harness):
    updater, _, _, csv, _ = harness
    updater.update_results()
    row = pd.read_csv(csv).iloc[0]
    for field in ("uva_alumni_gatherings", "vt_alumni_gatherings",
                  "uva_hanukkah_photos", "vt_hanukkah_photos"):
        assert row[field] == 0


def test_results_csv_missing_new_photo_column_rejected(harness):
    updater, _, _, csv, _ = harness
    updater.df = updater.df.drop(columns=["uva_hanukkah_photos"])
    before = csv.read_bytes()
    with pytest.raises(ValueError, match="2026 participation schema"):
        updater.update_results()
    assert csv.read_bytes() == before
