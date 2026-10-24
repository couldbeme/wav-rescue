#!/usr/bin/env python3
"""Read-only WAV carver for a raw device or disk image. Never writes to the source.
scan:    carve_wav.py scan <source> <out_dir>            -> lists every RIFF/WAVE header (offset, format, declared size)
extract: carve_wav.py extract <source> <offset> <out.wav> [--max-gb N]
         copies from the header until 64 MiB of silence-or-zeros or the declared size, then fixes the RIFF/data sizes in the copy."""
import os, struct, sys, json, time
CH = 8 << 20
_open = open   # replaced in tests

def _read(f, n):
    """Raw devices on Windows raise OSError at the end of the volume instead of returning b''."""
    try:
        return f.read(n)
    except OSError:
        return b""

def scan(src, out):
    os.makedirs(out, exist_ok=True)
    hits, pos, tail = [], 0, b""
    t0 = time.time()
    with _open(src, "rb", buffering=0) as f:
        while True:
            buf = _read(f, CH)
            if not buf: break
            data = tail + buf; base = pos - len(tail)
            i = data.find(b"RIFF")
            while i != -1:
                if i + 44 <= len(data) and data[i+8:i+12] == b"WAVE":
                    off = base + i
                    size = struct.unpack("<I", data[i+4:i+8])[0]
                    fmt = {}
                    j = data.find(b"fmt ", i, i + 512)
                    if j != -1 and j + 24 <= len(data):
                        tag, ch, sr = struct.unpack("<HHI", data[j+8:j+16]); bits = struct.unpack("<H", data[j+22:j+24])[0]
                        fmt = dict(tag=tag, channels=ch, rate=sr, bits=bits)
                    if off not in [h["offset"] for h in hits]:
                        hits.append(dict(offset=off, riff_size=size, **fmt)); print(json.dumps(hits[-1]), flush=True)
                i = data.find(b"RIFF", i + 1)
            tail = data[-64:]; pos += len(buf)
            if pos % (4 << 30) < CH: print(f"# {pos/2**30:.0f} GiB scanned, {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    json.dump(hits, open(os.path.join(out, "wav-headers.json"), "w"), indent=1)
    print(f"# done: {len(hits)} headers, {pos/2**30:.1f} GiB", file=sys.stderr)

def extract(src, off, dst, max_gb=8.0):
    blk = 512; start = off - off % blk; skip = off - start
    limit = int(max_gb * 2**30); zero_run = 0; written = 0
    with _open(src, "rb", buffering=0) as f, open(dst, "wb") as o:
        f.seek(start); hdr = _read(f, blk); f.seek(start)
        declared = struct.unpack("<I", hdr[skip+4:skip+8])[0] if len(hdr) >= skip + 8 else 0
        if 0 < declared < 0xFFFFFFF0: limit = min(limit, declared + 8)   # finalised file: copy exactly its declared size
        first = True
        while written < limit:
            buf = _read(f, CH)
            if not buf: break
            if first: buf = buf[skip:]; first = False
            buf = buf[:limit - written]
            o.write(buf); written += len(buf)
            zero_run = zero_run + len(buf) if buf.count(0) > 0.999 * len(buf) else 0
            if zero_run >= 64 << 20: break
    if 0 < declared < 0xFFFFFFF0:
        print(f"wrote {dst}: {written/2**20:.1f} MiB (declared size)"); return
    # trim trailing zero chunks, then fix header sizes in the copy
    with open(dst, "r+b") as o:
        size = os.path.getsize(dst); end = size
        while end > 44:
            o.seek(max(44, end - CH)); b = o.read(end - max(44, end - CH))
            nz = len(b.rstrip(b"\0"))
            if nz: end = max(44, end - CH) + nz; break
            end = max(44, end - CH)
        o.truncate(end)
        o.seek(0); head = o.read(4096); d = head.find(b"data")
        o.seek(4); o.write(struct.pack("<I", end - 8))
        if d != -1: o.seek(d + 4); o.write(struct.pack("<I", end - d - 8))
    print(f"wrote {dst}: {end/2**20:.1f} MiB")

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "scan": scan(a[1], a[2])
    elif a[0] == "extract": extract(a[1], int(a[2]), a[3], float(a[5]) if len(a) > 5 else 8.0)
