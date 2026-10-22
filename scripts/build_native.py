"""Build the baseline-x64 search accelerator with the installed MSVC tools."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    vswhere = Path(os.environ.get("ProgramFiles(x86)", os.environ["ProgramFiles"])) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    installation = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    if not installation:
        raise RuntimeError("Install Visual Studio Build Tools with Desktop development with C++.")
    versions = Path(installation) / "VC" / "Tools" / "MSVC"
    compiler_root = max(versions.iterdir(), key=lambda p: tuple(int(v) for v in p.name.split(".")))
    binaries = compiler_root / "bin" / "Hostx64" / "x64"
    work = ROOT / "build" / "native"
    work.mkdir(parents=True, exist_ok=True)
    output = ROOT / "vendor" / "parameter_search.dll"
    output.parent.mkdir(exist_ok=True)
    (work / "kernel32.def").write_text("LIBRARY KERNEL32.dll\nEXPORTS\nGetTickCount64\nGetActiveProcessorCount\nCreateThread\nWaitForSingleObject\nCloseHandle\n")
    env = os.environ.copy()
    env["INCLUDE"] = str(compiler_root / "include")
    env["PATH"] = str(binaries) + os.pathsep + env.get("PATH", "")
    subprocess.run([str(binaries / "lib.exe"), "/nologo", "/def:kernel32.def", "/machine:x64", "/out:kernel32.lib"], cwd=work, env=env, check=True)
    subprocess.run([str(binaries / "cl.exe"), "/nologo", "/O2", "/GL", "/Oi", "/GS-", "/Zl", "/std:c++17", "/LD", str(ROOT / "native/parameter_search.cpp"), "kernel32.lib", "/link", "/NODEFAULTLIB", "/NOENTRY", "/LTCG", "/OUT:" + str(output)], cwd=work, env=env, check=True)



if __name__ == "__main__":
    main()
