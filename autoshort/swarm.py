"""Swarm: one ball in a ring. Bounces sometimes split it in two, until the ring is packed.

Balls do not collide with each other (cheap, and it looks like a glowing cloud).
Deterministic per (seed, attempt).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

CX, CY = 540.0, 930.0
FPS = 60
SUBSTEPS = 6
WALL = 430.0
BALL_R = 13.0
MIN_INWARD = 240.0
VMAX = 1300.0
TAIL = 2.5


@dataclass
class SwarmParams:
    seed: int
    attempt: int
    target: int
    split_p: float
    gravity: float
    hue0: float
    hue_span: float
    wall: float = WALL
    fmt: str = "swarm"

    @property
    def ball_r(self) -> float:  # sized so the final swarm covers ~30% of the ring
        return self.wall * math.sqrt(0.3 / self.target)

    @property
    def n_rings(self) -> int:  # name used by hooks/titles
        return self.target

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SwarmSim:
    params: SwarmParams
    frames: list[list[tuple[float, float]]]  # per frame: ball positions (relative to ring centre)
    counts: list[int]
    events: list[dict]
    finish_t: float

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def duration(self) -> float:
        return self.n_frames / FPS


def make_params(seed: int, attempt: int = 0) -> SwarmParams:
    style = random.Random(seed + 700_000)
    rng = random.Random(seed * 7919 + attempt + 1)
    return SwarmParams(
        seed=seed,
        attempt=attempt,
        target=style.choice([100, 150, 200, 250]),
        split_p=rng.uniform(0.10, 0.22),
        gravity=style.choice([1200.0, 1600.0, 2000.0]),
        hue0=style.random(),
        hue_span=style.choice([0.25, 0.4, -0.3]),
    )


def simulate(p: SwarmParams, max_seconds: float = 40.0) -> SwarmSim | None:
    rng = random.Random(p.seed * 104729 + p.attempt + 1)
    dt = 1.0 / (FPS * SUBSTEPS)
    lim = p.wall - p.ball_r
    a = rng.uniform(0, math.tau)
    balls = [[0.0, -20.0, 450.0 * math.cos(a), 450.0 * math.sin(a)]]
    frames, counts, events = [], [], []
    finish: float | None = None
    step, t = 0, 0.0
    while True:
        if step % SUBSTEPS == 0:
            frames.append([(b[0], b[1]) for b in balls])
            counts.append(len(balls))
            if finish is not None and t >= finish + TAIL:
                break
            if finish is None and t > max_seconds:
                return None
        t += dt
        step += 1
        for b in list(balls):
            b[3] += p.gravity * dt
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            d = math.hypot(b[0], b[1])
            if d < lim or d == 0:
                continue
            nx, ny = b[0] / d, b[1] / d
            vn = b[2] * nx + b[3] * ny
            if vn <= 0:
                continue
            b[2] -= 2 * vn * nx
            b[3] -= 2 * vn * ny
            inward = -(b[2] * nx + b[3] * ny)
            if inward < MIN_INWARD:
                b[2] -= nx * (MIN_INWARD - inward)
                b[3] -= ny * (MIN_INWARD - inward)
            sp = math.hypot(b[2], b[3])
            if sp > VMAX:
                b[2] *= VMAX / sp
                b[3] *= VMAX / sp
            b[0], b[1] = nx * lim, ny * lim
            if finish is not None:
                continue
            events.append({"t": t, "kind": "bounce", "ring": 0, "x": b[0], "y": b[1]})
            if rng.random() < p.split_p:
                ang = rng.uniform(-0.6, 0.6)
                c, s = math.cos(ang), math.sin(ang)
                balls.append([b[0], b[1], b[2] * c - b[3] * s, b[2] * s + b[3] * c])
                if len(balls) >= p.target:
                    finish = t
                    events.append({"t": t, "kind": "break", "ring": 0, "x": 0.0, "y": 0.0})
    return SwarmSim(p, frames, counts, events, finish)


def quality_ok(sim: SwarmSim) -> tuple[bool, str]:
    if not 15.0 <= sim.duration <= 40.0:
        return False, f"duration={sim.duration:.1f}s outside 15-40s"
    if not 13.0 <= sim.finish_t <= 34.0:
        return False, f"finish_t={sim.finish_t:.1f}s outside 13-34s"
    if sim.counts[int(3 * FPS)] < 3:
        return False, "too slow to start"
    return True, "ok"
