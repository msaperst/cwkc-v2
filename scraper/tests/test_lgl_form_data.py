from email.message import EmailMessage
from unittest.mock import MagicMock, patch

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

def test_update_google_sheet_uses_durable_submission_id():
    ledger = MagicMock()
    ledger.insert.return_value = True
    row = {"total amount": "100"}

    result = lgl.update_google_sheet(ledger, row, "synthetic-id")

    assert result is True
    ledger.insert.assert_called_once_with(row, "synthetic-id")


# ---------- update_local_csv ---------- #

@patch("scraper.getLglFormData.CalculateValues")
@patch("scraper.getLglFormData.pd.read_csv")
@patch("scraper.getLglFormData.pd.DataFrame.to_csv")
def test_update_local_csv(mock_to_csv, mock_read_csv, mock_calc, monkeypatch):
    monkeypatch.setattr(lgl, "SPREADSHEET_SHEET", "entries_2026")
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
    mock_calc.assert_called_once_with(
        spreadsheet_key=lgl.SPREADSHEET_KEY,
        worksheet_name="entries_2026",
    )

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
