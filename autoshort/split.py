"""Split: one ball bounces around a round arena and clones itself on some bounces.

The count explodes (1, 2, 4, ... N) until the arena is full of balls. Each clone
generation has its own hue. Balls do not collide with each other (cheap, and it
keeps the swarm flowing). Deterministic per (seed, attempt).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

FPS = 60
SUBSTEPS = 4
TAU = math.tau
ARENA_R = 440.0
SPEED = 760.0


@dataclass
class SplitParams:
    seed: int
    attempt: int
    n_balls: int
    ball_r: float
    split_p: float
    hue0: float
    hue_step: float
    arena_r: float = ARENA_R
    fmt: str = "split"

    @property
    def n_rings(self) -> int:  # name used by hooks/titles
        return self.n_balls

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SplitSim:
    params: SplitParams
    frames: list[list[tuple[float, float, int]]]  # per frame: (x, y, generation) per ball
    counts: list[int]  # ball count per frame
    events: list[dict]
    finish_t: float

    @property
    def duration(self) -> float:
        return len(self.frames) / FPS


def make_params(seed: int, attempt: int = 0) -> SplitParams:
    style = random.Random(seed + 700_000)
    return SplitParams(
        seed=seed,
        attempt=attempt,
        n_balls=style.choice([120, 160, 200]),
        ball_r=style.choice([20.0, 22.0, 24.0]),
        split_p=style.uniform(0.12, 0.2),
        hue0=style.random(),
        hue_step=style.choice([0.045, 0.06, -0.05]),
    )


def simulate(p: SplitParams, max_seconds: float = 38.0, tail: float = 2.6) -> SplitSim | None:
    rng = random.Random(p.seed * 7919 + p.attempt + 1)
    dt = 1.0 / (FPS * SUBSTEPS)
    wall = p.arena_r - p.ball_r - 5.0
    a = rng.uniform(0, TAU)
    # ball: [x, y, vx, vy, generation]
    balls = [[0.0, -20.0, SPEED * math.cos(a), SPEED * math.sin(a), 0]]
    frames, counts, events = [], [], []
    finish = None
    step = 0
    while True:
        if step % SUBSTEPS == 0:
            frames.append([(b[0], b[1], b[4]) for b in balls])
            counts.append(len(balls))
        t = step * dt
        step += 1
        if finish is not None and t >= finish + tail:
            break
        if t > max_seconds:
            return None
        new = []
        for b in balls:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            d = math.hypot(b[0], b[1])
            if d < wall:
                continue
            nx, ny = b[0] / d, b[1] / d
            vn = b[2] * nx + b[3] * ny
            if vn > 0:
                b[2] -= 2 * vn * nx
                b[3] -= 2 * vn * ny
            b[0], b[1] = nx * wall, ny * wall
            prob = p.split_p + (1 - p.split_p) * max(0.0, 1 - len(balls) / 6)  # early splits come fast
            if finish is None and len(balls) + len(new) < p.n_balls and rng.random() < prob:
                ang = math.atan2(-ny, -nx) + rng.uniform(-1.3, 1.3)  # fan out inward
                b[4] += 1
                new.append([b[0], b[1], SPEED * math.cos(ang), SPEED * math.sin(ang), b[4]])
                events.append({"t": t, "kind": "bounce", "ring": 0, "x": b[0], "y": b[1]})
        balls.extend(new)
        if finish is None and len(balls) >= p.n_balls:
            finish = t
            events.append({"t": t, "kind": "break", "ring": 0, "x": 0.0, "y": 0.0})
    return SplitSim(p, frames, counts, events, finish)


def quality_ok(sim: SplitSim) -> tuple[bool, str]:
    if not 15.0 <= sim.duration <= 40.0:
        return False, f"duration={sim.duration:.1f}s outside 15-40s"
    if not 12.0 <= sim.finish_t <= 34.0:
        return False, f"finish_t={sim.finish_t:.1f}s outside 12-34s"
    i = int(sim.finish_t * FPS / 3)
    if not 1 < sim.counts[i] < sim.params.n_balls * 0.6:
        return False, "growth too front- or back-loaded"
    return True, "ok"
