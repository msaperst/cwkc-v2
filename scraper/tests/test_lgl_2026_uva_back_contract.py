"""UVA 2026 LGL backend contract reconstructed with invented donor information.

Exact form labels and selected *types* of answers are derived from the
finalized form's November 6 notification. No real names, addresses,
phone numbers, submission IDs or financial records are checked in.
"""
from email.message import EmailMessage
from html import escape

import pandas as pd
import pytest

from scraper.CalculateValues import CalculateValues
from scraper.EmailParser import EmailParser, determine_source
from scraper.donation_ledger import NORMALIZED_FIELDS
from scraper.getLglFormData import parse_lgl_email, validate_submission


UVA_BACK_2026_FIELDS = [
    ("Form title", "14th Annual Commonwealth Kiddush Cup Back-end Form"),
    ("Submission ID", "synthetic-uva-back-id"),
    ("Submission Date", "2026-11-06 15:21:30 -0500"),
    ("Gift amount", "0.01"),
    ("Is this a monthly gift?", "Yes"),
    ("Passthrough from", "Facebook"),
    ("Check number", ""),
    ("Other", ""),
    ("Transaction details", "Gift in hand"),
    ("Gift notes", "synthetic test record"),
    ("Name - Prefix", ""),
    ("Name - First Name", "Sample"),
    ("Name - Last Name", "Donor"),
    ("Name - Suffix", ""),
    ("Email", "sample@example.invalid"),
    ("Phone", "5550102006"),
    ("Address - Address Line 1", "100 Example Road"),
    ("Address - Address Line 2", ""),
    ("Address - City", "Sampletown"),
    ("Address - State/Province", "AZ"),
    ("Address - ZIP/Postal Code", "00000"),
    ("Address - Country", ""),
    ("Donor is a/n...", "Parent of an Alum"),
    ("Grad Year", "2016"),
    ("Is this gift being matched by workplace?", "No"),
    ("Check all that apply", "Donor asking to match gift"),
    ("This gift is:", "In Honor Of"),
    ("Honoree", ""),
    ("Is Recurring", "false"),
]


def _backend_mime(fields=UVA_BACK_2026_FIELDS):
    rows = "".join(
        f"<tr><td>{escape(field)}</td><td>{escape(value)}</td></tr>"
        for field, value in fields
    )
    message = EmailMessage()
    message["From"] = (
        "Brody Jewish Center <lglforms-submissions@littlegreenlight.com>"
    )
    message["To"] = "synthetic-operator@example.invalid"
    message["Subject"] = (
        "New Submission: Back End -- "
        "14th Annual Commonwealth Kiddush Cup Back-end Form"
    )
    message.set_content(
        f"<p><table>{rows}</table></p>",
        subtype="html",
        charset="utf-8",
        cte="quoted-printable",
    )
    assert message.get_content_type() == "text/html"
    assert not message.is_multipart()
    assert message["Content-Transfer-Encoding"] == "quoted-printable"
    return message.as_bytes()


def _parsed_backend(fields=UVA_BACK_2026_FIELDS):
    sender, raw = parse_lgl_email(_backend_mime(fields))
    source = determine_source(sender, raw["Form title"])
    normalized = EmailParser().normalize(raw, source)
    validate_submission(raw, normalized)
    return raw, normalized


def test_uva_backend_2026_real_mime_shape_and_normalized_fields():
    raw, normalized = _parsed_backend()
    assert raw["Is this a monthly gift?"] == "Yes"
    assert raw["Is Recurring"] == "false"
    assert raw["Transaction details"] == "Gift in hand"
    assert tuple(normalized) == NORMALIZED_FIELDS
    assert normalized["source"] == "uva-back"
    assert normalized["total amount"] == "0.01"
    assert normalized["status"] == "Parent of Alumni"
    # The legacy "Grad Year" belongs to a related person, not an alumnus.
    assert normalized["graduation year"] == ""
    assert normalized["recurring payment"] == "true"
    assert normalized["first time giver"] == "false"
    assert normalized["anonymous donation"] == "false"
    # An explicit request to pursue matching counts even though the
    # separate 'currently being matched' radio answer is No.
    assert normalized["work referral"] == "true"


def test_monthly_backend_answer_overrides_automatic_nonrecurring_flag():
    _, normalized = _parsed_backend()
    calculator = CalculateValues.__new__(CalculateValues)
    calculator.df = pd.DataFrame([{
        **normalized,
        "total amount": float(normalized["total amount"]),
        "recurring payment": normalized["recurring payment"] == "true",
    }])
    scores = calculator.calculate_all()
    uva = scores["uva"]
    assert uva["total_amount"] == pytest.approx(0.12)
    assert uva["most_money_families"] == pytest.approx(0.12)
    assert uva["most_individual_donors"] == 1
    assert uva["most_donors_class_2026"] == 0
    assert uva["most_alum_monthly_10_plus"] == 0
    assert uva["most_alum_work_matched"] == 0
    assert uva["most_gifts_over_1000"] == 0
    assert scores["vt"]["total_amount"] == 0


def test_same_phone_on_uva_front_and_backend_counts_one_unique_donor():
    _, normalized = _parsed_backend()
    front = {
        **normalized,
        "source": "uva-front",
        "total amount": 5.0,
        "recurring payment": False,
        "status": "Alumni",
        "graduation year": "2006",
        "first time giver": "true",
    }
    back = {
        **normalized,
        "total amount": 0.01,
        "recurring payment": True,
    }
    calculator = CalculateValues.__new__(CalculateValues)
    calculator.df = pd.DataFrame([front, back])
    scores = calculator.calculate_all()["uva"]
    assert scores["total_amount"] == pytest.approx(5.12)
    assert scores["most_individual_donors"] == 1
    assert scores["most_first_time_donors"] == 1
    assert scores["most_money_families"] == pytest.approx(0.12)
    assert scores["most_alum_work_matched"] == 1


def test_explicit_backend_no_monthly_does_not_annualize():
    fields = [
        (field, "No" if field == "Is this a monthly gift?" else value)
        for field, value in UVA_BACK_2026_FIELDS
    ]
    _, record = _parsed_backend(fields)
    assert record["recurring payment"] == "false"


def test_backend_zero_dollar_gift_fails_closed():
    fields = [
        (field, "0.00" if field == "Gift amount" else value)
        for field, value in UVA_BACK_2026_FIELDS
    ]
    sender, raw = parse_lgl_email(_backend_mime(fields))
    record = EmailParser().normalize(
        raw, determine_source(sender, raw["Form title"])
    )
    with pytest.raises(ValueError, match="positive"):
        validate_submission(raw, record)
