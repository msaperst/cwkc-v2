from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import gspread
import pandas as pd
import pytest

from scraper import getLglFormData as lgl


# ---------- parse_lgl_email ---------- #

def test_parse_lgl_email_success():
    # Sample HTML table
    html = """
    <table>
        <tr><td>Form title</td><td>Test Form</td></tr>
        <tr><td>Name</td><td>John Doe</td></tr>
    </table>
    """
    # Create a fake email message
    msg = EmailMessage()
    msg['From'] = "tester@example.com"
    msg.set_content("Plain text")  # plain part
    msg.add_alternative(html, subtype='html')

    raw_bytes = msg.as_bytes()

    sender, data = lgl.parse_lgl_email(raw_bytes)
    assert sender == "tester@example.com"
    assert data['Form title'] == "Test Form"
    assert data['Name'] == "John Doe"


def test_parse_lgl_email_no_html():
    msg = EmailMessage()
    msg['From'] = "tester@example.com"
    msg.set_content("Just plain text")
    raw_bytes = msg.as_bytes()

    with pytest.raises(ValueError, match="Email has no HTML part"):
        lgl.parse_lgl_email(raw_bytes)


def test_parse_lgl_email_no_table():
    msg = EmailMessage()
    msg['From'] = "tester@example.com"
    msg.add_alternative("<html><body><p>No table here</p></body></html>", subtype='html')
    raw_bytes = msg.as_bytes()

    with pytest.raises(ValueError, match="No table found in email"):
        lgl.parse_lgl_email(raw_bytes)


# ---------- update_google_sheet ---------- #

@patch("scraper.getLglFormData.gspread.service_account")
def test_update_google_sheet_creates_worksheet(mock_gspread):
    # Mock the sheet
    ws_mock = MagicMock()
    sh_mock = MagicMock()
    sh_mock.worksheet.side_effect = gspread.WorksheetNotFound  # force add_worksheet path
    sh_mock.add_worksheet.return_value = ws_mock
    mock_gspread.return_value.open_by_key.return_value = sh_mock

    # Sample normalized row
    row = {"name": "John", "total": "100"}
    lgl.update_google_sheet(mock_gspread.return_value, row)

    sh_mock.add_worksheet.assert_called_once()
    ws_mock.append_row.assert_called()  # headers + row appended


# ---------- update_local_csv ---------- #

@patch("scraper.getLglFormData.CalculateValues")
@patch("scraper.getLglFormData.pd.read_csv")
@patch("scraper.getLglFormData.pd.DataFrame.to_csv")
def test_update_local_csv(mock_to_csv, mock_read_csv, mock_calc):
    # Mock CSV dataframe
    df_mock = pd.DataFrame({"vt_total": [0], "uva_total": [0]})
    mock_read_csv.return_value = df_mock

    # Mock CalculateValues.calculate_all
    calc_instance = MagicMock()
    calc_instance.calculate_all.return_value = {
        "vt": {"total": 42},
        "uva": {"total": 99}
    }
    mock_calc.return_value = calc_instance

    lgl.update_local_csv()

    # Verify DataFrame updated
    assert df_mock.at[0, "vt_total"] == 42
    assert df_mock.at[0, "uva_total"] == 99
    mock_to_csv.assert_called_once()


# ---------- determine_source usage ---------- #

def test_normalize_row_with_source():
    # Use EmailParser with a simple dict
    parser = lgl.EmailParser()
    data = {"I am a/an": "Current Student", "Name - First Name": "Alice"}
    row = parser.normalize(data, lgl.determine_source("hillel at vt", "Front-End Form"))
    assert row["status"] == "Current Student"
    assert row["source"] == "vt-front"
