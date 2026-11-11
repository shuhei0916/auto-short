"""Synthesises the soundtrack from simulation events (no external assets)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .sim import Sim

SR = 44100
PENTATONIC = [0, 2, 4, 7, 9]
BASE = 261.63  # C4


def _freq(step: int) -> float:
    octave, idx = divmod(step, len(PENTATONIC))
    return BASE * 2 ** (octave + PENTATONIC[idx] / 12)


def _tone(freq: float, dur: float, decay: float, amp: float) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    env = np.exp(-t * decay) * np.minimum(1.0, t / 0.004)
    return amp * s * env


def _add(buf: np.ndarray, at: float, snd: np.ndarray) -> None:
    i = int(at * SR)
    n = min(len(snd), len(buf) - i)
    if n > 0:
        buf[i : i + n] += snd[:n]


def build_audio(sim: Sim, path: Path) -> None:
    rng = np.random.default_rng(sim.params.seed)
    buf = np.zeros(int(SR * sim.duration) + SR, dtype=np.float64)
    span = 3 * len(PENTATONIC) - 1
    last_bounce = -1.0
    i = 0
    for e in sim.events:
        if e["kind"] == "bounce":
            if e["t"] - last_bounce < 0.045:
                continue
            last_bounce = e["t"]
            pos = i % (2 * span)  # walk up and down the scale
            step = pos if pos <= span else 2 * span - pos
            _add(buf, e["t"], _tone(_freq(step), 0.45, 11.0, 0.5))
            i += 1
        else:
            root = e["ring"] % len(PENTATONIC)
            for off, amp in ((0, 0.5), (2, 0.4), (4, 0.35)):
                _add(buf, e["t"], _tone(_freq(root + off) / 2, 0.9, 5.0, amp))
            n = int(SR * 0.35)
            noise = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 14) * 0.35
            _add(buf, e["t"], noise)
    for j in range(6):  # finale arpeggio
        _add(buf, sim.finish_t + 0.09 * j, _tone(_freq(5 + 2 * j), 1.2, 4.0, 0.45))

    buf = buf[: int(SR * sim.duration)]
    buf = np.tanh(buf * 0.9)  # soft limiter
    pcm = (buf / max(1e-9, np.abs(buf).max()) * 0.89 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
