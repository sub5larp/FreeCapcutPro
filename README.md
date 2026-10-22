# FreeCapcutPro

A tool which makes you able to export CapCut videos with Pro features for free. See [this video](https://www.youtube.com/watch?v=_bsmMfMyIeI) for the method. It is patched in newer CapCut versions, which report the clip as "damaged"; this tool makes supported cache videos usable again.

Download [CapCutCacheRepair.exe](https://github.com/sub5larp/FreeCapcutPro/releases/latest/download/CapCutCacheRepair.exe), drag in the preprocessed cache MP4, and click **Convert to MP4**. Windows x64; no Python installation needed. Originals are kept untouched. Supports complete BDVE Type 1 H.264 caches, including short clips; not every cache format is supported.

The [source ZIP](https://github.com/sub5larp/FreeCapcutPro/releases/latest/download/CapCutCacheRepair-source.zip) includes application source, build scripts, licenses, and FFmpeg source/build materials.

## Build

With Python 3.14 and Visual Studio C++ Build Tools on Windows x64:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts\build.py
```

Output: `dist/CapCutCacheRepair.exe`. Run `scripts/package_release.py` with the same Python to prepare the two release downloads.

Application code: MIT. Bundled components retain their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). Independent project, not affiliated with CapCut or ByteDance.
