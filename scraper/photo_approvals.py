"""Read explicitly approved photo IDs without touching participation scores."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit, parse_qs

from .getGoogleFormData import (
    GATHERING_FIELDS, GATHERING_SHEET_ID, HANUKKAH_FIELDS, HANUKKAH_SHEET_ID,
    CURRENT_TAB, _normalize, _school, _in_season,
)

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


def read_candidates(workbook, fields, category: str, year: int) -> list[ApprovedPhoto]:
    rows = workbook.worksheet(CURRENT_TAB).get_all_values()
    if not rows:
        raise ValueError("Missing photo response headers")
    headers = [_normalize(header) for header in rows[0]]
    if "approved" not in headers or "alt text" not in headers:
        return []
    required = {key: fields[key] for key in ("timestamp", "school", "photo")}
    required.update({"approved": "approved", "alt": "alt text"})
    if category == "hanukkah_photos":
        required["photo_release"] = fields["photo_release"]
    columns = {}
    for key, prefix in required.items():
        matches = [i for i, header in enumerate(headers)
                   if header == prefix or (key not in {"approved", "alt"} and
                       (header.startswith(prefix + " ") or
                        (prefix.endswith(":") and header.startswith(prefix))))]
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous photo response column: " + key)
        columns[key] = matches[0]
    candidates = {}
    denied = set()
    for row in rows[1:]:
        row = row + [""] * len(headers)
        if not row[columns["photo"]] or not _in_season(row[columns["timestamp"]], year):
            continue
        alt = row[columns["alt"]].strip()
        approved = _normalize(row[columns["approved"]]) == "yes" and 0 < len(alt) <= 300
        if category == "hanukkah_photos":
            approved = approved and _normalize(row[columns["photo_release"]]) == "yes"
        try:
            ids = set(file_ids(row[columns["photo"]]))
        except ValueError:
            if approved:
                raise
            continue
        if not approved:
            denied.update(ids)
            continue
        school = _school(row[columns["school"]])
        for file_id in ids:
            photo = ApprovedPhoto(file_id, school, category, alt)
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
