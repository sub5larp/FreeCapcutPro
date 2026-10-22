"""Include the installed runtime components' license texts in each build."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "licenses"
    target.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        raise RuntimeError("Python runtime license was not found")
    shutil.copyfile(python_license, target / "Python.txt")
    for package in ("tkinterdnd2", "pyinstaller"):
        distribution = importlib.metadata.distribution(package)
        for item in distribution.files:
            if "license" in str(item).lower() or "copying" in str(item).lower():
                path = Path(distribution.locate_file(item))
                if path.is_file():
                    name = package + "-" + str(item).replace("/", "_").replace("\\", "_")
                    shutil.copyfile(path, target / name)
    for name in ("tcl8.6", "tk8.6", "tcl9.0", "tk9.0"):
        base = Path(sys.base_prefix) / "tcl" / name
        for filename in ("license.terms", "license.txt"):
            path = base / filename
            if path.exists():
                shutil.copyfile(path, target / f"{name}.txt")
    shutil.copyfile(ROOT / "vendor/ffmpeg/LICENSE.txt", target / "FFmpeg-LGPL.txt")


if __name__ == "__main__":
    main()
