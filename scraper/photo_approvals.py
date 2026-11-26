"""Read explicitly approved photo IDs without touching participation scores."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit, parse_qs

import gspread

from .getGoogleFormData import (
    GATHERING_FIELDS, GATHERING_SHEET_ID, HANUKKAH_FIELDS, HANUKKAH_SHEET_ID,
    CURRENT_TAB, _normalize, _school, _in_season,
)

APPROVAL_TAB = "Photo approvals"
APPROVAL_HEADER = ["Drive file ID", "Approved", "Alt text", "Review photo"]
FILE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}")


@dataclass(frozen=True)
class ApprovedPhoto:
    file_id: str
    school: str
    category: str
    alt: str


def file_ids(value: str) -> list[str]:
    """Accept only known Google Drive upload URL forms, never arbitrary URLs."""
    result = []
    for part in re.split(r"[,\n]", value):
        if not part.strip():
            continue
        url = urlsplit(part.strip())
        if url.scheme != "https" or url.netloc != "drive.google.com":
            raise ValueError("Unexpected photo upload link")
        if url.path == "/open":
            file_id = parse_qs(url.query).get("id", [""])[0]
        else:
            match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]+)(?:/view)?/?", url.path)
            file_id = match.group(1) if match else ""
        if not FILE_ID.fullmatch(file_id):
            raise ValueError("Invalid Drive photo identifier")
        result.append(file_id)
    return result


def read_approvals(workbook) -> dict[str, str]:
    """Missing tab means no permission; duplicate approval rows fail closed."""
    try:
        rows = workbook.worksheet(APPROVAL_TAB).get_all_values()
    except gspread.WorksheetNotFound:
        return {}
    if not rows or rows[0] not in (APPROVAL_HEADER, APPROVAL_HEADER[:3]):
        raise ValueError("Invalid photo approval header")
    approvals = {}
    seen = set()
    for row in rows[1:]:
        if not any(row):
            continue
        file_id, approved, alt = (row + ["", "", ""])[:3]
        if not FILE_ID.fullmatch(file_id) or file_id in seen:
            raise ValueError("Invalid or duplicate photo approval")
        seen.add(file_id)
        if _normalize(approved) == "yes" and alt.strip() and len(alt.strip()) <= 300:
            approvals[file_id] = alt.strip()
    return approvals


def read_candidates(workbook, fields, category: str, year: int) -> list[ApprovedPhoto]:
    approvals = read_approvals(workbook)
    if not approvals:
        return []
    rows = workbook.worksheet(CURRENT_TAB).get_all_values()
    if not rows:
        raise ValueError("Missing photo response headers")
    headers = [_normalize(header) for header in rows[0]]
    required = ["timestamp", "school", "photo"]
    if category == "hanukkah_photos":
        required.append("photo_release")
    columns = {}
    for key in required:
        prefix = fields[key]
        matches = [i for i, header in enumerate(headers)
                   if header == prefix or header.startswith(prefix + " ")
                   or (prefix.endswith(":") and header.startswith(prefix))]
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous photo response column: " + key)
        columns[key] = matches[0]
    candidates = {}
    denied = set()
    for row in rows[1:]:
        row = row + [""] * len(headers)
        ids = set(file_ids(row[columns["photo"]])) & approvals.keys()
        if not ids:
            continue
        if not _in_season(row[columns["timestamp"]], year):
            continue
        if category == "hanukkah_photos" and _normalize(row[columns["photo_release"]]) != "yes":
            denied.update(ids)
            continue
        school = _school(row[columns["school"]])
        for file_id in ids:
            photo = ApprovedPhoto(file_id, school, category, approvals[file_id])
            if file_id in candidates and candidates[file_id] != photo:
                denied.add(file_id)
            candidates[file_id] = photo
    return [photo for file_id, photo in sorted(candidates.items()) if file_id not in denied]


def approved_photos(client, year: int) -> list[ApprovedPhoto]:
    photos = read_candidates(client.open_by_key(GATHERING_SHEET_ID), GATHERING_FIELDS,
                             "alumni_gatherings", year)
    photos += read_candidates(client.open_by_key(HANUKKAH_SHEET_ID), HANUKKAH_FIELDS,
                              "hanukkah_photos", year)
    # A file associated with conflicting sources must not appear in either gallery.
    counts = {}
    for photo in photos:
        counts[photo.file_id] = counts.get(photo.file_id, 0) + 1
    return [photo for photo in photos if counts[photo.file_id] == 1]
