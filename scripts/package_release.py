"""Package the standalone executable and source archive for a release."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ("app.py", "cache_repair", "native", "scripts", "assets", "licenses", ".gitignore", "CacheRepair.spec", "requirements-build.txt", "README.md", "THIRD_PARTY.md", "LICENSE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "dist" / "CapCutCacheRepair.exe")
    args = parser.parse_args()
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    executable = args.exe.resolve(strict=True)
    release_executable = output / "CapCutCacheRepair.exe"
    if executable != release_executable.resolve():
        shutil.copyfile(executable, release_executable)
    subprocess.run([sys.executable, str(ROOT / "scripts/collect_sources.py")], check=True)
    source = output / "CapCutCacheRepair-source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as z:
        for name in INCLUDE:
            entry = ROOT / name
            for path in ([entry] if entry.is_file() else sorted(entry.rglob("*"))):
                if path.is_file() and "__pycache__" not in path.parts:
                    z.write(path, path.relative_to(ROOT).as_posix())
        lock = json.loads((ROOT / "scripts/source-lock.json").read_text())
        for name in lock:
            archive = output / (name + "-source.zip")
            z.write(archive, "third_party/" + archive.name, compress_type=zipfile.ZIP_STORED)
    for path in (release_executable, source):
        with path.open("rb") as f:
            print(hashlib.file_digest(f, "sha256").hexdigest() + "  " + path.name)
    print("Release uploads: CapCutCacheRepair.exe and CapCutCacheRepair-source.zip")


if __name__ == "__main__":
    main()
