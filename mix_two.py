#!/usr/bin/env python3
"""Sum two time-aligned 24-bit stereo WAVs into one, peak-normalised to -1 dBFS (two passes, chunked)."""
import sys, wave, numpy as np
A, B, OUT = sys.argv[1:4]; CH = 44100 * 30

def dec(b):
    a = np.frombuffer(b, np.uint8).reshape(-1, 3).astype(np.int32)
    s = a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16)
    return np.where(s >= 1 << 23, s - (1 << 24), s).astype(np.float64)

def enc(x):
    s = np.clip(np.round(x), -(1 << 23), (1 << 23) - 1).astype(np.int32) & 0xFFFFFF
    return np.stack([s & 0xFF, (s >> 8) & 0xFF, (s >> 16) & 0xFF], 1).astype(np.uint8).tobytes()

def chunks():
    a, b = wave.open(A), wave.open(B)
    assert a.getparams()[:3] == b.getparams()[:3] == (2, 3, 44100), "need 24-bit stereo 44.1k"
    n = min(a.getnframes(), b.getnframes())
    for i in range(0, n, CH):
        k = min(CH, n - i)
        yield dec(a.readframes(k)) + dec(b.readframes(k))

peak = max(np.abs(c).max() for c in chunks())
g = 0.891 * ((1 << 23) - 1) / peak
o = wave.open(OUT, "wb"); o.setnchannels(2); o.setsampwidth(3); o.setframerate(44100)
for c in chunks(): o.writeframes(enc(c * g))
o.close()
print(f"peak of sum {peak/2**23:.2f} FS, gain {20*np.log10(g):.1f} dB -> {OUT}")
