"""Synthetic tests for the independent photo publication pipeline."""
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from scraper import getPhotos, photo_approvals as approvals, photo_snapshot as snapshot
from scraper.tests.test_google_form_data import GATHERING_HEADER, HANUKKAH_HEADER, PHOTO_RELEASE_YES


ID = "synthetic_file_123"
OTHER = "synthetic_file_456"
LINK = "https://drive.google.com/open?id=" + ID
YEAR = 2026


def workbook(rows):
    book = MagicMock()
    book.worksheet.return_value.get_all_values.return_value = rows
    return book


def responses(category, values, moderated=True):
    fields = approvals.HANUKKAH_FIELDS if category == "hanukkah_photos" else approvals.GATHERING_FIELDS
    if category == "hanukkah_photos":
        headers = [HANUKKAH_HEADER[i] for i in (0, 3, 6, 7)]
    else:
        headers = [GATHERING_HEADER[i] for i in (0, 2, 6)]
    if moderated:
        headers += ["Image Approved", "Image Alt Text"]
    return fields, [headers] + values


@pytest.mark.parametrize("url", [
    LINK,
    "https://drive.google.com/file/d/" + ID + "/view?usp=sharing",
    "https://drive.google.com/open?usp=sharing&id=" + ID,
])
def test_file_ids(url):
    assert approvals.file_ids(url) == [ID]
    assert approvals.file_ids(url + ", " + LINK + "\n") == [ID, ID]


@pytest.mark.parametrize("url", [
    "https://example.invalid/open?id=" + ID,
    "http://drive.google.com/open?id=" + ID,
    "https://drive.google.com/open?id=bad",
    "https://drive.google.com/unknown",
])
def test_reject_unknown_links(url):
    with pytest.raises(ValueError):
        approvals.file_ids(url)


def test_unconfigured_sheet_and_missing_alt_fail_closed():
    category = "hanukkah_photos"
    fields, rows = responses(category, [["11/26/2026", "UVA", LINK, PHOTO_RELEASE_YES]], moderated=False)
    assert approvals.read_candidates(rows, fields, category, YEAR) == []
    fields, rows = responses(category, [
        ["11/26/2026", "UVA", LINK, PHOTO_RELEASE_YES, "Yes", ""],
        ["11/26/2026", "VT", "https://drive.google.com/open?id=" + OTHER, PHOTO_RELEASE_YES, "Yes", "x" * 301],
    ])
    assert approvals.read_candidates(rows, fields, category, YEAR) == []
    rows[0].append("Image Approved")
    with pytest.raises(ValueError, match="ambiguous"):
        approvals.read_candidates(rows, fields, category, YEAR)
    with pytest.raises(ValueError, match="headers"):
        approvals.read_candidates([], fields, category, YEAR)


def test_hanukkah_requires_release_and_approval():
    category = "hanukkah_photos"
    fields, rows = responses(category, [
        ["11/26/2026", "UVA", LINK, PHOTO_RELEASE_YES, " YES ", "  Candles  "],
        ["11/26/2026", "VT", "https://drive.google.com/open?id=" + OTHER, "No", "Yes", "Private"],
        ["11/26/2026", "UVA", "", PHOTO_RELEASE_YES, "Yes", "No upload"],
    ])
    assert approvals.read_candidates(rows, fields, category, YEAR) == [
        approvals.ApprovedPhoto(ID, "uva", category, "Candles")
    ]
    rows[1][-2] = "No"
    assert approvals.read_candidates(rows, fields, category, YEAR) == []
    rows[1][-2] = "Yes"
    rows.append(["11/26/2026", "UVA", LINK, "No", "Yes", "Candles"])
    assert approvals.read_candidates(rows, fields, category, YEAR) == []


def test_gathering_early_approval_and_season_and_conflicts():
    category = "alumni_gatherings"
    fields, rows = responses(category, [
        ["11/25/2026", "VT", LINK, "Yes", "Group"],
        ["11/25/2025", "UVA", LINK, "Yes", "Group"],
        ["11/25/2026", "VT", "not a URL", "No", ""],
    ])
    assert approvals.read_candidates(rows, fields, category, YEAR) == [
        approvals.ApprovedPhoto(ID, "vt", category, "Group")
    ]
    rows.append(["11/25/2026", "UVA", LINK, "Yes", "Group"])
    assert approvals.read_candidates(rows, fields, category, YEAR) == []
    rows[3][-2:] = ["Yes", "Group"]
    with pytest.raises(ValueError, match="upload link"):
        approvals.read_candidates(rows, fields, category, YEAR)


def test_multiple_uploads_share_row_approval():
    category = "alumni_gatherings"
    fields, rows = responses(category, [
        ["11/25/2026", "VT", LINK + ", https://drive.google.com/open?id=" + OTHER, "Yes", "Group"],
    ])
    assert {p.file_id for p in approvals.read_candidates(rows, fields, category, YEAR)} == {ID, OTHER}


def test_cross_source_conflict():
    client = MagicMock()
    _, gatherings = responses("alumni_gatherings", [["11/25/2026", "VT", LINK, "Yes", "Group"]])
    _, hanukkah = responses("hanukkah_photos", [["11/25/2026", "UVA", LINK, PHOTO_RELEASE_YES, "Yes", "Candles"]])
    client.open_by_key.side_effect = [workbook(gatherings), workbook(hanukkah)]
    assert approvals.approved_photos(client, YEAR) == []


def image_bytes():
    output = io.BytesIO()
    image = Image.new("RGB", (2000, 1000), "orange")
    exif = image.getexif()
    exif[270] = "private description"
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def test_optimize_strips_metadata_and_resizes():
    with Image.open(io.BytesIO(getPhotos.optimize(image_bytes()))) as image:
        assert image.size == (1600, 800)
        assert not image.getexif()
        assert image.format == "JPEG"
    with pytest.raises(ValueError):
        getPhotos.optimize(b"")


def test_drive_download_validates_metadata_and_size():
    drive = MagicMock()
    resource = drive.files.return_value
    metadata = resource.get.return_value.execute
    media = resource.get_media.return_value.execute
    metadata.return_value = {"size": "3", "mimeType": "image/jpeg"}
    media.return_value = b"abc"
    assert getPhotos.download_photo(drive, ID) == b"abc"
    media.return_value = b"ab"
    with pytest.raises(ValueError):
        getPhotos.download_photo(drive, ID)
    metadata.return_value = {"size": "3", "mimeType": "text/html"}
    with pytest.raises(ValueError):
        getPhotos.download_photo(drive, ID)
    metadata.return_value = {"size": str(getPhotos.MAX_BYTES + 1), "mimeType": "image/png"}
    with pytest.raises(ValueError):
        getPhotos.download_photo(drive, ID)


def test_publish_only_approved_assets_and_skip_bad_image(tmp_path):
    destination = tmp_path / "gallery"
    photos = [
        approvals.ApprovedPhoto(ID, "uva", "hanukkah_photos", "Candles"),
        approvals.ApprovedPhoto(OTHER, "vt", "alumni_gatherings", "Broken"),
    ]
    assert getPhotos.generate(photos, lambda value: image_bytes() if value == ID else b"bad",
                              destination, YEAR) == (1, 1)
    manifest = json.loads((destination / "photos.json").read_text())
    assert len(manifest) == 1
    assert manifest[0]["alt"] == "Candles"
    assert ID not in json.dumps(manifest)
    path = destination / Path(manifest[0]["src"]).name
    assert path.name == hashlib.sha256(path.read_bytes()).hexdigest() + ".jpg"
    restored = tmp_path / "restored"
    restored.mkdir()
    snapshot.validate_snapshot(lambda name: (destination / name).read_bytes(), YEAR, restored)
    assert (restored / path.name).read_bytes() == path.read_bytes()
    assert (restored / "photos.json").read_bytes() == (destination / "photos.json").read_bytes()
    with pytest.raises(ValueError):
        getPhotos.generate([], lambda _: b"", destination, YEAR)
    assert getPhotos.generate([], lambda _: b"", tmp_path / "revoked", YEAR) == (0, 0)


def test_snapshot_invalid_and_disabled_clear_gallery(tmp_path, monkeypatch):
    destination = tmp_path / "photos"
    destination.mkdir()
    (destination / "stale.jpg").write_bytes(b"stale")
    monkeypatch.setattr(snapshot, "fetch_snapshot", lambda: True)
    monkeypatch.setattr(snapshot, "read_snapshot_file", lambda _: b"invalid")
    snapshot.restore(YEAR, destination, enabled=True)
    assert sorted(path.name for path in destination.iterdir()) == ["photos.json"]
    assert json.loads((destination / "photos.json").read_text()) == []
    monkeypatch.setattr(snapshot, "fetch_snapshot", lambda: pytest.fail("disabled must not fetch"))
    snapshot.restore(YEAR, destination, enabled=False)
    assert json.loads((destination / "photos.json").read_text()) == []


@pytest.mark.parametrize("manifest", [
    {},
    [{"school": "other", "category": "hanukkah_photos", "src": "x", "alt": "A"}],
    [{"school": "uva", "category": "hanukkah_photos", "src": "../private.jpg", "alt": "A"}],
    [{"school": "uva", "category": "hanukkah_photos", "src": "assets/photos/" + "a" * 64 + ".jpg", "alt": "A"}],
])
def test_snapshot_rejects_unvalidated_data(tmp_path, manifest):
    files = {"season.json": json.dumps({"year": YEAR}).encode(),
             "photos.json": json.dumps(manifest).encode()}
    with pytest.raises(ValueError):
        snapshot.validate_snapshot(lambda name: files.get(name, b"bad"), YEAR, tmp_path)
    with pytest.raises(ValueError):
        snapshot.validate_snapshot(lambda name: files[name], YEAR + 1, tmp_path)


def test_approved_photos_reuses_already_read_scoring_rows():
    _, gatherings = responses("alumni_gatherings", [["11/25/2026", "VT", LINK, "Yes", "Group"]])
    _, hanukkah = responses("hanukkah_photos", [])
    rows = {approvals.GATHERING_SHEET_ID: gatherings, approvals.HANUKKAH_SHEET_ID: hanukkah}
    assert approvals.approved_photos(None, YEAR, rows) == [
        approvals.ApprovedPhoto(ID, "vt", "alumni_gatherings", "Group")
    ]


def test_sync_uses_read_only_credentials_and_omits_failed_file(monkeypatch, tmp_path, capsys):
    credentials = MagicMock()
    monkeypatch.setattr(getPhotos.Credentials, "from_service_account_file", credentials)
    client = MagicMock()
    monkeypatch.setattr(getPhotos.gspread, "authorize", lambda _: client)
    monkeypatch.setattr(getPhotos, "approved_photos", lambda *_: [
        approvals.ApprovedPhoto(ID, "uva", "hanukkah_photos", "Candles"),
        approvals.ApprovedPhoto(OTHER, "vt", "alumni_gatherings", "Broken")
    ])
    builder = MagicMock()
    monkeypatch.setattr(getPhotos, "build", builder)
    monkeypatch.setattr(getPhotos, "download_photo",
                        lambda _, value: image_bytes() if value == ID else b"invalid")
    output = tmp_path / "photos"
    getPhotos.sync_photos("fake.json", output)
    credentials.assert_called_once_with("fake.json", scopes=getPhotos.SCOPES)
    assert len(json.loads((output / "photos.json").read_text())) == 1
    logs = capsys.readouterr().out
    assert "1 approved images were inaccessible" in logs
    assert ID not in logs


def test_sync_fails_closed_to_empty_gallery_if_source_unavailable(monkeypatch, tmp_path, capsys):
    credentials = MagicMock(side_effect=PermissionError("private details"))
    monkeypatch.setattr(getPhotos.Credentials, "from_service_account_file", credentials)
    output = tmp_path / "photos"
    getPhotos.sync_photos("fake.json", output)
    assert json.loads((output / "photos.json").read_text()) == []
    logs = capsys.readouterr().out
    assert "publishing empty gallery" in logs
    assert "private details" not in logs


def test_legacy_moderation_headers_do_not_authorize_publication():
    category = "alumni_gatherings"
    fields, rows = responses(category, [
        ["11/25/2026", "VT", LINK, "Yes", "Group"],
    ])
    rows[0][-2:] = ["Approved", "Alt Text"]
    assert approvals.read_candidates(rows, fields, category, YEAR) == []


@pytest.mark.parametrize("release,expected", [
    (PHOTO_RELEASE_YES, True),
    ("  yes! YOU CAN SHARE MY PHOTO ON THE CWKC WEBPAGE.  ", True),
    ("Yes", False),
    ("No", False),
    ("", False),
    ("Yes, but do not publish my photo.", False),
])
def test_actual_hanukkah_release_answer(release, expected):
    category = "hanukkah_photos"
    fields = approvals.HANUKKAH_FIELDS
    rows = [HANUKKAH_HEADER + ["Image Approved", "Image Alt Text"],
            ["11/27/2026 11:53:21", "Synthetic attendee", "test@example.invalid",
             "Virginia Tech Hillel", "Yes", "2016", LINK, release, "Yes", "Synthetic candles"]]
    result = approvals.read_candidates(rows, fields, category, YEAR)
    assert result == ([approvals.ApprovedPhoto(ID, "vt", category, "Synthetic candles")]
                      if expected else [])
