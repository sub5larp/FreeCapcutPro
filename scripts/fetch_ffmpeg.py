"""Download a checksum-pinned LGPL shared build. This runs only at build time."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT / "scripts" / "ffmpeg-lock.json").read_text())
    downloads = ROOT / ".downloads"
    downloads.mkdir(exist_ok=True)
    archive = downloads / lock["name"]
    if not archive.exists():
        print("Downloading the pinned FFmpeg build...", flush=True)
        request = urllib.request.Request(lock["url"], headers={"User-Agent": "CacheRepair-build"})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("xb") as out:
            shutil.copyfileobj(response, out)
    with archive.open("rb") as inp:
        actual = hashlib.file_digest(inp, "sha256").hexdigest()
    if actual != lock["sha256"]:
        raise RuntimeError("FFmpeg archive checksum does not match scripts/ffmpeg-lock.json")
    target = ROOT / "vendor" / "ffmpeg"
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            parts = Path(entry.filename).parts
            if len(parts) < 2 or entry.is_dir():
                continue
            relative = Path(*parts[1:])
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unsafe archive member")
            # Keep binaries and the original licenses/build documentation.
            if relative.parts[0] in ("include", "lib"):
                continue
            output = target / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry) as inp, output.open("wb") as out:
                shutil.copyfileobj(inp, out)
    if not (target / "bin" / "ffmpeg.exe").is_file():
        raise RuntimeError("FFmpeg was not found in the extracted package")
    (target / "origin.json").write_text(json.dumps(lock, indent=2) + "\n")
    print("FFmpeg download and checksum verified.", flush=True)


if __name__ == "__main__":
    main()
