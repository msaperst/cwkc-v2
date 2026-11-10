"""Read-only audit of unread LGL notifications before production ingestion.

This command selects the mailbox READ-ONLY, fetches with BODY.PEEK[], and
does not open Google Sheets, mark email Seen, write a scoreboard, or charge
anyone. Reports intentionally omit donor names, addresses, email and phone.
"""
import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .CalculateValues import CalculateValues
from .EmailParser import EmailParser, determine_source
from .affiliations import (
    ALUMNI, CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS, FAMILY_AFFILIATIONS,
)
from .donation_ledger import NORMALIZED_FIELDS, fingerprint
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
            if ALUMNI in tags and r["graduation year"] == "2026"
        }),
        "most_gifts_over_1000": sum(
            _annualized(r) >= 1000 for r in school_rows
        ),
        "most_alum_monthly_10_plus": sum(
            ALUMNI in tags and _is_true(r["recurring payment"])
            and Decimal(r["total amount"]) >= 10
            for r, tags in zip(school_rows, statuses)
        ),
        "most_alum_work_matched": sum(
            ALUMNI in tags and _is_true(r["work referral"])
            for r, tags in zip(school_rows, statuses)
        ),
        "most_money_families": sum((
            _annualized(r) for r, tags in zip(school_rows, statuses)
            if FAMILY_AFFILIATIONS.intersection(tags)
        ), Decimal(0)),
        "most_money_grandparents_current_students": sum((
            _annualized(r) for r, tags in zip(school_rows, statuses)
            if CURRENT_STUDENT_GRANDPARENT_AFFILIATIONS.intersection(tags)
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
    if ALUMNI in row["status"].split(", ") and not row["graduation year"]:
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
    seen_fingerprints = set()
    identical_mime_skipped = 0
    for uid in uids:
        try:
            fetched = server.fetch(uid, ["BODY.PEEK[]"])
            raw = fetched[uid][b"BODY[]"]
            identity = fingerprint(raw)
            if identity in seen_fingerprints:
                # Production's durable ledger keys the complete raw MIME.
                # Count identical notifications only once in this projection.
                identical_mime_skipped += 1
                continue
            entry = _parse_one(raw, uid)
            seen_fingerprints.add(identity)
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
        "identical_mime_skipped": identical_mime_skipped,
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


def build_preview_csv(report: dict, output_path: Path, *, include_forms=False,
                      credentials_file="scraper/spreadsheet_credentials.json"):
    """Render the standard public CSV columns from read-only computed scores.

    Intentionally redact donor_names: workflow logs and artifacts may be
    readable by people who should not see prelaunch donor identities.
    """
    if report["failed"] or report["missing_exclusion_ids"]:
        raise ValueError("Incomplete audit: cannot generate a score preview")
    template = Path(__file__).resolve().parent.parent / "public/assets/csv/results.csv"
    frame = pd.read_csv(template).astype(object)
    if len(frame) != 1:
        raise ValueError("Unexpected score CSV row count")
    for school in ("uva", "vt"):
        for metric, value in report["provisional_metrics"][school].items():
            column = f"{school}_{metric}"
            if column not in frame.columns:
                raise ValueError("Unexpected score CSV column")
            frame.at[0, column] = value

    if include_forms:
        # The existing Sheets updater mutates only its *in-memory DataFrame*
        # when dry_run=True. It never writes or publishes a file.
        from .getGoogleFormData import SubmissionUpdater
        updater = SubmissionUpdater(credentials_file, str(template))
        # Reading participation Sheets produces informational stdout; retain
        # its in-memory result without printing prelaunch participation totals.
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            updater.update_results(dry_run=True)
        for column in (
            "uva_alumni_gatherings", "vt_alumni_gatherings",
            "uva_hanukkah_photos", "vt_hanukkah_photos",
        ):
            if column not in frame.columns or column not in updater.df.columns:
                raise ValueError("Participation CSV schema mismatch")
            frame.at[0, column] = updater.df.at[0, column]

    # A private, unpublished preview is still not clearance to expose names.
    frame.at[0, "uva_donor_names"] = ""
    frame.at[0, "vt_donor_names"] = ""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def write_action_summary(report: dict, frame: pd.DataFrame, *, include_forms=False):
    """Print the proposed CSV as GitHub Actions job output without PII."""
    summary = [
        "## CWKC read-only results preview",
        "",
        f"Unread notifications: **{report['unread_matching']}**; "
        f"parsed: **{report['parsed']}**; failed: **{report['failed']}**; "
        f"excluded: **{report['excluded']}**; "
        f"unreconciled flagged: **{report['unreconciled_flags']}**.",
        "",
        "### Proposed public results.csv (donor-name columns redacted)",
        "",
        "```csv",
        frame.to_csv(index=False).strip(),
        "```",
        "",
        ("Participation: read-only current Google Forms data."
         if include_forms else
         "Participation/football: unchanged starter CSV values; NOT live-verified."),
        "",
        "**PREVIEW ONLY:** Unreconciled staff/test notifications and duplicate "
        "transactions may inflate this estimate. This is not financial sign-off.",
        "",
    ]
    text = "\n".join(summary)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(text)
    else:
        print(text)


# Fixed workspace paths: user-supplied CLI strings must never become
# filesystem paths in a workflow that handles private financial data.
PREVIEW_FILE = Path(".cwkc-preview-results.csv")
EXCLUSIONS_FILE = Path(".cwkc-excluded-submissions.txt")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only CWKC LGL email-to-CSV scoring preview"
    )
    parser.add_argument(
        "--include-forms", action="store_true",
        help="Also read current Google Forms responses into the CSV preview",
    )
    parser.add_argument(
        "--private-workflow", action="store_true",
        help="Keep financial totals out of public GitHub Actions logs",
    )
    args = parser.parse_args(argv)
    if os.getenv("GITHUB_ACTIONS") == "true" and not args.private_workflow:
        parser.error("Actions must run this audit with --private-workflow")
    if not EMAIL_ACCOUNT or not EMAIL_PASSWORD:
        parser.error("Configure the service mailbox IMAP credentials first")

    excluded = set()
    if EXCLUSIONS_FILE.is_file():
        excluded = {
            line.strip() for line in EXCLUSIONS_FILE.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    with IMAPClient(IMAP_SERVER, ssl=True) as server:
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.select_folder(MAILBOX, readonly=True)
        report = audit_unread(server, frozenset(excluded))

    frame = build_preview_csv(
        report, PREVIEW_FILE, include_forms=args.include_forms,
    )
    if not args.private_workflow:
        write_action_summary(report, frame, include_forms=args.include_forms)

    # All console data is safe for a public CI log: no donor identities/amounts.
    print(
        "Read-only audit:",
        f"unread={report['unread_matching']}",
        f"parsed={report['parsed']}",
        f"duplicate_mime={report['identical_mime_skipped']}",
        f"failed={report['failed']}",
        f"excluded={report['excluded']}",
        f"flagged={report['unreconciled_flags']}",
    )
    print("Independent scoring comparison:", report["independent_score_comparison"])
    if args.private_workflow:
        print("Plaintext aggregate CSV prepared for artifact download; totals withheld from logs")
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write(
                    "## CWKC read-only preview\n\n"
                    "The proposed CSV is available as a one-day downloadable artifact; "
                    "no financial totals or "
                    "donor identities are displayed in this public workflow.\n\n"
                    f"Unread: {report['unread_matching']}; parsed: {report['parsed']}; "
                    f"failed: {report['failed']}; exclusions: {report['excluded']}; "
                    f"flagged: {report['unreconciled_flags']}.\n\n"
                )
    else:
        print("Provisional category metrics (not reconciled to payments):")
        print(json.dumps(report["provisional_metrics"], indent=2))
    print(report["warning"])




if __name__ == "__main__":
    main()
