"""November 10, 2026 LGL public/staff notification contracts.

The real four notifications were compared to the screenshots and HTML email
headers. All identities, phone numbers, emails, addresses, dates and IDs here
are invented. These tests neither access IMAP nor place charges.
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


BASE_CONTACT = [
    ("Name - First Name", "Example"),
    ("Name - Last Name", "Donor"),
    ("Email", "donor@example.invalid"),
    ("Phone", "5550102026"),
]

UVA_FRONT = [
    ("Form title", "14th Annual Commonwealth Kiddush Cup Front End Form"),
    ("Submission ID", "synthetic-uva-front-nov10"),
    ("Total Amount", "$5.00"),
    *BASE_CONTACT,
    ("I am a/an", "Current Parent||Alum"),
    ("Alumni Grad Year", ""),
    ("Intended Grad Year", ""),
    ("Related Grad Year", "2028"),
    ("Check all that apply",
     "This is my first gift to Hillel at UVA||"
     "Please don't list my name. I would like to remain anonymous."),
    ("Does your workplace match charitable giving?",
     "I'm not sure, can you look into it for me?"),
    ("Is Recurring", "false"),
]

VT_FRONT = [
    ("Form title", "CWKC 2026 Donation Form"),
    ("Submission ID", "synthetic-vt-front-nov10"),
    ("Total Amount", "$5.00"),
    *BASE_CONTACT,
    ("I am a/an...", "Graduate Student||Current Parent||Alumni"),
    ("Intended Graduation Year", "2027"),
    ("Alumni Graduation Year", "2006"),
    ("Related Student Graduation Year", "2028"),
    ("Check All That Apply:",
     "This is my first gift to Hillel at VT ||"
     "Please don't list my name. I would like to remain anonymous."),
    ("Does Your Workplace Match Charitable Giving?",
     " Yes! I'll go ahead and ask them"),
    ("Employer Name:", "Example Employer"),
    ("Matching Grant", "Yes!"),
    ("Is Recurring", "false"),
]

VT_BACK = [
    ("Form title", "CWKC 2026 Back End Form (Virginia Tech)"),
    ("Submission ID", "synthetic-vt-back-nov10"),
    ("Gift Amount", "20"),
    ("Date", "11/11/2026"),
    ("Is this a monthly gift?", "Yes"),
    ("Passthrough from", "Facebook"),
    ("Transaction Details", "Gift in hand"),
    ("Gift Notes", "SYNTHETIC NO-PAYMENT TEST"),
    *BASE_CONTACT,
    ("Donor is a/an...", "Current Parent||Alum"),
    ("Intended Graduation Year", ""),
    ("Alumni Graduation Year", "2006"),
    ("Related Student Graduation Year", "2027"),
    ("Is This Gift Being Matched by Their Workplace?", "No"),
    ("Check All That Apply", "Donor wants to be anonymous"),
    ("Is Recurring", "false"),
]

UVA_BACK = [
    ("Form title", "14th Annual Commonwealth Kiddush Cup Back-end Form"),
    ("Submission ID", "synthetic-uva-back-nov10"),
    ("Gift amount", "2.06"),
    ("Is this a monthly gift?", "No"),
    ("Passthrough from", "Check"),
    ("Check number", "SYNTHETIC-CHECK"),
    ("Transaction details", "Gift in hand"),
    ("Gift notes", "SYNTHETIC NO-PAYMENT TEST"),
    *BASE_CONTACT,
    ("Donor is a/n...", "Current Parent||Alum"),
    ("Intended Grad Year", ""),
    ("Alumni Grad Year", ""),
    ("Related Grad Year", "2026"),
    ("Is this gift being matched by workplace?", "Yes"),
    ("Check all that apply", "Donor wants to be anonymous"),
    ("Is Recurring", "false"),
]


def _notification(fields, school):
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in fields
    )
    msg = EmailMessage()
    name = "Brody Jewish Center" if school == "uva" else "Hillel at VT"
    msg["From"] = f"{name} <lglforms-submissions@littlegreenlight.com>"
    msg["To"] = "synthetic-service@example.invalid"
    msg.set_content(
        f"<p><table>{rows}</table></p>",
        subtype="html", charset="utf-8", cte="quoted-printable",
    )
    assert msg.get_content_type() == "text/html"
    assert msg["Content-Transfer-Encoding"] == "quoted-printable"
    return msg.as_bytes()


def _normalized(fields, school):
    sender, original = parse_lgl_email(_notification(fields, school))
    record = EmailParser().normalize(
        original, determine_source(sender, original["Form title"])
    )
    validate_submission(original, record)
    assert tuple(record) == NORMALIZED_FIELDS
    return original, record


@pytest.mark.parametrize("school,fields,source,affiliations,year,amount,recurring", [
    ("uva", UVA_FRONT, "uva-front", "Alumni, Current Parent", "", "5.0", "false"),
    ("vt", VT_FRONT, "vt-front", "Alumni, Current Parent, Current Student",
     "2006", "5.0", "false"),
    ("vt", VT_BACK, "vt-back", "Alumni, Current Parent",
     "2006", "20.0", "true"),
    ("uva", UVA_BACK, "uva-back", "Alumni, Current Parent",
     "", "2.06", "false"),
])
def test_actual_nov10_email_labels_normalize_without_failing(
    school, fields, source, affiliations, year, amount, recurring,
):
    original, normalized = _normalized(fields, school)
    assert original["Form title"] == fields[0][1]
    assert normalized["source"] == source
    assert normalized["status"] == affiliations
    assert normalized["graduation year"] == year
    assert normalized["total amount"] == amount
    assert normalized["recurring payment"] == recurring
    assert normalized["anonymous donation"] == "true"


@pytest.mark.parametrize("school,fields,expected", [
    ("uva", UVA_FRONT, "true"),
    ("vt", VT_FRONT, "true"),
    ("vt", VT_BACK, "false"),
    ("uva", UVA_BACK, "false"),
])
def test_nov10_first_time_flags(school, fields, expected):
    assert _normalized(fields, school)[1]["first time giver"] == expected


@pytest.mark.parametrize("school,fields,expected", [
    ("uva", UVA_FRONT, "true"),
    ("vt", VT_FRONT, "true"),
    ("vt", VT_BACK, "false"),
    ("uva", UVA_BACK, "true"),
])
def test_nov10_workplace_match_referral_flags(school, fields, expected):
    assert _normalized(fields, school)[1]["work referral"] == expected


@pytest.mark.parametrize("school,fields,expected_total,expected_family,expected_class", [
    ("uva", UVA_FRONT, 5, 5, 0),
    ("vt", VT_FRONT, 5, 5, 0),
    ("vt", VT_BACK, 240, 240, 0),  # monthly: 20 * 12
    ("uva", UVA_BACK, 2.06, 2.06, 0),  # related YEAR=2026 != donor class
])
def test_nov10_scoring_counts_each_gift_once_and_never_uses_child_year(
    school, fields, expected_total, expected_family, expected_class,
):
    _, row = _normalized(fields, school)
    calc = CalculateValues.__new__(CalculateValues)
    calc.df = pd.DataFrame([{
        **row,
        "total amount": float(row["total amount"]),
        "recurring payment": row["recurring payment"] == "true",
    }])
    totals = calc.calculate_all()
    metrics = totals[school]
    assert metrics["total_amount"] == pytest.approx(expected_total)
    assert metrics["most_money_families"] == pytest.approx(expected_family)
    assert metrics["most_individual_donors"] == 1
    assert metrics["most_donors_class_2026"] == expected_class
    assert metrics["donor_names"] == ""
    other = "uva" if school == "vt" else "vt"
    assert totals[other]["total_amount"] == 0


@pytest.mark.parametrize("school,fields,label", [
    ("uva", UVA_FRONT, "Alumni Grad Year"),
    ("vt", VT_FRONT, "Alumni Graduation Year"),
    ("vt", VT_BACK, "Alumni Graduation Year"),
    ("uva", UVA_BACK, "Alumni Grad Year"),
])
def test_only_explicit_donor_alumni_2026_gets_class_point(school, fields, label):
    updated = [(k, "2026" if k == label else v) for k, v in fields]
    _, record = _normalized(updated, school)
    assert record["graduation year"] == "2026"
    calc = CalculateValues.__new__(CalculateValues)
    calc.df = pd.DataFrame([{
        **record, "total amount": float(record["total amount"]),
        "recurring payment": record["recurring payment"] == "true",
    }])
    assert calc.calculate_all()[school]["most_donors_class_2026"] == 1


@pytest.mark.parametrize("school,fields", [
    ("uva", UVA_FRONT), ("uva", UVA_BACK),
])
def test_blank_alumni_year_is_valid_and_eligible_for_other_categories(
    school, fields,
):
    server, ledger = MagicMock(), MagicMock()
    server.fetch.return_value = {31: {b"BODY[]": _notification(fields, school)}}
    ledger.known.return_value = False
    ledger.insert.return_value = True
    result = process_messages(server, [31], ledger)
    assert result == {"new": 1, "already_stored": 0, "pending": 0, "failed": 0}
    assert ledger.insert.call_count == 1
    saved = ledger.insert.call_args.args[0]
    assert saved["graduation year"] == ""
    server.add_flags.assert_called_once_with(31, ["\\Seen"])


@pytest.mark.parametrize("school,fields", [
    ("uva", UVA_FRONT), ("vt", VT_FRONT),
    ("vt", VT_BACK), ("uva", UVA_BACK),
])
def test_no_alumni_affiliation_never_inherits_related_year(school, fields):
    converted = [
        (k, "Current Parent") if k.lower().startswith(
            ("i am a/an", "donor is a/")
        ) else (k, v)
        for k, v in fields
    ]
    _, row = _normalized(converted, school)
    assert row["graduation year"] == ""
    assert row["status"] == "Current Parent"
