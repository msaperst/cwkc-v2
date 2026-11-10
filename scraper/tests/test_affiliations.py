"""External LGL affiliation labels and scoring groups are centralized here.

These tests intentionally hard-code the school's known form options so a
mistaken edit to the mapping cannot silently change expected classifications.
"""
import pytest

from scraper.CalculateValues import CalculateValues
from scraper.EmailParser import EmailParser
from scraper.affiliations import (
    AFFILIATION_ALIASES, ALUMNI, COMMUNITY_MEMBER,
    CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS, FAMILY_AFFILIATIONS,
    RELATED_PERSON_AFFILIATIONS,
)


@pytest.mark.parametrize("raw,normalized", [
    ("Current Student", "Current Student"),
    ("Undergraduate Student", "Current Student"),
    ("Graduate Student", "Current Student"),
    ("Current Parent", "Current Parent"),
    ("Current Grandparent", "Current Grandparent"),
    ("Alum", "Alumni"),
    ("Alumni", "Alumni"),
    ("Parent of Alumni", "Parent of Alumni"),
    ("Parent of an Alum", "Parent of Alumni"),
    ("Grandparent of Alumni", "Grandparent of Alumni"),
    ("Grandparent of an Alum", "Grandparent of Alumni"),
    ("Family member of an Alum", "Family Member of Alumni"),
    ("Family member of Alumni", "Family Member of Alumni"),
    ("Family Member of Alumni", "Family Member of Alumni"),
    ("Other Student Relative", "Other Student Relative"),
    ("Community Member", "Community Member"),
])
def test_known_lgl_choices_are_normalized_without_guessing(raw, normalized):
    assert AFFILIATION_ALIASES[raw] == normalized


def test_family_and_grandparent_groups_are_exact():
    assert FAMILY_AFFILIATIONS == frozenset({
        "Current Parent",
        "Current Grandparent",
        "Parent of Alumni",
        "Grandparent of Alumni",
        "Family Member of Alumni",
        "Other Student Relative",
    })
    assert CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS == {
        "Current Grandparent",
    }
    assert RELATED_PERSON_AFFILIATIONS is FAMILY_AFFILIATIONS
    assert COMMUNITY_MEMBER not in FAMILY_AFFILIATIONS
    assert ALUMNI not in FAMILY_AFFILIATIONS
    assert FAMILY_AFFILIATIONS <= set(AFFILIATION_ALIASES.values())


def test_consumer_mapping_compatibility_names_use_shared_references():
    assert EmailParser.STATUS_MAP is AFFILIATION_ALIASES
    assert CalculateValues.FAMILY_STATUSES is FAMILY_AFFILIATIONS
    assert (
        CalculateValues.GRANDPARENT_STATUS
        is CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS
    )


def test_unsupported_affiliation_fails_instead_of_becoming_community_member():
    with pytest.raises(ValueError, match="Unrecognized donor affiliation"):
        EmailParser().normalize({
            "I am a/an": "New school category not mapped",
            "Total Amount": "$100.00",
        }, source="uva-front")


def test_legacy_missing_affiliation_keeps_community_fallback():
    row = EmailParser().normalize({"Total Amount": "$10.00"}, "uva-front")
    assert row["status"] == COMMUNITY_MEMBER
