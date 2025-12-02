import random
from typing import Dict, Set

COMMUNITY_MEMBER = 'Community Member'
GRANDPARENT_OF_ALUMNI = 'Grandparent of Alumni'
PARENT_OF_ALUMNI = 'Parent of Alumni'


def determine_source(email_from: str, form_title: str) -> str:
    """
    Determine the donation source based on the email 'From' address
    and whether the form is a front-end or back-end submission.
    """
    sender = email_from.lower()
    title = form_title.lower().replace("-", " ")  # normalize hyphens

    if "hillel at vt" in sender:
        school = "vt"
    elif "brody jewish center" in sender:
        school = "uva"
    else:
        school = "unknown"

    if "back end" in title or "backend" in title:
        form_type = "back"
    else:
        form_type = "front"

    return f"{school}-{form_type}"


class EmailParser:
    """
    Class to normalize donation email data into a consistent format for Google Sheets.
    """

    # ========== Canonical Enums / Mappings ==========
    STATUS_MAP = {
        'Current Student': 'Current Student',
        'Current Parent': 'Current Parent',
        'Current Grandparent': 'Current Grandparent',
        'Alumni': 'Alumni',
        'Alum': 'Alumni',
        PARENT_OF_ALUMNI: PARENT_OF_ALUMNI,
        'Parent of an Alum': PARENT_OF_ALUMNI,
        GRANDPARENT_OF_ALUMNI: GRANDPARENT_OF_ALUMNI,
        'Grandparent of an Alum': GRANDPARENT_OF_ALUMNI,
        COMMUNITY_MEMBER: COMMUNITY_MEMBER
    }

    FIRST_TIME_GIFTS: Set[str] = {
        "Donor's first gift to Hillel at VT",
        "This is my first gift to Hillel at VT",
        "Donor's first gift to Hillel at UVA",
        "This is my first gift to Hillel at UVA",
    }

    ANONYMOUS_DONATIONS: Set[str] = {
        "Donor wants to be anonymous",
        "Please don't list my name. I would like to remain anonymous.",
    }

    WORK_REFERRAL_CHECK_ALL: Set[str] = {
        "Donor asking to match gift"
    }

    WORK_REFERRAL_YES_VALUES: Set[str] = {
        "Yes",  # "Is this gift being matched by workplace?"
        "Yes! I'll go ahead and ask them"  # "Does your workplace match charitable giving?"
    }

    def normalize(self, parsed_email: Dict[str, str], source: str) -> Dict[str, str]:
        """
        Convert parsed email key/value pairs into a normalized row for Google Sheets.
        """

        # Status
        raw_status = parsed_email.get("I am a/an", parsed_email.get("I am a/an...",
                                                                    parsed_email.get("Donor is a/an...",
                                                                                     parsed_email.get("Donor is a/n...",
                                                                                                      COMMUNITY_MEMBER))
                                                                    ))
        # Split on '||', normalize, and map each to canonical form
        statuses = [
            self.STATUS_MAP.get(s.strip(), COMMUNITY_MEMBER)
            for s in raw_status.split("||")
            if s.strip()
        ]
        # Join multiple statuses with commas (e.g., "Alumni, Parent of Alumni")
        status = ", ".join(sorted(set(statuses))) if statuses else COMMUNITY_MEMBER

        # Name fields
        first_name = parsed_email.get("Name - First Name", "").strip()
        last_name = parsed_email.get("Name - Last Name", "").strip()

        # Phone
        phone = parsed_email.get("Phone", "").strip()
        if not phone:
            phone = self.generate_fallback_phone()

        # Total amount
        raw_amount = parsed_email.get("Total Amount", parsed_email.get("Gift amount", "0"))
        clean_amount = (
            raw_amount
            .replace("$", "")
            .replace(",", "")
            .strip()
        )
        total_amount = str(float(clean_amount))

        # Graduation year
        grad_year = parsed_email.get("Grad Year", "").strip()

        # Recurring payment (check front-end 'Is Recurring' or back-end 'Is this a monthly gift?')
        recurring_raw = parsed_email.get("Is Recurring", "").strip().lower()
        monthly_raw = parsed_email.get("Is this a monthly gift?", "").strip().lower()
        recurring_payment = "true" if recurring_raw in ("true", "yes") or monthly_raw in ("true", "yes") else "false"

        # Check-all-that-apply
        check_all_raw = parsed_email.get("Check all that apply", parsed_email.get("Check all that apply:", ""))
        check_all_values = {
            x.strip().replace('\xa0', ' ').replace("  ", " ")
            for x in check_all_raw.split("||")
            if x.strip()
        }

        # First-time giver
        first_time_giver = "true" if check_all_values.intersection(self.FIRST_TIME_GIFTS) else "false"

        # Anonymous donation
        anonymous_donation = "true" if check_all_values.intersection(self.ANONYMOUS_DONATIONS) else "false"

        # Work referral
        work_referral = False
        if check_all_values.intersection(self.WORK_REFERRAL_CHECK_ALL):
            work_referral = True

        workplace_field_1 = parsed_email.get("Is this gift being matched by workplace?", "")
        workplace_field_2 = parsed_email.get("Does your workplace match charitable giving?", "")
        if workplace_field_1.strip() in self.WORK_REFERRAL_YES_VALUES or workplace_field_2.strip() in self.WORK_REFERRAL_YES_VALUES:
            work_referral = True
        work_referral = "true" if work_referral else "false"

        normalized = {
            "phone number": phone,
            "total amount": total_amount,
            "first name": first_name,
            "last name": last_name,
            "anonymous donation": anonymous_donation,
            "first time giver": first_time_giver,
            "graduation year": grad_year,
            "status": status,
            "work referral": work_referral,
            "recurring payment": recurring_payment,
            "source": source
        }

        return normalized

    @staticmethod
    def generate_fallback_phone() -> str:
        """
        Generate a 10-digit fallback phone number if none was provided.
        Ensures the first digit is non-zero.
        """
        return str(random.randint(10 ** 9, 10 ** 10 - 1))
