"""Optional portable native accelerator for ambiguous short-cache parameters."""
import ctypes
from pathlib import Path
import struct
import sys
import threading


def search(observations, first, last, key, digest, seconds, check_cancel):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    path = root / "vendor" / "parameter_search.dll"
    if not path.is_file():
        return None
    library = ctypes.CDLL(str(path))
    function = library.search_parameters
    function.argtypes = [ctypes.c_uint8, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_long), ctypes.POINTER(ctypes.c_uint32)]
    function.restype = ctypes.c_int
    count = len(observations)
    positions = (ctypes.c_uint64 * count)(*(p for p, _ in observations))
    states = (ctypes.c_uint8 * count)(*(bool(flag) for _, flag in observations))
    target = (ctypes.c_uint32 * 8)(*struct.unpack(">8I", digest))
    cancelled = ctypes.c_long(0)
    result = (ctypes.c_uint32 * 2)()
    finished = threading.Event()
    exceptions = []

    def watch():
        while not finished.wait(0.1):
            try:
                check_cancel()
            except Exception as exc:
                exceptions.append(exc)
                cancelled.value = 1
                return

    monitor = threading.Thread(target=watch, daemon=True)
    monitor.start()
    try:
        code = function(key, target, positions, states, count, first, last, int(seconds * 1000), ctypes.byref(cancelled), result)
    finally:
        finished.set()
        monitor.join()
    if exceptions:
        raise exceptions[0]
    check_cancel()
    if code == 0:
        return result[0], result[1]
    if code == 2:
        raise TimeoutError("Parameter discovery timed out. No output was saved.")
    return None
