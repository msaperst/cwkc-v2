"""Restore only a validated, season-matched gallery from the public data branch."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SEASON_CONFIG = Path("public/assets/config/season.json")

PHOTO_DIR = Path("public/assets/photos")
PHOTO_REF = "refs/remotes/origin/cwkc-photos"
CATEGORIES = {"alumni_gatherings", "hanukkah_photos"}
SCHOOLS = {"uva", "vt"}
IMAGE_PATH = re.compile(r"assets/photos/([a-f0-9]{64}\.jpg)")
MAX_IMAGE_SIZE = 25 * 1024 * 1024


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def read_snapshot_file(name: str) -> bytes:
    return git("show", f"{PHOTO_REF}:{PHOTO_DIR.as_posix()}/{name}")


def validate_snapshot(read, year: int, destination: Path) -> None:
    """Copy exactly the manifest and referenced content-addressed JPEGs."""
    if json.loads(read("season.json")) != {"year": year}:
        raise ValueError("Photo snapshot belongs to a different season")
    manifest = json.loads(read("photos.json"))
    if not isinstance(manifest, list):
        raise ValueError("Invalid photo manifest")
    copied = set()
    for entry in manifest:
        if (not isinstance(entry, dict) or set(entry) != {"school", "category", "src", "alt"}
                or entry["school"] not in SCHOOLS or entry["category"] not in CATEGORIES
                or not isinstance(entry["alt"], str) or not 0 < len(entry["alt"].strip()) <= 300):
            raise ValueError("Invalid photo manifest entry")
        match = IMAGE_PATH.fullmatch(entry["src"])
        if not match:
            raise ValueError("Invalid public photo path")
        name = match.group(1)
        if name in copied:
            continue
        payload = read(name)
        if (not 0 < len(payload) <= MAX_IMAGE_SIZE or not payload.startswith(b"\xff\xd8")
                or hashlib.sha256(payload).hexdigest() + ".jpg" != name):
            raise ValueError("Invalid public photo content")
        (destination / name).write_bytes(payload)
        copied.add(name)
    (destination / "photos.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                              encoding="utf-8")


def fetch_snapshot() -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", "refs/heads/cwkc-photos"],
        capture_output=True,
    )
    if result.returncode == 2:
        return False
    result.check_returncode()
    git("fetch", "--no-tags", "origin", f"refs/heads/cwkc-photos:{PHOTO_REF}")
    return True


def restore(year: int, destination: Path = PHOTO_DIR, *, enabled: bool) -> None:
    """Gallery problems must never block a scoreboard or code deployment."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "photos"
        staging.mkdir()
        try:
            if enabled and fetch_snapshot():
                validate_snapshot(read_snapshot_file, year, staging)
            else:
                (staging / "photos.json").write_text("[]\n", encoding="utf-8")
        except Exception:
            # Do not expose Git error payloads or any unvalidated snapshot.
            shutil.rmtree(staging)
            staging.mkdir()
            (staging / "photos.json").write_text("[]\n", encoding="utf-8")
            print("::warning::Photo snapshot unavailable or invalid; publishing empty gallery")
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)


def main():
    year = int(json.loads(SEASON_CONFIG.read_text(encoding="utf-8"))["year"])
    restore(year, enabled=os.getenv("CWKC_PHOTOS_ENABLED") == "true")


if __name__ == "__main__":
    main()
