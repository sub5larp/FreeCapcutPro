# Third-party components

The application code is MIT-licensed. Included components retain their own
copyrights and licenses. License texts are in `licenses/` and inside the EXE.

| Component | License | Source |
| --- | --- | --- |
| Python | PSF license and included notices | https://github.com/python/cpython |
| Tcl/Tk | Tcl/Tk license | https://www.tcl.tk/software/tcltk/ |
| TkinterDnD2 / tkdnd | MIT and included notices | https://github.com/Eliav2/tkinterdnd2 |
| FFmpeg shared libraries and command-line tools | LGPL v3 or later, plus included dependency notices | https://ffmpeg.org/ |
| PyInstaller bootloader | GPL with distribution exception | https://pyinstaller.org/en/stable/license.html |

FFmpeg is invoked as a bundled subprocess, using unmodified shared DLLs.
The exact upstream archive and SHA-256 are recorded in
`scripts/ffmpeg-lock.json`. Its build configuration is available using the
bundled `ffmpeg.exe -buildconf`. Build recipes and dependency sources are
maintained by https://github.com/BtbN/FFmpeg-Builds.

The release source ZIP includes the pinned FFmpeg source snapshot and upstream
build recipes in `third_party/`. The recipes contain dependency source URLs and
build instructions. `scripts/collect_sources.py` verifies the source archives
against `scripts/source-lock.json`; `scripts/package_release.py` includes them
in the source ZIP.

BDVE format research reference:
https://github.com/pikadexofc/capcut-cache-recover/blob/main/capcut_cache_recover/cryptor.py
This project implements its own bounded parameter discovery and validation.
No upstream recovery package is installed at runtime.
