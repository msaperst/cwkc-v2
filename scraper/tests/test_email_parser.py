import pytest

from scraper.EmailParser import determine_source, EmailParser


# ---------- determine_source tests ----------

@pytest.mark.parametrize("email_from, form_title, expected", [
    ("Hillel at VT <lglforms-submissions@littlegreenlight.com>", "CWKC 2025 Donation Form", "vt-front"),
    ("Brody Jewish Center <lglforms-submissions@littlegreenlight.com>",
     "13th Annual Commonwealth Kiddush Cup Back-end Form", "uva-back"),
    ("someone@random.org", "frontend gift submission", "unknown-front"),
    ("Hillel at VT <lglforms-submissions@littlegreenlight.com>", "CWKC 2025 Back End Form (Virginia Tech)", "vt-back"),
    ("Brody Jewish Center <lglforms-submissions@littlegreenlight.com>",
     "13th Annual Commonwealth Kiddush Cup Front End Form", "uva-front"),
])
def test_determine_source(email_from, form_title, expected):
    """determine_source should return correct school + form_type combinations."""
    assert determine_source(email_from, form_title) == expected


# ---------- EmailParser.normalize tests ----------

@pytest.fixture
def parser():
    return EmailParser()


def test_basic_normalization(parser):
    """Normalizes a simple, typical donor email correctly."""
    email_data = {
        "I am a/an": "Alumni",
        "Name - First Name": "John",
        "Name - Last Name": "Doe",
        "Phone": "555-1234",
        "Total Amount": "$25.00",
        "Grad Year": "2010",
        "Is Recurring": "Yes",
        "Check all that apply": "Donor's first gift to Hillel at VT || Donor asking to match gift"
    }

    normalized = parser.normalize(email_data, source="vt-front")

    assert normalized["first name"] == "John"
    assert normalized["last name"] == "Doe"
    assert normalized["phone number"] == "555-1234"
    assert normalized["total amount"] == "25.0"
    assert normalized["graduation year"] == "2010"
    assert normalized["status"] == "Alumni"
    assert normalized["recurring payment"] == "true"
    assert normalized["first time giver"] == "true"
    assert normalized["work referral"] == "true"
    assert normalized["anonymous donation"] == "false"
    assert normalized["source"] == "vt-front"


def test_multi_status_mapping(parser):
    """Multiple raw statuses are normalized, deduplicated, and mapped to canonical form."""
    email_data = {
        "I am a/an": "Alum || Parent of an Alum || Parent of Alumni",
        "Name - First Name": "Becca",
        "Name - Last Name": "Goldberg",
        "Total Amount": "$50.00"
    }
    result = parser.normalize(email_data, source="uva-back")

    # Should unify to "Alumni, Parent of Alumni"
    assert result["status"] == "Alumni, Parent of Alumni"
    assert result["first name"] == "Becca"
    assert result["total amount"] == "50.0"
    assert result["source"] == "uva-back"


def test_anonymous_donation(parser):
    """Recognizes anonymous donation via check-all-that-apply."""
    email_data = {
        "I am a/an": "Community Member",
        "Name - First Name": "Anon",
        "Check all that apply": "Please don't list my name. I would like to remain anonymous.",
        "Total Amount": "100"
    }
    result = parser.normalize(email_data, source="vt-front")

    assert result["anonymous donation"] == "true"
    assert result["first time giver"] == "false"


def test_recurring_payment_back_end(parser):
    """Recognizes recurring payment via backend field."""
    email_data = {
        "Donor is a/an...": "Parent of Alumni",
        "Name - First Name": "Chris",
        "Is this a monthly gift?": "Yes",
        "Gift amount": "$10"
    }
    result = parser.normalize(email_data, source="uva-back")

    assert result["recurring payment"] == "true"
    assert result["total amount"] == "10.0"


def test_default_values_when_missing_fields(parser):
    """Fills in defaults when optional fields are missing."""
    email_data = {
        "Total Amount": "$0.00"
    }
    result = parser.normalize(email_data, source="unknown-front")

    # Defaults
    assert result["status"] == "Community Member"
    assert result["first name"] == ""
    assert result["recurring payment"] == "false"
    assert result["total amount"] == "0.0"


def test_work_referral_via_yes_field(parser):
    """Recognizes workplace matching fields."""
    email_data = {
        "I am a/an": "Alumni",
        "Total Amount": "$100",
        "Does your workplace match charitable giving?": "Yes! I'll go ahead and ask them"
    }
    result = parser.normalize(email_data, source="vt-front")

    assert result["work referral"] == "true"
    assert result["first time giver"] == "false"


def test_phone_number_generated_when_blank(parser):
    """Generates a valid 10-digit fallback phone number when phone is missing or blank."""
    email_data = {
        "I am a/an": "Alumni",
        "Name - First Name": "Sam",
        "Name - Last Name": "Smith",
        "Phone": "",  # <-- blank on purpose
        "Total Amount": "$10.00"
    }

    result = parser.normalize(email_data, source="vt-front")

    phone = result["phone number"]

    assert phone != ""  # Should not be empty
    assert phone.isdigit()  # Should be digits only
    assert len(phone) == 10  # Should be 10 digits
