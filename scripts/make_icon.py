"""Generate the application's geometric icon with the Python standard library."""
from pathlib import Path
import struct
import zlib


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def main():
    size = 256
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            color = (16, 23, 34, 255)
            if 38 <= x <= 218 and 53 <= y <= 203:
                color = (114, 227, 193, 255)
            if 54 <= x <= 202 and 69 <= y <= 187:
                color = (25, 35, 49, 255)
            if 103 <= x <= 163 and abs(y - 128) <= (163 - x) * 0.7:
                color = (238, 243, 248, 255)
            for hole_y in (78, 111, 144, 177):
                if (39 <= x <= 49 or 207 <= x <= 217) and hole_y <= y < hole_y + 8:
                    color = (16, 23, 34, 255)
            rows.extend(color)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png
    output = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
    output.write_bytes(ico)


if __name__ == "__main__":
    main()
