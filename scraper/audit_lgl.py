"""Read-only audit of unread LGL notifications before production ingestion.

This command selects the mailbox READ-ONLY, fetches with BODY.PEEK[], and
does not open Google Sheets, mark email Seen, write a scoreboard, or charge
anyone. Reports intentionally omit donor names, addresses, email and phone.
"""
import argparse
import json
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .CalculateValues import CalculateValues
from .EmailParser import EmailParser, determine_source
from .donation_ledger import NORMALIZED_FIELDS
from .getLglFormData import (
    EMAIL_ACCOUNT, EMAIL_PASSWORD, FROM_FILTER, IMAP_SERVER, MAILBOX,
    IMAPClient, parse_lgl_email, validate_submission,
)

FORM_TITLES = {
    "uva-front": "14th Annual Commonwealth Kiddush Cup Front End Form",
    "uva-back": "14th Annual Commonwealth Kiddush Cup Back-end Form",
    "vt-front": "CWKC 2026 Donation Form",
    "vt-back": "CWKC 2026 Back End Form (Virginia Tech)",
}
MONEY_METRICS = {
    "total_amount", "most_money_families",
    "most_money_grandparents_current_students",
}
FAMILY = {
    "Current Parent", "Current Grandparent",
    "Parent of Alumni", "Grandparent of Alumni",
}


def _is_true(value):
    return str(value).casefold() == "true"


def _annualized(row):
    amount = Decimal(row["total amount"])
    return amount * (12 if _is_true(row["recurring payment"]) else 1)


def _reference(rows, school):
    """Independent, small reference implementation of the scoring rules."""
    school_rows = [
        r for r in rows if r["source"].startswith(school)
    ]
    statuses = [set(r["status"].split(", ")) for r in school_rows]
    names = []
    seen_names = set()
    for r in school_rows:
        if _is_true(r["anonymous donation"]):
            continue
        identity = (r["phone number"], r["first name"], r["last name"])
        if identity not in seen_names:
            seen_names.add(identity)
            names.append(f"{r['first name']} {r['last name']}".strip())

    return {
        "total_amount": sum((_annualized(r) for r in school_rows), Decimal(0)),
        "most_individual_donors": len({r["phone number"] for r in school_rows}),
        "donor_names": ", ".join(names),
        "most_first_time_donors": len({
            r["phone number"] for r in school_rows if _is_true(r["first time giver"])
        }),
        "most_donors_class_2026": len({
            r["phone number"] for r, tags in zip(school_rows, statuses)
            if "Alumni" in tags and r["graduation year"] == "2026"
        }),
        "most_gifts_over_1000": sum(
            _annualized(r) >= 1000 for r in school_rows
        ),
        "most_alum_monthly_10_plus": sum(
            "Alumni" in tags and _is_true(r["recurring payment"])
            and Decimal(r["total amount"]) >= 10
            for r, tags in zip(school_rows, statuses)
        ),
        "most_alum_work_matched": sum(
            "Alumni" in tags and _is_true(r["work referral"])
            for r, tags in zip(school_rows, statuses)
        ),
        "most_money_families": sum((
            _annualized(r) for r, tags in zip(school_rows, statuses)
            if FAMILY.intersection(tags)
        ), Decimal(0)),
        "most_money_grandparents_current_students": sum((
            _annualized(r) for r, tags in zip(school_rows, statuses)
            if "Current Grandparent" in tags
        ), Decimal(0)),
    }


def _calculate(rows):
    """Compare the real CalculateValues implementation with independent math."""
    frame = pd.DataFrame(rows, columns=NORMALIZED_FIELDS)
    frame["source"] = frame["source"].astype(str)
    frame["total amount"] = pd.to_numeric(frame["total amount"], errors="raise")
    frame["recurring payment"] = frame["recurring payment"].map(_is_true)
    scorer = CalculateValues.__new__(CalculateValues)
    scorer.df = frame
    actual = scorer.calculate_all()
    clean = {}
    for school in ("uva", "vt"):
        expected = _reference(rows, school)
        for key, value in expected.items():
            calculated = actual[school][key]
            if key in MONEY_METRICS:
                if abs(Decimal(str(calculated)) - value) > Decimal("0.001"):
                    raise AssertionError(f"{school} {key}: score mismatch")
            elif calculated != value:
                raise AssertionError(f"{school} {key}: score mismatch")
        # Donor names are checked internally but never included in output.
        clean[school] = {
            key: (str(Decimal(str(value)).quantize(Decimal("0.01")))
                  if key in MONEY_METRICS else int(value))
            for key, value in actual[school].items() if key != "donor_names"
        }
    return clean


def _get_field(data, label):
    """Case-insensitive label lookup without exposing private field values."""
    wanted = label.casefold()
    return next((
        value for key, value in data.items()
        if key.casefold() == wanted
    ), "")


def _parse_one(raw, uid):
    sender, data = parse_lgl_email(raw)
    source = determine_source(sender, data.get("Form title", ""))
    if FORM_TITLES.get(source) != data.get("Form title"):
        raise ValueError("Unrecognized 2026 form title")
    row = EmailParser().normalize(data, source)
    validate_submission(data, row)
    if tuple(row) != NORMALIZED_FIELDS:
        raise ValueError("Normalized schema mismatch")

    notes = _get_field(data, "Gift notes")
    flags = []
    if source.endswith("-back"):
        flags.append("staff-entry-check-payment")
    if "test" in notes.casefold():
        flags.append("test-note")
    if "Alumni" in row["status"].split(", ") and not row["graduation year"]:
        flags.append("unverified-alumni-year")
    if data.get("__ambiguous_alumni_year__") == "true":
        flags.append("old-ambiguous-vt-years")
    if not _get_field(data, "Phone"):
        flags.append("missing-original-phone")
    if _get_field(data, "Is Recurring").casefold() == "false" and (
        _get_field(data, "Is this a monthly gift?").casefold() == "yes"
    ):
        flags.append("monthly-form-vs-recurring-flag")
    if not data.get("Submission ID"):
        flags.append("missing-lgl-submission-id")

    return {
        "uid": uid,
        "submission_id": data.get("Submission ID", ""),
        "submission_date": data.get("Submission Date", ""),
        "source": source,
        "amount": row["total amount"],
        "annualized_amount": str(_annualized(row)),
        "status": row["status"],
        "donor_alumni_year": row["graduation year"],
        "flags": flags,
        "_row": row,  # in-memory only: includes donor identity; never serialize
    }


def audit_unread(server, excluded_ids=frozenset()):
    """Audit all matching UNSEEN mail without acknowledging or changing it."""
    uids = server.search(["UNSEEN", "FROM", FROM_FILTER])
    entries, errors = [], []
    for uid in uids:
        try:
            fetched = server.fetch(uid, ["BODY.PEEK[]"])
            entry = _parse_one(fetched[uid][b"BODY[]"], uid)
            entries.append(entry)
        except Exception as exc:
            # Exception text may contain PII; only the type is safe to show.
            errors.append({"uid": uid, "error_type": type(exc).__name__})

    present_ids = [e["submission_id"] for e in entries if e["submission_id"]]
    duplicate_ids = {x for x in present_ids if present_ids.count(x) > 1}
    inventory = []
    for entry in entries:
        flags = list(entry["flags"])
        if entry["submission_id"] in duplicate_ids:
            flags.append("duplicate-lgl-submission-id")
        inventory.append({
            key: value for key, value in entry.items() if not key.startswith("_")
        } | {
            "flags": flags,
            "excluded": entry["submission_id"] in excluded_ids,
        })

    included = [
        entry["_row"] for entry in entries
        if entry["submission_id"] not in excluded_ids
    ]
    metrics = _calculate(included)
    return {
        "unread_matching": len(uids),
        "parsed": len(entries),
        "failed": len(errors),
        "excluded": sum(x["excluded"] for x in inventory),
        "unreconciled_flags": sum(
            bool(x["flags"]) and not x["excluded"] for x in inventory
        ),
        "missing_exclusion_ids": sorted(
            excluded_ids.difference(present_ids)
        ),
        "errors": errors,
        "inventory": inventory,
        "provisional_metrics": metrics,
        "independent_score_comparison": "passed",
        "warning": (
            "NOT verified financial totals: reconcile actual LGL gifts, "
            "staff tests and duplicate transactions before publication."
        ),
    }


def _write_private_json(path: Path, report: dict):
    """Create a new owner-only local inventory, never overwrite an old one."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="READ-ONLY CWKC LGL email inventory and score projection"
    )
    parser.add_argument(
        "--exclude-file", type=Path,
        help="Local private text file: one verified non-donation submission ID per line",
    )
    parser.add_argument(
        "--report", type=Path,
        help="Write a NEW private 0600 JSON inventory with IDs but NO donor PII",
    )
    args = parser.parse_args(argv)
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        parser.error("Configure the service mailbox IMAP credentials first")
    excluded = set()
    if args.exclude_file:
        excluded = {
            line.strip() for line in args.exclude_file.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    with IMAPClient(IMAP_SERVER, ssl=True) as server:
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.select_folder(MAILBOX, readonly=True)
        report = audit_unread(server, frozenset(excluded))

    if args.report:
        _write_private_json(args.report, report)
    # Console output never includes donors' contact details or submission IDs.
    print(
        "Read-only audit:",
        f"unread={report['unread_matching']}",
        f"parsed={report['parsed']}",
        f"failed={report['failed']}",
        f"excluded={report['excluded']}",
        f"flagged={report['unreconciled_flags']}",
    )
    print("Independent scoring comparison:", report["independent_score_comparison"])
    print("Provisional category metrics (not reconciled to payments):")
    print(json.dumps(report["provisional_metrics"], indent=2))
    print(report["warning"])
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
