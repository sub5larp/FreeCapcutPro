"""Desktop entry point, with a headless conversion option for automation."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="CapCut Cache Repair")
    parser.add_argument("file", nargs="?", help="Preselect a cache MP4 in the GUI")
    parser.add_argument("--convert", type=Path, help="Convert without opening the GUI")
    parser.add_argument("--output", type=Path, help="Destination for --convert")
    parser.add_argument("--result", type=Path, help="Write a machine-readable success or failure result")
    args = parser.parse_args()
    if args.convert:
        from cache_repair.engine import next_output, recover
        try:
            output = args.output or next_output(args.convert)
            report = recover(args.convert, output)
            result, code = {"ok": True, "output": str(output), "report": report}, 0
        except Exception as exc:
            result, code = {"ok": False, "error": str(exc)}, 1
        if args.result:
            with args.result.open("x", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        if sys.stdout:
            print(json.dumps(result))
        return code
    from cache_repair.gui import App
    App(args.file).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
