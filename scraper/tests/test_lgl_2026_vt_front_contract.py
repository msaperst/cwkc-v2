"""2026 VT public LGL notification contract, reconstructed with synthetic identities.

The 2026-11-06 original notification was delivered to the service mailbox.
The real LGL form repeats "Graduation Year" for alumni and related students;
that ambiguity must block ingestion rather than silently misclassify donors.
Nothing in this module reaches IMAP, LGL, Google Sheets, or payment services.
"""
from email.message import EmailMessage
from html import escape
from unittest.mock import MagicMock

import pandas as pd
import pytest

from scraper.CalculateValues import CalculateValues
from scraper.EmailParser import EmailParser, determine_source
from scraper.donation_ledger import NORMALIZED_FIELDS
from scraper.getLglFormData import (
    parse_lgl_email, process_messages, validate_submission,
)


VT_FRONT_2026_FIELDS = [
    ("Form title", "CWKC 2026 Donation Form"),
    ("Submission ID", "synthetic-2026-vt-public-id"),
    ("Submission Date", "2026-11-06 18:01:48 -0500"),
    ("Total Amount", "$5.00"),
    ("Amount - Details", "Amount: $5.00"),
    ("Amount - Quantity", "0"),
    ("Name - Prefix", ""),
    ("Name - First Name", "Example"),
    ("Name - Last Name", "Donor"),
    ("Name - Suffix", ""),
    ("Email", "vt-donor@example.invalid"),
    ("Phone", "5550102028"),
    ("Current Address - Address Line 1", "100 Sample Street"),
    ("Current Address - Address Line 2", ""),
    ("Current Address - City", "Exampleville"),
    ("Current Address - State/Province", "AZ"),
    ("Current Address - ZIP/Postal Code", "00000"),
    ("Current Address - Country", "United States"),
    ("I am a/an...", "Current Parent||Alumni"),
    ("Intended Graduation Year", ""),
    ("Graduation Year", "2006"),  # donor's alumni year
    ("Graduation Year", "2028"),  # related student's year
    ("What Is the Name of Your Student? - Prefix", ""),
    ("What Is the Name of Your Student? - First Name", "Student"),
    ("What Is the Name of Your Student? - Last Name", "Example"),
    ("What Is the Name of Your Student? - Suffix", ""),
    ("What Is Their Email?", "vt-student@example.invalid"),
    ("What Is Their Phone Number?", "5550100000"),
    ("Check All That Apply:",
     "Please don't list my name. I would like to remain anonymous."),
    ("Does Your Workplace Match Charitable Giving?",
     "I'm not sure, can you look into it for me?"),
    ("Employer Name:", "Example Employer"),
    ("Matching Grant", "Yes!"),
    ("Is Recurring", "false"),
]


def _message(fields=VT_FRONT_2026_FIELDS):
    """Generate the real single-part QP HTML shape with fake donor details."""
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in fields
    )
    message = EmailMessage()
    message["From"] = "Hillel at VT <lglforms-submissions@littlegreenlight.com>"
    message["To"] = (
        "office@example.invalid, organizer@example.invalid, "
        "service@example.invalid"
    )
    message["Subject"] = "New Submission: Donor -- CWKC 2026 Donation Form"
    message.set_content(
        f"<p><table>{rows}</table></p>",
        subtype="html", charset="utf-8", cte="quoted-printable",
    )
    assert not message.is_multipart()
    assert message.get_content_type() == "text/html"
    assert message["Content-Transfer-Encoding"] == "quoted-printable"
    return message.as_bytes()


def _distinct_year_labels():
    """The safe form change: make each same-named year self-describing."""
    return [
        ("Alumni Graduation Year", value) if label == "Graduation Year"
        and value == "2006"
        else ("Related Student Graduation Year", value)
        if label == "Graduation Year" and value == "2028"
        else (label, value)
        for label, value in VT_FRONT_2026_FIELDS
    ]


def _normalized(fields):
    sender, raw = parse_lgl_email(_message(fields))
    record = EmailParser().normalize(
        raw, determine_source(sender, raw["Form title"])
    )
    validate_submission(raw, record)
    assert tuple(record) == NORMALIZED_FIELDS
    return raw, record


@pytest.mark.parametrize("same_year", [False, True])
def test_real_vt_duplicate_graduation_years_fail_closed(same_year):
    fields = [
        (label, "2006" if same_year and label == "Graduation Year" else value)
        for label, value in VT_FRONT_2026_FIELDS
    ]
    with pytest.raises(ValueError, match="Repeated graduation-year field is ambiguous"):
        parse_lgl_email(_message(fields))


def test_unparseable_vt_email_stays_unread_and_does_not_write_to_sheet():
    server, ledger = MagicMock(), MagicMock()
    server.fetch.return_value = {17: {b"BODY[]": _message()}}
    ledger.known.return_value = False
    result = process_messages(server, [17], ledger)
    assert result == {"new": 0, "already_stored": 0, "pending": 0, "failed": 1}
    server.fetch.assert_called_once_with(17, ["BODY.PEEK[]"])
    server.add_flags.assert_not_called()
    ledger.insert.assert_not_called()


def test_safe_distinct_year_labels_normalize_multiaffiliation_and_vt_answers():
    raw, record = _normalized(_distinct_year_labels())
    assert raw["I am a/an..."] == "Current Parent||Alumni"
    assert raw["Alumni Graduation Year"] == "2006"
    assert raw["Related Student Graduation Year"] == "2028"
    assert record["source"] == "vt-front"
    assert record["total amount"] == "5.0"
    assert record["status"] == "Alumni, Current Parent"
    assert record["graduation year"] == "2006"
    assert record["anonymous donation"] == "true"
    assert record["work referral"] == "true"
    assert record["first time giver"] == "false"
    assert record["recurring payment"] == "false"


def test_vt_2026_one_time_anonymous_parent_alum_scores_without_double_count():
    _, record = _normalized(_distinct_year_labels())
    calculator = CalculateValues.__new__(CalculateValues)
    calculator.df = pd.DataFrame([{
        **record,
        "total amount": float(record["total amount"]),
        "recurring payment": False,
    }])
    scores = calculator.calculate_all()
    vt = scores["vt"]
    assert vt["total_amount"] == 5
    assert vt["most_individual_donors"] == 1
    assert vt["most_money_families"] == 5
    assert vt["most_alum_work_matched"] == 1
    assert vt["donor_names"] == ""
    assert vt["most_first_time_donors"] == 0
    assert vt["most_donors_class_2026"] == 0
    assert vt["most_gifts_over_1000"] == 0
    assert vt["most_alum_monthly_10_plus"] == 0
    assert scores["uva"]["total_amount"] == 0


def test_matching_grant_yes_alone_is_not_workplace_referral():
    fields = [
        (label, "This does not apply to me")
        if label == "Does Your Workplace Match Charitable Giving?"
        else (label, value)
        for label, value in _distinct_year_labels()
    ]
    _, record = _normalized(fields)
    assert record["work referral"] == "false"
    assert record["total amount"] == "5.0"


@pytest.mark.parametrize("student_option", [
    "Undergraduate Student", "Graduate Student",
])
def test_vt_undergraduate_and_grad_students_map_to_current_student(student_option):
    fields = [
        (label, student_option) if label == "I am a/an..." else (label, value)
        for label, value in _distinct_year_labels()
    ]
    _, record = _normalized(fields)
    assert record["status"] == "Current Student"


def test_standalone_vt_alumni_graduation_year_is_parsed():
    fields = [
        (label, value) for label, value in VT_FRONT_2026_FIELDS
        if not (label == "Graduation Year" and value == "2028")
    ]
    _, record = _normalized(fields)
    assert record["graduation year"] == "2006"


def test_direct_normalizer_fails_on_conflicting_case_variants():
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        EmailParser().normalize(
            {"Total Amount": "$5.00", "total amount:": "$10.00"},
            "vt-front",
        )


def test_vt_public_first_time_checkbox_is_recognized_after_label_canonicalization():
    fields = [
        (label, "This is my first gift to Hillel at VT")
        if label == "Check All That Apply:" else (label, value)
        for label, value in _distinct_year_labels()
    ]
    _, record = _normalized(fields)
    assert record["first time giver"] == "true"
    assert record["anonymous donation"] == "false"
