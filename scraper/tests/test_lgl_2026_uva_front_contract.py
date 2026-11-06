"""2026 UVA public LGL notification contract, reconstructed with synthetic donor data.

The structure and option texts mirror the first real 2026 UVA public
notification. No identifying details, donation records or credentials are
stored in source control, and these tests never connect to IMAP or Sheets.
"""
from email.message import EmailMessage
from html import escape

import pandas as pd

from scraper.CalculateValues import CalculateValues
from scraper.EmailParser import EmailParser, determine_source
from scraper.donation_ledger import NORMALIZED_FIELDS
from scraper.getLglFormData import parse_lgl_email, validate_submission


UVA_FRONT_2026_FIELDS = [
    ("Form title", "14th Annual Commonwealth Kiddush Cup Front End Form"),
    ("Submission ID", "synthetic-2026-notification-id"),
    ("Submission Date", "2026-11-06 14:42:28 -0500"),
    ("Total Amount", "$5.00"),
    ("Amount - Details", "Amount: $5.00"),
    ("Amount - Quantity", "0"),
    ("Name - Prefix", ""),
    ("Name - First Name", "Sample"),
    ("Name - Last Name", "Donor"),
    ("Name - Suffix", ""),
    ("Email", "sample@example.invalid"),
    ("Phone", "555-010-2006"),
    ("Current Address - Address Line 1", "100 Example Way"),
    ("Current Address - Address Line 2", ""),
    ("Current Address - City", "Sampletown"),
    ("Current Address - State/Province", "AZ"),
    ("Current Address - ZIP/Postal Code", "00000"),
    ("Current Address - Country", ""),
    ("I am a/an", "Alum"),
    ("Grad Year", "2006"),
    ("Check all that apply", "This is my first gift to Hillel at UVA"),
    ("This gift is:", ""),
    ("Honoree", ""),
    ("Does your workplace match charitable giving?",
     "Yes! I'll go ahead and ask them"),
    ("Employer Name", "Example Employer"),
    ("Is Recurring", "false"),
]


def _synthetic_uva_notification():
    rows = "".join(
        f"<tr><td>{escape(field)}</td><td>{escape(value)}</td></tr>"
        for field, value in UVA_FRONT_2026_FIELDS
    )
    message = EmailMessage()
    message["From"] = (
        "Brody Jewish Center <lglforms-submissions@littlegreenlight.com>"
    )
    message["To"] = "synthetic-inbox@example.invalid"
    message.set_content("Synthetic LGL notification; no real financial gift")
    message.add_alternative(f"<html><body><table>{rows}</table></body></html>",
                            subtype="html")
    return message.as_bytes()


def _synthetic_uva_singlepart_qp_notification():
    """Match LGL's actual Content-Type/transfer encoding without using donor PII."""
    rows = "".join(
        f"<tr><td>{escape(field)}{' ' if field == 'Does your workplace match charitable giving?' else ''}</td>"
        f"<td>{escape(value)}</td></tr>"
        for field, value in UVA_FRONT_2026_FIELDS
    )
    message = EmailMessage()
    message["From"] = (
        "Brody Jewish Center <lglforms-submissions@littlegreenlight.com>"
    )
    message["To"] = (
        "manager@example.invalid, organizer@example.invalid, "
        "service@example.invalid"
    )
    message["Subject"] = (
        "New Submission: Donor -- 14th Annual Commonwealth Kiddush Cup "
        "Front End Form"
    )
    # The real LGL delivery was one text/html part, not multipart/alternative,
    # and used quoted-printable encoding with wrapped lines (= sequences).
    message.set_content(
        f"<p><table>{rows}</table></p>",
        subtype="html",
        charset="utf-8",
        cte="quoted-printable",
    )
    assert not message.is_multipart()
    assert message.get_content_type() == "text/html"
    assert message["Content-Transfer-Encoding"] == "quoted-printable"
    return message.as_bytes()


def test_real_2026_uva_mime_shape_single_html_quoted_printable():
    """A single-part quoted-printable LGL email must parse like multipart HTML."""
    sender, raw = parse_lgl_email(_synthetic_uva_singlepart_qp_notification())
    assert "Brody Jewish Center" in sender
    assert raw["Form title"] == "14th Annual Commonwealth Kiddush Cup Front End Form"
    assert raw["Does your workplace match charitable giving?"] == (
        "Yes! I'll go ahead and ask them"
    )
    normalized = EmailParser().normalize(
        raw, determine_source(sender, raw["Form title"])
    )
    validate_submission(raw, normalized)
    assert tuple(normalized) == NORMALIZED_FIELDS
    assert normalized["source"] == "uva-front"
    assert normalized["total amount"] == "5.0"
    assert normalized["status"] == "Alumni"
    assert normalized["first time giver"] == "true"
    assert normalized["work referral"] == "true"
    assert normalized["recurring payment"] == "false"


def _parse_and_normalize():
    sender, raw = parse_lgl_email(_synthetic_uva_notification())
    source = determine_source(sender, raw["Form title"])
    normalized = EmailParser().normalize(raw, source)
    validate_submission(raw, normalized)
    return raw, normalized


def test_2026_uva_front_real_labels_and_option_values_are_recognized():
    original, record = _parse_and_normalize()
    assert original["Form title"].startswith("14th Annual")
    assert tuple(record) == NORMALIZED_FIELDS
    assert record["source"] == "uva-front"
    assert record["total amount"] == "5.0"
    assert record["graduation year"] == "2006"
    assert record["status"] == "Alumni"
    assert record["first time giver"] == "true"
    assert record["work referral"] == "true"
    assert record["recurring payment"] == "false"
    assert record["anonymous donation"] == "false"


def test_uva_public_five_dollar_first_time_work_match_scores_independently():
    _, normalized = _parse_and_normalize()
    calc = CalculateValues.__new__(CalculateValues)
    calc.df = pd.DataFrame([{
        **normalized,
        "total amount": float(normalized["total amount"]),
        "recurring payment": False,
    }])
    scores = calc.calculate_all()
    uva = scores["uva"]
    assert uva["total_amount"] == 5
    assert uva["most_individual_donors"] == 1
    assert uva["most_first_time_donors"] == 1
    assert uva["most_alum_work_matched"] == 1
    assert uva["most_donors_class_2026"] == 0
    assert uva["most_gifts_over_1000"] == 0
    assert uva["most_alum_monthly_10_plus"] == 0
    assert scores["vt"]["total_amount"] == 0
