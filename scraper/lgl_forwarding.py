"""Classify direct LGL notifications and strictly verified Gmail forwards.

Only configured staff-domain forwards with the original LGL sender and
notification subject are eligible. These checks are structural safeguards,
not a replacement for reconciliation against actual LGL payments.
"""
import re
from email.utils import parseaddr

from .donation_ledger import fingerprint

LGL_ADDRESS = "lglforms-submissions@littlegreenlight.com"
FORM_TITLES = {
    "uva-front": "14th Annual Commonwealth Kiddush Cup Front End Form",
    "uva-back": "14th Annual Commonwealth Kiddush Cup Back-end Form",
    "vt-front": "CWKC 2026 Donation Form",
    "vt-back": "CWKC 2026 Back End Form (Virginia Tech)",
}
FORWARDER_DOMAINS = frozenset({"brodyjewishcenter.org", "hillelvt.org"})
FORWARD_SUBJECT = re.compile(r"^\s*Fwd?:\s*New Submission:", re.IGNORECASE)
FORWARD_MARKER = re.compile(
    r"(?m)^\s*-{5,}\s*Forwarded message\s*-{5,}\s*$"
)


def search_unread_lgl(server, from_filter=LGL_ADDRESS):
    """Find direct and forwarded notifications without changing read flags."""
    forwards = server.search(["UNSEEN", "SUBJECT", "Fwd: New Submission:"])
    direct = server.search(["UNSEEN", "FROM", from_filter])
    return sorted(set(forwards) | set(direct))


def original_sender(msg):
    """Return the original LGL From for a direct or authenticated staff forward.

    We require a real Gmail-style plain-text forwarding header. The external
    envelope belongs to an authorized Hillel domain, while the embedded From
    must identify the expected LGL sender and school. Anything else fails
    closed rather than treating a staff forward as an arbitrary donation.
    """
    outer = str(msg.get("From", ""))
    subject = str(msg.get("Subject", ""))
    if not FORWARD_SUBJECT.match(subject):
        return outer

    from_address = parseaddr(outer)[1].lower()
    if not any(from_address.endswith("@" + domain) for domain in FORWARDER_DOMAINS):
        raise ValueError("LGL forward is not from an authorized Hillel domain")

    plain_part = msg.get_body(preferencelist=("plain",))
    if plain_part is None:
        raise ValueError("LGL forward lacks original forwarding headers")
    body = plain_part.get_content().replace("\r\n", "\n")
    marker = FORWARD_MARKER.search(body)
    if marker is None:
        raise ValueError("LGL forward lacks the Gmail forwarded-message marker")

    header = body[marker.end():].split("\n\n", 1)[0]
    from_match = re.search(r"(?mi)^From:\s*(.+?)\s*$", header)
    subject_match = re.search(r"(?mi)^Subject:\s*(.+?)\s*$", header)
    if from_match is None or subject_match is None:
        raise ValueError("LGL forward lacks its original From or Subject")
    original = from_match.group(1).strip()
    name, address = parseaddr(original)
    if address.lower() != LGL_ADDRESS:
        raise ValueError("Forwarded original is not an LGL notification")
    if not any(school in name.casefold() for school in
               ("brody jewish center", "hillel at vt")):
        raise ValueError("LGL forward has an unrecognized Hillel sender")
    if not subject_match.group(1).casefold().startswith("new submission:"):
        raise ValueError("Forwarded original is not a donation notification")
    return original


def submission_key(raw_message, parsed_data):
    """Use LGL's stable source ID so direct and forwarded copies dedupe.

    Earlier messages without an LGL ID retain their MIME fingerprint. A
    forwarded copy must have an LGL ID, or there is no safe cross-copy key.
    The key stays private in the normalized donation ledger.
    """
    source_id = next((
        str(value).strip() for label, value in parsed_data.items()
        if " ".join(label.split()).rstrip(": ").casefold() == "submission id"
    ), "")
    if source_id:
        return "lgl:" + source_id.casefold()
    return fingerprint(raw_message)
