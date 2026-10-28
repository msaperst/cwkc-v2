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



def _email_with_rows(rows):
    """Only fabricated field/value pairs; no live submissions or accounts."""
    message = EmailMessage()
    message["From"] = "Hillel at VT <lglforms-submissions@littlegreenlight.com>"
    message.set_content("Synthetic form message")
    table = "<table>" + "".join(
        f"<tr><td>{field}</td><td>{value}</td></tr>"
        for field, value in rows
    ) + "</table>"
    message.add_alternative(table, subtype="html")
    return message.as_bytes()


@pytest.mark.parametrize(("rows", "error"), [
    (
        [("Graduation Year", "2026"), ("Graduation Year", "2025")],
        "Repeated graduation-year field is ambiguous",
    ),
    (
        [("Graduation Year", "2026"), ("Graduation Year", "2026")],
        "Repeated graduation-year field is ambiguous",
    ),
    (
        [("Graduation Year", "2026"), (" graduation  YEAR :", "2025")],
        "Repeated graduation-year field is ambiguous",
    ),
    (
        [("Intended Graduation Year", "2026"), ("Intended Graduation Year", "")],
        "Repeated graduation-year field is ambiguous",
    ),
    (
        [("Total Amount", "$25.00"), ("Total Amount", "$50.00")],
        "Conflicting duplicate LGL form field",
    ),
    (
        [("I am a/an", "Alumni"), ("I am a/an", "Current Parent")],
        "Conflicting duplicate LGL form field",
    ),
    (
        [("Check all that apply:", "Option A"), ("check all that apply", "Option B")],
        "Conflicting duplicate LGL form field",
    ),
])
def test_parse_lgl_email_rejects_ambiguous_repeated_fields(rows, error):
    raw = _email_with_rows(rows)
    with pytest.raises(ValueError, match=error):
        lgl.parse_lgl_email(raw)


def test_parse_lgl_email_accepts_identical_non_year_duplicates():
    raw = _email_with_rows([
        ("Form title", "CWKC Donation"),
        ("Form TITLE:", "CWKC Donation"),
        ("Total Amount", "$25.00"),
        ("Total Amount", "$25.00"),
    ])
    _, data = lgl.parse_lgl_email(raw)
    assert data == {"Form title": "CWKC Donation", "Total Amount": "$25.00"}


def test_parse_lgl_email_preserves_different_graduation_year_questions():
    raw = _email_with_rows([
        ("Alumni Graduation Year", "2026"),
        ("Related Student Graduation Year", "2025"),
        ("Intended Graduation Year", "2027"),
    ])
    _, data = lgl.parse_lgl_email(raw)
    assert data["Alumni Graduation Year"] == "2026"
    assert data["Related Student Graduation Year"] == "2025"
    assert data["Intended Graduation Year"] == "2027"


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


def test_lgl_step_summary_contains_only_synthetic_counts(monkeypatch, tmp_path):
    report = tmp_path / "github-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(report))
    ledger = MagicMock()
    ledger.ids = {"synthetic-hash"}
    ledger.legacy_rows = 0
    values = {"new": 1, "already_stored": 2, "pending": 0, "failed": 1}

    lgl.write_processing_summary([11, 7, 9, 3], values, ledger)

    body = report.read_text(encoding="utf-8")
    assert "### CWKC LGL processing\n" in body
    assert "| Matching unread notifications at start | 4 |" in body
    assert "| New donation rows persisted | 1 |" in body
    assert "| Failed notifications (left unread) | 1 |" in body
    assert "| Highest matched mailbox UID (not a processed watermark) | 11 |" in body
    assert "| Identified normalized Sheet rows | 1 |" in body
    assert "synthetic-hash" not in body
    assert "donor" not in body.lower()


def test_lgl_step_summary_is_optional_and_handles_empty_mail(monkeypatch, tmp_path):
    report = tmp_path / "summary.md"
    ledger = MagicMock()
    ledger.ids = set()
    ledger.legacy_rows = 0
    values = {"new": 0, "already_stored": 0, "pending": 0, "failed": 0}
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    lgl.write_processing_summary([], values, ledger)
    assert not report.exists()

    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(report))
    lgl.write_processing_summary([], values, ledger)
    assert "| Matching unread notifications at start | 0 |" in report.read_text()
    assert "| Highest matched mailbox UID (not a processed watermark) | None |" in report.read_text()
