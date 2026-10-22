# Build from any checkout path using the pinned development requirements.
from pathlib import Path

root = Path(SPECPATH)
binary_dir = root / 'vendor' / 'ffmpeg' / 'bin'
# Treat the complete self-contained FFmpeg directory as data. PyInstaller's
# dependency scanner otherwise duplicates its DLLs at the archive root.
media_files = [(str(p), 'vendor/ffmpeg/bin') for p in binary_dir.iterdir()
               if p.suffix.lower() == '.dll' or p.name in ('ffmpeg.exe', 'ffprobe.exe')]
data = [(str(root / 'assets'), 'assets'),
        (str(root / 'vendor/parameter_search.dll'), 'vendor'),
        (str(root / 'licenses'), 'licenses'),
        (str(root / 'THIRD_PARTY.md'), '.'),
        (str(root / 'vendor/ffmpeg/LICENSE.txt'), 'vendor/ffmpeg'),
        (str(root / 'vendor/ffmpeg/origin.json'), 'vendor/ffmpeg')] + media_files
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=[],
             datas=data, hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False, optimize=1)
# Preserve media files as data even if the initial classification sees a PE.
# Their upstream folder is complete, and is exercised by packaged-EXE tests.
for item in list(a.binaries):
    if item[0].replace('\\', '/').startswith('vendor/ffmpeg/bin/'):
        a.binaries.remove(item)
        a.datas.append((item[0], item[1], 'DATA'))
media_names = {p.name for p in binary_dir.glob('*.dll')}
a.binaries = [item for item in a.binaries if item[0] not in media_names]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CapCutCacheRepair',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'assets/app.ico'),
          version=str(root / 'assets/version-info.txt'))
