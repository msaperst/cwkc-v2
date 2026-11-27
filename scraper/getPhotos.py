"""Generate a public gallery from explicitly approved private Drive uploads."""
import hashlib
import io
import json
from pathlib import Path
import tempfile

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from PIL import Image, ImageOps

from .getGoogleFormData import SEASON_CONFIG
from .photo_approvals import approved_photos

MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 1600
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly",
          "https://www.googleapis.com/auth/drive.readonly"]


def download_photo(drive, file_id: str) -> bytes:
    resource = drive.files()
    metadata = resource.get(fileId=file_id, fields="size,mimeType,trashed",
                            supportsAllDrives=True).execute()
    if metadata.get("trashed") or metadata.get("mimeType") not in {
        "image/jpeg", "image/png", "image/webp"
    }:
        raise ValueError("Unsupported Drive photo type")
    size = int(metadata.get("size", 0))
    if not 0 < size <= MAX_BYTES:
        raise ValueError("Drive photo exceeds size limit or has no size")
    payload = resource.get_media(fileId=file_id, supportsAllDrives=True).execute()
    if not 0 < len(payload) <= MAX_BYTES or len(payload) != size:
        raise ValueError("Drive photo size mismatch")
    return payload


def optimize(payload: bytes) -> bytes:
    """Decode only supported raster formats, rotate, resize and discard metadata."""
    if not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("Invalid photo size")
    with Image.open(io.BytesIO(payload), formats=["JPEG", "PNG", "WEBP"]) as source:
        if source.width * source.height > MAX_PIXELS or getattr(source, "is_animated", False):
            raise ValueError("Unsupported photo dimensions or animation")
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
        clean = Image.new("RGB", image.size)
        clean.paste(image)
        output = io.BytesIO()
        clean.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue()


def generate(photos, download, destination: Path, year: int) -> tuple[int, int]:
    """Build in staging; replace the public directory only after validation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Photo generation requires an empty output directory")
    manifest = []
    failures = 0
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "photos"
        staging.mkdir()
        for photo in photos:
            # Do not log source IDs, filenames, request URLs or exception payloads.
            try:
                image = optimize(download(photo.file_id))
            except Exception:
                # Omit unreadable photos, including previously published ones.
                # A failed file must not block removal of revoked approvals.
                failures += 1
                continue
            filename = hashlib.sha256(image).hexdigest() + ".jpg"
            (staging / filename).write_bytes(image)
            entry = {"school": photo.school, "category": photo.category,
                     "src": "assets/photos/" + filename, "alt": photo.alt}
            if entry not in manifest:
                manifest.append(entry)
        manifest.sort(key=lambda item: (item["category"], item["school"], item["src"]))
        (staging / "photos.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                            encoding="utf-8")
        (staging / "season.json").write_text(json.dumps({"year": year}) + "\n",
                                             encoding="utf-8")
        staging.replace(destination)
    return len(manifest), failures


def sync_photos(credentials_file: str, output: Path):
    year = int(json.loads(SEASON_CONFIG.read_text(encoding="utf-8"))["year"])
    try:
        credentials = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
        client = gspread.authorize(credentials)
        photos = approved_photos(client, year)
        with build("drive", "v3", credentials=credentials, cache_discovery=False) as drive:
            count, failures = generate(photos, lambda file_id: download_photo(drive, file_id),
                                       output, year)
    except Exception:
        raise SystemExit("Photo sync failed; check private approval data and Drive access") from None
    print(f"Prepared {count} approved gallery images")
    if failures:
        print(f"::warning::{failures} approved images were inaccessible or unsupported; omitted from gallery")

