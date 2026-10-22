"""Recovery, cancellation and full media validation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading

from .format import RepairError, boxes, discover, footer


class Cancelled(RepairError):
    pass


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def bundled_tools():
    # Resolve only relative to the application, never a developer's installation.
    folder = resource_root() / "vendor" / "ffmpeg" / "bin"
    result = tuple(folder / name for name in ("ffmpeg.exe", "ffprobe.exe"))
    if not all(p.is_file() for p in result):
        raise RepairError("The bundled video tools are missing. Extract or rebuild the complete app.")
    return result


def next_output(source, directory=None):
    source = Path(source)
    directory = Path(directory) if directory else source.parent
    suffix = 0
    while True:
        extra = f"-{suffix}" if suffix else ""
        path = directory / f"{source.stem}.recovered{extra}.mp4"
        if not path.exists() and not path.with_suffix(".repair.json").exists():
            return path
        suffix += 1


def file_hash(path, check=lambda: None):
    value = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            check()
            value.update(chunk)
    return value.hexdigest()


def run_tool(args, cancel, on_line=lambda line: None):
    """Drain stdout while keeping stderr bounded on disk; children have no console."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            [str(a) for a in args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=errors, text=True,
            encoding="utf-8", errors="replace", creationflags=flags,
        )
        lines = queue.Queue()

        def read():
            try:
                for line in process.stdout:
                    lines.put(line)
            finally:
                lines.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        output = []
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled("Conversion cancelled.")
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                output.append(line)
                on_line(line.strip())
            process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            reader.join(timeout=3)
            process.stdout.close()
        errors.seek(0, os.SEEK_END)
        length = errors.tell()
        errors.seek(max(0, length - 3000))
        error = errors.read().decode("utf-8", errors="replace").strip()
        if process.returncode or error:
            raise RepairError("Video validation failed. The cache may be incomplete.\n" + error)
        return "".join(output)


def recover(source, destination, notify=lambda message, fraction: None, cancel=None):
    cancel = cancel or threading.Event()

    def check():
        if cancel.is_set():
            raise Cancelled("Conversion cancelled.")

    check()
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    report_path = destination.with_suffix(".repair.json")
    if source == destination or destination.exists() or report_path.exists():
        raise RepairError("The output already exists. Choose a different name or folder.")
    if not source.is_file():
        raise RepairError("Select an MP4 file.")
    if source.name.lower().endswith(".alpha.mp4"):
        raise RepairError("Select the main cache MP4, rather than its alpha sidecar.")
    ffmpeg, ffprobe = bundled_tools()
    before = source.stat()
    notify("Reading the cache...", 0.03)
    data = source.read_bytes()
    check()
    if len(data) < 100:
        raise RepairError("The file is too small to contain a complete video.")
    original_hash = hashlib.sha256(data).hexdigest()
    version, target = footer(data)
    payload = data[:-68]
    del data
    key = payload[4] ^ ord("f")
    if bytes(b ^ key for b in payload[4:8]) != b"ftyp":
        raise RepairError("This cache header is not supported.")
    notify("Detecting the cache format...", 0.1)
    parameters = discover(payload, key, target, 45, notify, check)
    step, length = parameters if parameters else (len(payload), len(payload))
    notify("Restoring the video...", 0.25)
    decoded = bytearray(payload)
    del payload
    table = bytes(i ^ key for i in range(256))
    for pos in range(0, len(decoded), step):
        check()
        decoded[pos:pos + length] = decoded[pos:pos + length].translate(table)
        if pos % (step * 16) == 0:
            notify("Restoring the video...", 0.25 + 0.25 * pos / len(decoded))
    kinds = {name for name, _, _ in boxes(decoded)}
    if not {b"ftyp", b"moov", b"mdat"}.issubset(kinds):
        raise RepairError("The restored file has incomplete MP4 metadata.")
    output_hash = hashlib.sha256(decoded).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cache-repair-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "video.mp4"
        candidate.write_bytes(decoded)
        del decoded
        check()
        notify("Checking the video and audio...", 0.55)
        metadata = json.loads(run_tool([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", candidate], cancel))
        videos = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        if not videos:
            raise RepairError("No video stream was found in the restored file.")
        duration = float(metadata["format"].get("duration", 0))

        def progress(line):
            if line.startswith("out_time_us=") and duration > 0:
                try:
                    fraction = max(0, min(1, int(line.split("=", 1)[1]) / 1_000_000 / duration))
                    notify("Checking the video and audio...", 0.55 + fraction * 0.35)
                except ValueError:
                    pass

        output = run_tool([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-err_detect", "explode", "-i", candidate, "-map", "0:v?", "-map", "0:a?", "-progress", "pipe:1", "-nostats", "-f", "null", "-"], cancel, progress)
        frames = [int(line.split("=", 1)[1]) for line in output.splitlines() if line.startswith("frame=")]
        if not frames or frames[-1] < 1 or "progress=end" not in output:
            raise RepairError("The decoder did not confirm a complete video.")
        if len(videos) == 1 and str(videos[0].get("nb_frames", "")).isdigit() and frames[-1] != int(videos[0]["nb_frames"]):
            raise RepairError("The decoded frame count does not match the video metadata.")
        notify("Saving the verified MP4...", 0.93)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or file_hash(source, check) != original_hash:
            raise RepairError("The cache changed during conversion. Wait for preprocessing to finish.")
        check()
        metadata["format"]["filename"] = destination.name
        report = {
            "source_name": source.name, "output_name": destination.name,
            "source_sha256": original_hash, "output_sha256": output_hash,
            "source_unchanged": True, "bdve_type": 1, "bdve_version": version,
            "step": step if parameters else None, "length": length if parameters else None, "xor_key": key,
            "restoration": "periodic_xor" if parameters else "whole_payload_xor",
            "parameter_hash_verified": parameters is not None, "reencoded": False,
            "full_video_and_audio_decode_passed": True,
            "decoded_video_frames": frames[-1], "media": metadata,
        }
        published = []
        try:
            with destination.open("xb") as out:
                published.append(destination)
                with candidate.open("rb") as inp:
                    while block := inp.read(4 * 1024 * 1024):
                        check()
                        out.write(block)
            if file_hash(destination, check) != output_hash:
                raise RepairError("The saved output could not be verified.")
            with report_path.open("x", encoding="utf-8") as f:
                published.append(report_path)
                json.dump(report, f, indent=2)
                f.write("\n")
        except BaseException:
            for created in published:
                created.unlink(missing_ok=True)
            raise
    notify("Conversion complete", 1.0)
    return report
