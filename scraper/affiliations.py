"""One source of truth for normalized donor affiliations and scoring groups.

LGL question choices (left-hand keys) are external form labels. Canonical
affiliations (right-hand values) are stored in the private donation worksheet
and consumed by the scoring and preview calculations.

When a school's form gains a choice, update AFFILIATION_ALIASES here and the
contract tests. Do not add special-case scoring aliases in other modules.
"""

CURRENT_STUDENT = "Current Student"
CURRENT_PARENT = "Current Parent"
CURRENT_GRANDPARENT = "Current Grandparent"
ALUMNI = "Alumni"
PARENT_OF_ALUMNI = "Parent of Alumni"
GRANDPARENT_OF_ALUMNI = "Grandparent of Alumni"
FAMILY_MEMBER_OF_ALUMNI = "Family Member of Alumni"
OTHER_STUDENT_RELATIVE = "Other Student Relative"
COMMUNITY_MEMBER = "Community Member"

# Explicit aliases are intentional: preserve historical and current LGL
# notification labels without multiplying normalized values.
AFFILIATION_ALIASES = {
    CURRENT_STUDENT: CURRENT_STUDENT,
    "Undergraduate Student": CURRENT_STUDENT,
    "Graduate Student": CURRENT_STUDENT,
    CURRENT_PARENT: CURRENT_PARENT,
    CURRENT_GRANDPARENT: CURRENT_GRANDPARENT,
    ALUMNI: ALUMNI,
    "Alum": ALUMNI,
    PARENT_OF_ALUMNI: PARENT_OF_ALUMNI,
    "Parent of an Alum": PARENT_OF_ALUMNI,
    GRANDPARENT_OF_ALUMNI: GRANDPARENT_OF_ALUMNI,
    "Grandparent of an Alum": GRANDPARENT_OF_ALUMNI,
    FAMILY_MEMBER_OF_ALUMNI: FAMILY_MEMBER_OF_ALUMNI,
    "Family member of an Alum": FAMILY_MEMBER_OF_ALUMNI,
    "Family member of Alumni": FAMILY_MEMBER_OF_ALUMNI,
    OTHER_STUDENT_RELATIVE: OTHER_STUDENT_RELATIVE,
    COMMUNITY_MEMBER: COMMUNITY_MEMBER,
}

# Family-of-alumni/current-student giving: any one of these qualifying
# affiliations awards this category, but each gift's dollars count only once.
FAMILY_AFFILIATIONS = frozenset({
    CURRENT_PARENT,
    CURRENT_GRANDPARENT,
    PARENT_OF_ALUMNI,
    GRANDPARENT_OF_ALUMNI,
    FAMILY_MEMBER_OF_ALUMNI,
    OTHER_STUDENT_RELATIVE,
})

# The same affiliations make a legacy unlabeled "Grad Year" ambiguous:
# it could belong to a child or other relative rather than the donor.
RELATED_PERSON_AFFILIATIONS = FAMILY_AFFILIATIONS

# The narrower category only covers grandparents of CURRENT students.
CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS = frozenset({CURRENT_GRANDPARENT})
