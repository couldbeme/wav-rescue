#!/usr/bin/env python3
"""Find suspicious bursts in recovered 24-bit WAVs.
check_splices.py a.wav [b.wav]
A recovery splice (foreign data stitched in) shows up as a dense run of extreme sample jumps in one file.
With two simultaneous recordings, a burst found at the same moment in both is in the recording itself."""
import sys, wave, numpy as np

def regions(path):
    w = wave.open(path); sr = w.getframerate(); ch = w.getnchannels()
    assert w.getsampwidth() == 3, "24-bit WAV expected"
    raw = np.frombuffer(w.readframes(w.getnframes()), np.uint8)
    a = raw[: len(raw) // 3 * 3].reshape(-1, 3).astype(np.int32)
    s = a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16); s = np.where(s >= 1 << 23, s - (1 << 24), s)
    x = s[0::ch].astype(np.float64)
    d = np.abs(np.diff(x)); thr = min(np.percentile(d, 99.99) * 3, 0.4 * (1 << 24))   # adjacent-sample jump of 40% of full range: not music
    reg = []
    for i in np.nonzero(d > thr)[0]:
        if reg and i - reg[-1][1] < sr: reg[-1][1] = i; reg[-1][2] += 1
        else: reg.append([i, i, 1])
    return sr, [(r0 / sr, (r1 - r0) / sr, c) for r0, r1, c in reg]

def main(paths):
    found = {p: regions(p)[1] for p in paths}
    for p, reg in found.items():
        others = [q for q in paths if q != p]
        print(f"{p}: {len(reg)} burst region(s)")
        for t, dur, c in reg:
            shared = any(abs(t - t2) < 0.05 for q in others for t2, _, _ in found[q])
            tag = "in both files -> in the recording" if shared else ("only here -> listen" if others else "")
            print(f"  {int(t//60):02d}:{t%60:05.2f}  {dur*1000:6.1f} ms  {c} jumps  {tag}")

if __name__ == "__main__":
    main(sys.argv[1:])
