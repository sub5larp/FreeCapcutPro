"""BDVE parsing and parameter discovery; no per-file presets."""
import hashlib
import struct
import time

class RepairError(Exception):
    pass


def digest_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def u32(data, offset=0):
    return struct.unpack_from(">I", data, offset)[0]


def boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    while start < end:
        if end - start < 8:
            raise RepairError("Incomplete MP4 box header.")
        size, name = struct.unpack_from(">I4s", data, start)
        header = 8
        if size == 1:
            if end - start < 16:
                raise RepairError("Incomplete extended MP4 box header.")
            size = struct.unpack_from(">Q", data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            raise RepairError("Invalid or incomplete MP4 box.")
        yield name, start + header, start + size
        start += size


def child(data, start, end, name):
    for kind, a, b in boxes(data, start, end):
        if kind == name:
            return a, b
    raise RepairError("Missing MP4 box: " + name.decode("ascii", errors="replace"))


def footer(data):
    # The footer is self-describing; unknown layouts are rejected.
    tail = data[-68:]
    if len(tail) != 68 or tail[:16] != struct.pack(">I4sI4s", 68, b"bdve", 48, b"crpt"):
        raise RepairError("No supported BDVE footer. This is not the cache format this tool repairs.")
    if tail[56:] != struct.pack(">I4sI", 12, b"size", 68):
        raise RepairError("Damaged BDVE footer.")
    kind, version = struct.unpack_from(">II", tail, 16)
    if kind != 1:
        raise RepairError(f"Unsupported BDVE cryptor type {kind}.")
    return version, tail[24:56]


def read_samples(data):
    """Read AVC sample locations from an intact moov, even with a scrambled ftyp."""
    cursor = 0
    while True:
        marker = data.find(b"moov", cursor)
        if marker < 0:
            raise RepairError("No intact AVC sample table available for automatic discovery.")
        cursor = marker + 4
        start = marker - 4
        if start < 0:
            continue
        end = start + u32(data, start)
        if end > len(data) or end < marker + 4:
            continue
        try:
            for name, a, b in boxes(data, marker + 4, end):
                if name != b"trak":
                    continue
                mdia = child(data, a, b, b"mdia")
                hdlr = child(data, *mdia, b"hdlr")
                if data[hdlr[0] + 8:hdlr[0] + 12] != b"vide":
                    continue
                minf = child(data, *mdia, b"minf")
                stbl = child(data, *minf, b"stbl")
                stsd = child(data, *stbl, b"stsd")
                if data[stsd[0] + 12:stsd[0] + 16] not in (b"avc1", b"avc3"):
                    continue
                avcc = data.find(b"avcC", stsd[0], stsd[1])
                if avcc < 0 or avcc + 9 > stsd[1] or (data[avcc + 8] & 3) != 3:
                    continue  # Discovery requires four-byte AVC NAL lengths.
                size_start, size_end = child(data, *stbl, b"stsz")
                if size_end - size_start < 12:
                    continue
                fixed, count = struct.unpack_from(">II", data, size_start + 4)
                if count > 10_000_000 or (not fixed and size_start + 12 + count * 4 > size_end):
                    continue
                sizes = [fixed] * count if fixed else list(struct.unpack_from(f">{count}I", data, size_start + 12))
                sc_start, sc_end = child(data, *stbl, b"stsc")
                n = u32(data, sc_start + 4)
                if not n or sc_start + 8 + n * 12 > sc_end:
                    continue
                runs = [struct.unpack_from(">III", data, sc_start + 8 + i * 12) for i in range(n)]
                if runs[0][0] != 1 or any(x[1] == 0 for x in runs):
                    continue
                try:
                    co_start, co_end = child(data, *stbl, b"stco")
                    width, fmt = 4, "I"
                except RepairError:
                    co_start, co_end = child(data, *stbl, b"co64")
                    width, fmt = 8, "Q"
                n = u32(data, co_start + 4)
                if co_start + 8 + n * width > co_end:
                    continue
                offsets = struct.unpack_from(f">{n}{fmt}", data, co_start + 8)
                result, sample, run = [], 0, 0
                for index, pos in enumerate(offsets, 1):
                    while run + 1 < len(runs) and runs[run + 1][0] <= index:
                        run += 1
                    for _ in range(runs[run][1]):
                        if sample >= count:
                            raise RepairError("Inconsistent MP4 sample table.")
                        size = sizes[sample]
                        if size < 5 or pos + size > len(data):
                            raise RepairError("Invalid AVC sample extent.")
                        result.append((pos, size))
                        pos += size
                        sample += 1
                if sample == count and result:
                    return sorted(result)
        except (RepairError, struct.error, IndexError):
            continue


def parameter_hash(step, length, key):
    return hashlib.sha256(struct.pack(">IIB", step, length, key)).digest()


def discover(data, key, target, seconds, notify=lambda message, fraction: None, check_cancel=lambda: None):
    table = bytes(i ^ key for i in range(256))
    try:
        samples = read_samples(data)
    except RepairError:
        samples = read_samples(data.translate(table))
    observations = [(0, True)]
    for pos, size in samples:
        raw = u32(data, pos)
        decoded = raw ^ (key * 0x01010101)
        plain_ok = 0 < raw <= size - 4
        xor_ok = 0 < decoded <= size - 4
        if plain_ok != xor_ok:
            observations.append((pos, xor_ok))
    lo, hi, cycle = 1, 5_000_000, 0
    for (pa, ea), (pb, eb) in zip(observations, observations[1:]):
        if not ea and eb:
            cycle += 1
            lo = max(lo, pa // cycle + 1)
            hi = min(hi, pb // cycle)
    if not any(not flag for _, flag in observations):
        # A cache can end before its first clear region. The period cannot be
        # inferred from absent bytes; validate a whole-payload restoration.
        return None
    if cycle < 1 or lo > hi:
        raise RepairError("This cache has too few visible boundaries to determine its partial scrambling pattern.")
    notify("Detecting the cache format...", 0.12)
    from .native import search
    accelerated = search(observations, lo, hi, key, target, seconds, check_cancel)
    if accelerated:
        if parameter_hash(*accelerated, key) != target:
            raise RepairError("Parameter verification failed.")
        return accelerated
    deadline, trials = time.monotonic() + seconds, 0
    for step in range(lo, hi + 1):
        check_cancel()
        if time.monotonic() > deadline:
            raise RepairError("Parameter discovery timed out; no output was published.")
        low, high = 1, step
        for pos, encrypted in observations:
            remainder = pos % step
            if encrypted:
                low = max(low, remainder + 1)
            else:
                high = min(high, remainder)
            if low > high:
                break
        for length in range(low, high + 1):
            if parameter_hash(step, length, key) == target:
                return step, length
            trials += 1
            if trials % 8192 == 0:
                check_cancel()
                if time.monotonic() > deadline:
                    raise RepairError("Parameter discovery timed out; no output was published.")
    raise RepairError("No parameters match the footer checksum. Unsupported or incomplete cache.")

