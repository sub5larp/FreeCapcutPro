"""Collect pinned FFmpeg source and build recipes alongside release artifacts."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT / "scripts/source-lock.json").read_text())
    target = ROOT / "artifacts"
    target.mkdir(exist_ok=True)
    for name, item in lock.items():
        path = target / (name + "-source.zip")
        if not path.exists():
            request = urllib.request.Request(item["url"], headers={"User-Agent": "CacheRepair-build"})
            with urllib.request.urlopen(request, timeout=120) as inp, path.open("xb") as out:
                shutil.copyfileobj(inp, out)
        with path.open("rb") as inp:
            actual = hashlib.file_digest(inp, "sha256").hexdigest()
        if actual != item["sha256"]:
            raise RuntimeError(f"Source archive checksum mismatch: {name}")
        print(f"Verified {name} source archive.", flush=True)


if __name__ == "__main__":
    main()
