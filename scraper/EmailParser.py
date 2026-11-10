import random
from typing import Dict, Set

from .affiliations import (
    AFFILIATION_ALIASES, ALUMNI, COMMUNITY_MEMBER, RELATED_PERSON_AFFILIATIONS,
)


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

    # Compatibility alias; labels and groups are defined in affiliations.py.
    STATUS_MAP = AFFILIATION_ALIASES

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

    def _normalize_affiliations(self, fields: Dict[str, str]) -> tuple[list[str], str]:
        """Normalize known LGL affiliations without guessing unfamiliar labels."""
        raw_status = fields.get(
            "i am a/an",
            fields.get("i am a/an...",
                       fields.get("donor is a/an...",
                                  fields.get("donor is a/n...", COMMUNITY_MEMBER))),
        )
        try:
            statuses = [
                self.STATUS_MAP[value.strip()]
                for value in raw_status.split("||") if value.strip()
            ]
        except KeyError:
            # Unknown LGL labels must not silently lose eligibility for
            # family or other scoring categories.
            raise ValueError("Unrecognized donor affiliation") from None
        status = ", ".join(sorted(set(statuses))) if statuses else COMMUNITY_MEMBER
        return statuses, status

    def normalize(self, parsed_email: Dict[str, str], source: str) -> Dict[str, str]:
        """Convert parsed email values into the fixed Google Sheets schema."""
        fields = self._canonical_fields(parsed_email)
        statuses, status = self._normalize_affiliations(fields)

        first_name = fields.get("name - first name", "")
        last_name = fields.get("name - last name", "")
        phone = fields.get("phone", "") or self.generate_fallback_phone()

        # 2026 organizer decision: count the full LGL-reported amount,
        # including any optional 3% donor-paid processing fee. Do not
        # substitute the smaller gift selection in "Amount - Details".
        # Backend forms use "Gift amount" rather than "Total Amount".
        raw_amount = fields.get("total amount", fields.get("gift amount", "0"))
        clean_amount = raw_amount.replace("$", "").replace(",", "").strip()
        total_amount = str(float(clean_amount))

        # Class-of-2026 scoring uses the donor's own alumni year only.
        # The November 10 UVA public/backend forms may leave Alumni Grad
        # Year blank while emitting a related student's year (even 2026).
        # Keep the otherwise valid donation, but do not guess alumni credit.
        donor_year_labels = (
            "alumni graduation year", "alumni grad year", "donor graduation year",
        )
        donor_year = next(
            (fields[label] for label in donor_year_labels if fields.get(label)),
            "",
        )
        is_alumni = ALUMNI in statuses
        is_related = bool(RELATED_PERSON_AFFILIATIONS.intersection(statuses))
        raw_generic_year = fields.get(
            "grad year", fields.get("graduation year", ""),
        )
        # An empty Intended Graduation Year accompanies some legacy alumni-
        # only submissions. It does not make their one generic year ambiguous.
        has_named_years = (
            any(label in fields for label in (
                *donor_year_labels, "related grad year",
                "related student graduation year",
            ))
            or bool(fields.get("intended grad year")
                    or fields.get("intended graduation year"))
        )
        if not is_alumni:
            # A relative's year must never be the donor's alumni year.
            grad_year = ""
        elif donor_year:
            grad_year = donor_year
        elif not has_named_years and not is_related:
            # Legacy generic year is safely attributable only to a donor
            # selected as Alumni without any related-person affiliation.
            grad_year = raw_generic_year
        else:
            # Mixed affiliations, or explicitly blank named alumni year:
            # score the other categories, but no alumni class-year credit.
            grad_year = ""


        recurring_raw = fields.get("is recurring", "").lower()
        monthly_raw = fields.get("is this a monthly gift?", "").lower()
        recurring_payment = (
            "true" if recurring_raw in ("true", "yes")
            or monthly_raw in ("true", "yes") else "false"
        )

        check_all_values = {
            x.strip().replace("\xa0", " ").replace("  ", " ")
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

        workplace_answers = (
            fields.get("is this gift being matched by workplace?", ""),
            fields.get("does your workplace match charitable giving?", ""),
            fields.get("is this gift being matched by their workplace?", ""),
        )
        matching_answers = {v.casefold() for v in self.WORK_REFERRAL_YES_VALUES}
        work_referral = (
            bool(check_all_values.intersection(self.WORK_REFERRAL_CHECK_ALL))
            or any(answer.casefold() in matching_answers
                   for answer in workplace_answers)
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
