"""Plinko: balls drop one by one through a peg triangle and pile up into a bell curve.

Drops start slow and speed up. Deterministic per (seed, attempt).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

CX = 540.0
FPS = 60
SUBSTEPS = 8
TOP_Y = 480.0  # first peg row
ROW_DY = 62.0
DX = 84.0
BALL_R = 11.0
PEG_R = 9.0
GRAVITY = 2400.0
REST = 0.5
HDAMP = 0.55
SLOT_COLS = 3
SLOT_DY = 21.0
ROW_HEIGHT_PER_BIN = 1.0


@dataclass
class PlinkoParams:
    seed: int
    attempt: int
    rows: int
    n_balls: int
    hue0: float
    hue_span: float
    bounce_jitter: float
    fmt: str = "plinko"

    @property
    def n_rings(self) -> int:  # name used by hooks/titles
        return self.n_balls

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlinkoSim:
    params: PlinkoParams
    balls: list[dict]  # {start, pts, bin, slot, land}: frame indices, path, final slot
    events: list[dict]
    finish_t: float
    final_counts: list[int]
    n_frames: int
    floor_y: float

    @property
    def duration(self) -> float:
        return self.n_frames / FPS


def board(rows: int):
    pegs = [
        (CX + (j - i / 2) * DX, TOP_Y + i * ROW_DY)
        for i in range(rows)
        for j in range(i + 1)
    ]
    bottom = TOP_Y + (rows - 1) * ROW_DY
    bins_top = bottom + 70
    floor = bins_top + 300
    return pegs, bins_top, floor


def bin_x(rows: int, k: int) -> float:
    return CX + (k - rows / 2) * DX


def slot_pos(rows: int, k: int, count: int, floor: float) -> tuple[float, float]:
    col, lvl = count % SLOT_COLS, count // SLOT_COLS
    x = bin_x(rows, k) + (col - (SLOT_COLS - 1) / 2) * (DX - 14) / SLOT_COLS
    return x, floor - BALL_R - 2 - lvl * SLOT_DY


def make_params(seed: int, attempt: int = 0) -> PlinkoParams:
    style = random.Random(seed + 900_000)
    return PlinkoParams(
        seed=seed,
        attempt=attempt,
        rows=style.randint(8, 10),
        n_balls=style.choice([90, 110, 130, 150]),
        hue0=style.random(),
        hue_span=style.choice([0.3, 0.45, -0.35]),
        bounce_jitter=style.uniform(0.04, 0.12),
    )


def drop_times(n: int) -> list[float]:
    t, out = 0.6, []
    for i in range(n):
        out.append(t)
        t += max(0.07, 0.55 * 0.93**i)
    return out


def simulate(p: PlinkoParams) -> PlinkoSim:
    rng = random.Random(p.seed * 7919 + p.attempt + 1)
    pegs, bins_top, floor = board(p.rows)
    by_row = [[q for q in pegs if abs(q[1] - (TOP_Y + i * ROW_DY)) < 1] for i in range(p.rows)]
    dt = 1.0 / (FPS * SUBSTEPS)
    counts = [0] * (p.rows + 1)
    balls, events = [], []
    last_land = 0
    for t0 in drop_times(p.n_balls):
        start = int(t0 * FPS)
        x, y = CX + rng.uniform(-2.5, 2.5), TOP_Y - 100
        vx, vy = rng.uniform(-8, 8), 0.0
        pts, step = [], 0
        k = slot = None
        while True:
            if step % SUBSTEPS == 0:
                pts.append((x, y))
            tt = (start * SUBSTEPS + step) * dt
            step += 1
            if k is None:
                vy += GRAVITY * dt
                x += vx * dt
                y += vy * dt
                row = int((y - TOP_Y) / ROW_DY + 0.5)
                for r in (row - 1, row, row + 1):
                    if not 0 <= r < p.rows:
                        continue
                    for px, py in by_row[r]:
                        dx, dy = x - px, y - py
                        d = math.hypot(dx, dy)
                        if d < BALL_R + PEG_R and d > 0:
                            nx, ny = dx / d, dy / d
                            vn = vx * nx + vy * ny
                            if vn < 0:
                                vx -= (1 + REST) * vn * nx
                                vy -= (1 + REST) * vn * ny
                                vx = vx * HDAMP + rng.uniform(-1, 1) * p.bounce_jitter * 400
                                events.append({"t": tt, "kind": "bounce", "ring": 0, "x": x, "y": y})
                            x, y = px + nx * (BALL_R + PEG_R), py + ny * (BALL_R + PEG_R)
                if y >= bins_top:
                    k = min(p.rows, max(0, int(round((x - CX) / DX + p.rows / 2))))
                    slot = slot_pos(p.rows, k, counts[k], floor)
                    counts[k] += 1
                    vy = max(vy, 300.0)
            else:
                vy += GRAVITY * dt
                y += vy * dt
                x += (slot[0] - x) * min(1.0, 14 * dt)
                if y >= slot[1]:
                    pts.append(slot)
                    events.append({"t": tt, "kind": "bounce", "ring": 0, "x": slot[0], "y": slot[1]})
                    break
        balls.append({"start": start, "pts": pts, "bin": k, "slot": slot, "land": start + len(pts) - 1})
        last_land = max(last_land, start + len(pts) - 1)
    events.sort(key=lambda e: e["t"])
    finish = (last_land + 1) / FPS
    events.append({"t": finish, "kind": "break", "ring": 0, "x": CX, "y": floor})
    n_frames = int((finish + 3.0) * FPS)
    return PlinkoSim(p, balls, events, finish, counts, n_frames, floor)


def quality_ok(sim: PlinkoSim) -> tuple[bool, str]:
    if not 15.0 <= sim.duration <= 40.0:
        return False, f"duration={sim.duration:.1f}s outside 15-40s"
    c = sim.final_counts
    n = sim.params.n_balls
    if c[0] + c[-1] > 0.12 * n:
        return False, "too many balls on the edges"
    if max(c) < 0.16 * n:
        return False, "no clear peak"
    return True, "ok"
