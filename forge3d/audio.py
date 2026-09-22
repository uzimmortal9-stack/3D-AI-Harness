"""Forge3D audio engine — synthesis, WAV mixing, and platform playback.

Dependency-free: synthesis + mixing in numpy, playback via OS tools
(winsound on Windows, afplay on macOS, aplay/paplay on Linux).
"""
import os
import struct
import subprocess
import sys
import wave

import numpy as np

SAMPLE_RATE = 22050


def synth(freq=440.0, duration=1.0, wave_kind="sine", volume=0.5, rate=SAMPLE_RATE):
    t = np.arange(int(rate * duration)) / rate
    if wave_kind == "sine":
        s = np.sin(2 * np.pi * freq * t)
    elif wave_kind == "square":
        s = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_kind == "saw":
        s = 2 * ((freq * t) % 1.0) - 1
    elif wave_kind == "noise":
        rng = np.random.default_rng(int(freq))
        s = rng.normal(0, 1, len(t))
    elif wave_kind == "chord":
        s = sum(np.sin(2 * np.pi * freq * m * t) for m in (1, 1.25, 1.5)) / 3
    else:
        raise ValueError(f"unknown wave '{wave_kind}'")
    # envelope to avoid clicks
    fade = max(4, int(rate * 0.01))
    env = np.ones_like(s)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return (s * env * volume).astype(np.float32)


def mix(parts, rate=SAMPLE_RATE):
    """parts: list of (samples, start_seconds). Returns float32 array."""
    end = max((int(rate * st) + len(s)) for s, st in parts) if parts else 0
    out = np.zeros(end, np.float32)
    for s, st in parts:
        i = int(rate * st)
        out[i:i + len(s)] += s
    return np.clip(out, -1, 1)


def write_wav(path, samples, rate=SAMPLE_RATE):
    pcm = (np.asarray(samples, np.float32) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        ch = w.getnchannels()
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, rate


def play(path, block=False):
    """Best-effort playback via OS tooling."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME |
                               (0 if block else winsound.SND_ASYNC))
            return True
        tool = "afplay" if sys.platform == "darwin" else \
            ("paplay" if _which("paplay") else "aplay")
        if _which(tool):
            subprocess.Popen([tool, "-q", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception:
        pass
    return False


def _which(cmd):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.exists(os.path.join(d, cmd)):
            return True
    return False
