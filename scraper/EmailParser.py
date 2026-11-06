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
        'Undergraduate Student': 'Current Student',
        'Graduate Student': 'Current Student',
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
        "Yes! I'll go ahead and ask them",  # "Does your workplace match charitable giving?"
        "I'm not sure, can you look into it for me?"  # VT requests follow-up
    }

    @staticmethod
    def _canonical_fields(parsed_email: Dict[str, str]) -> Dict[str, str]:
        """Accept harmless LGL capitalization and trailing-colon differences.

        Do not hide conflicting duplicate values if normalize is called
        directly, rather than through parse_lgl_email's earlier guard.
        """
        fields = {}
        for label, value in parsed_email.items():
            key = " ".join(label.split()).rstrip(": ").casefold()
            cleaned = value.strip()
            if key in fields and fields[key] != cleaned:
                raise ValueError("Conflicting duplicate LGL form field")
            fields[key] = cleaned
        return fields

    def normalize(self, parsed_email: Dict[str, str], source: str) -> Dict[str, str]:
        """Convert parsed email values into the fixed Google Sheets schema."""
        fields = self._canonical_fields(parsed_email)

        raw_status = fields.get(
            "i am a/an",
            fields.get("i am a/an...",
                       fields.get("donor is a/an...",
                                  fields.get("donor is a/n...", COMMUNITY_MEMBER))),
        )
        statuses = [
            self.STATUS_MAP.get(s.strip(), COMMUNITY_MEMBER)
            for s in raw_status.split("||") if s.strip()
        ]
        status = ", ".join(sorted(set(statuses))) if statuses else COMMUNITY_MEMBER

        first_name = fields.get("name - first name", "")
        last_name = fields.get("name - last name", "")
        phone = fields.get("phone", "") or self.generate_fallback_phone()

        raw_amount = fields.get("total amount", fields.get("gift amount", "0"))
        clean_amount = raw_amount.replace("$", "").replace(",", "").strip()
        total_amount = str(float(clean_amount))

        # Use the donor's own alumni year, never a distinct related-student year.
        # Identical repeated "Graduation Year" labels still fail closed in
        # parse_lgl_email; do not guess from their order in a notification.
        grad_year = fields.get(
            "alumni graduation year",
            fields.get("donor graduation year",
                       fields.get("grad year", fields.get("graduation year", ""))),
        )

        recurring_raw = fields.get("is recurring", "").lower()
        monthly_raw = fields.get("is this a monthly gift?", "").lower()
        recurring_payment = (
            "true" if recurring_raw in ("true", "yes")
            or monthly_raw in ("true", "yes") else "false"
        )

        check_all_values = {
            x.strip().replace("\\xa0", " ").replace("  ", " ")
            for x in fields.get("check all that apply", "").split("||")
            if x.strip()
        }
        first_time_giver = (
            "true" if check_all_values.intersection(self.FIRST_TIME_GIFTS)
            else "false"
        )
        anonymous_donation = (
            "true" if check_all_values.intersection(self.ANONYMOUS_DONATIONS)
            else "false"
        )

        workplace_answer_1 = fields.get("is this gift being matched by workplace?", "")
        workplace_answer_2 = fields.get("does your workplace match charitable giving?", "")
        matching_answers = {v.casefold() for v in self.WORK_REFERRAL_YES_VALUES}
        work_referral = (
            bool(check_all_values.intersection(self.WORK_REFERRAL_CHECK_ALL))
            or workplace_answer_1.casefold() in matching_answers
            or workplace_answer_2.casefold() in matching_answers
        )
        # The VT "Matching Grant" question is a separate challenge grant
        # election, NOT proof of workplace matching or additional gift dollars.

        return {
            "phone number": phone,
            "total amount": total_amount,
            "first name": first_name,
            "last name": last_name,
            "anonymous donation": anonymous_donation,
            "first time giver": first_time_giver,
            "graduation year": grad_year,
            "status": status,
            "work referral": "true" if work_referral else "false",
            "recurring payment": recurring_payment,
            "source": source,
        }

    @staticmethod
    def generate_fallback_phone() -> str:
        """
        Generate a 10-digit fallback phone number if none was provided.
        Ensures the first digit is non-zero.
        """
        return str(random.randint(10 ** 9, 10 ** 10 - 1))
