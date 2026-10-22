"""Build the portable Windows executable from a clean checkout."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Build the Windows EXE on Windows.")
    for script in ("fetch_ffmpeg.py", "build_native.py", "make_icon.py", "collect_licenses.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(args.output_dir.resolve()), str(ROOT / "CacheRepair.spec")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
