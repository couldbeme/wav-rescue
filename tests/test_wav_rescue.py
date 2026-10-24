import os, struct, subprocess, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

def wav_bytes(pcm, finalised=True, bits=16):
    ba = 2 * bits // 8
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 2, 44100, 44100 * ba, ba, bits)
    body = b"WAVE" + fmt + b"data" + struct.pack("<I", len(pcm) if finalised else 0) + pcm
    return b"RIFF" + struct.pack("<I", len(body) if finalised else 0) + body

def run(*a):
    return subprocess.run([PY, "-I", os.path.join(HERE, a[0]), *a[1:]], capture_output=True, text=True, check=True).stdout

def test_unfinalised_recording_is_recovered(tmp_path):
    pcm = os.urandom(3_000_000)
    img = tmp_path / "disk.img"; img.write_bytes(os.urandom(1003) + wav_bytes(pcm, finalised=False) + b"\0" * (70 << 20))
    out = run("carve_wav.py", "scan", str(img), str(tmp_path))
    assert '"offset": 1003' in out and '"riff_size": 0' in out
    run("carve_wav.py", "extract", str(img), "1003", str(tmp_path / "r.wav"))
    w = wave.open(str(tmp_path / "r.wav")); assert w.getnframes() * 4 == len(pcm)

def test_finalised_file_stops_at_declared_size(tmp_path):
    pcm = os.urandom(2_000_004)
    one = wav_bytes(pcm, bits=24 // 1 if False else 16)
    img = tmp_path / "disk.img"; img.write_bytes(os.urandom(777) + one + one + os.urandom(1 << 20))
    run("carve_wav.py", "extract", str(img), "777", str(tmp_path / "a.wav"))
    assert (tmp_path / "a.wav").read_bytes() == one

def _w24(path, x):
    s = np.clip(np.round(x), -(1 << 23), (1 << 23) - 1).astype(np.int32) & 0xFFFFFF
    b = np.stack([s & 0xFF, (s >> 8) & 0xFF, (s >> 16) & 0xFF], 1).astype(np.uint8).tobytes()
    w = wave.open(str(path), "wb"); w.setnchannels(2); w.setsampwidth(3); w.setframerate(44100); w.writeframes(b); w.close()

def test_mix_is_normalised_sum(tmp_path):
    t = np.arange(44100 * 2)
    a = np.round(np.repeat(0.5 * (1 << 23) * np.sin(t / 20), 2)); b = np.round(np.repeat(0.5 * (1 << 23) * np.sin(t / 7), 2))
    _w24(tmp_path / "a.wav", a); _w24(tmp_path / "b.wav", b)
    run("mix_two.py", str(tmp_path / "a.wav"), str(tmp_path / "b.wav"), str(tmp_path / "m.wav"))
    w = wave.open(str(tmp_path / "m.wav")); raw = np.frombuffer(w.readframes(w.getnframes()), np.uint8).reshape(-1, 3).astype(np.int32)
    s = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16); s = np.where(s >= 1 << 23, s - (1 << 24), s)
    assert abs(np.abs(s).max() / ((1 << 23) - 1) - 0.891) < 1e-3
    ref = (a + b) * (0.891 * ((1 << 23) - 1) / np.abs(a + b).max())
    assert np.abs(s - np.round(ref)).max() <= 1

def test_shared_burst_is_labelled_in_recording(tmp_path):
    rng = np.random.default_rng(0); n = 44100 * 4
    base = np.repeat(0.05 * (1 << 23) * np.sin(np.arange(n) / 30), 2)
    burst = slice(2 * 44100 * 2, 2 * 44100 * 2 + 2000)
    a, b = base.copy(), base.copy() * 0.8
    a[burst] = rng.choice([-1, 1], 2000) * 0.99 * (1 << 23); b[burst] = rng.choice([-1, 1], 2000) * 0.99 * (1 << 23)
    b[2 * 7 * 44100 // 2: 2 * 7 * 44100 // 2 + 2000] = rng.choice([-1, 1], 2000) * 0.99 * (1 << 23)
    _w24(tmp_path / "a.wav", a); _w24(tmp_path / "b.wav", b)
    out = run("check_splices.py", str(tmp_path / "a.wav"), str(tmp_path / "b.wav"))
    assert "in both files" in out and "only here" in out
