"""Ring Escape: a ball bounces inside concentric rotating rings, each with a gap.

Passing through a gap destroys that ring. The video ends when every ring is gone.
The simulation is deterministic for a given (seed, attempt).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

W, H = 1080, 1920
CX, CY = 540.0, 930.0
FPS = 60
SUBSTEPS = 8
TAU = math.tau
FORMATS = ("ring_escape", "ball_grow")


@dataclass
class Params:
    seed: int
    attempt: int
    n_rings: int
    radii: list[float]
    gaps: list[float]  # radians
    omegas: list[float]  # rad/s
    phases: list[float]
    thickness: float
    gravity: float
    ball_r: float
    v0: tuple[float, float]
    speedup: float
    vmax: float
    hue0: float
    hue_span: float
    fmt: str = "ring_escape"
    growth: float = 0.0  # ball_grow: radius added per bounce

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sim:
    params: Params
    frames: list[tuple[float, float]]  # ball position per frame, relative to centre
    broken: list[int]  # rings destroyed so far, per frame
    events: list[dict]  # {t, kind: bounce|break, ring, x, y}
    finish_t: float
    radius: list[float]  # ball radius per frame
    bounces: list[int]  # bounce count per frame

    @property
    def duration(self) -> float:
        return len(self.frames) / FPS


def make_params(seed: int, attempt: int = 0, fmt: str = "ring_escape") -> Params:
    if fmt == "ball_grow":
        return _make_params_grow(seed, attempt)
    # Look-and-feel depends on the seed only; retries change just the initial conditions.
    style = random.Random(seed)
    rng = random.Random(seed * 7919 + attempt + 1)

    n = style.randint(6, 10)
    r0, r1 = 120.0, 490.0
    radii = [r0 + (r1 - r0) * k / (n - 1) for k in range(n)]
    base_gap = style.uniform(42.0, 62.0)
    gaps = [math.radians(base_gap * (r0 / r) ** 0.3) for r in radii]
    w = style.uniform(0.6, 1.4)
    direction = style.choice([1, -1])
    omegas = [direction * (-1) ** k * w * style.uniform(0.8, 1.25) for k in range(n)]
    phases = [rng.uniform(0, TAU) for _ in range(n)]
    a = rng.uniform(0, TAU)
    return Params(
        seed=seed,
        attempt=attempt,
        n_rings=n,
        radii=radii,
        gaps=gaps,
        omegas=omegas,
        phases=phases,
        thickness=9.0,
        gravity=style.choice([1400.0, 1800.0, 2200.0]),
        ball_r=16.0,
        v0=(500.0 * math.cos(a), 500.0 * math.sin(a)),
        speedup=1.012,
        vmax=1500.0,
        hue0=style.random(),
        hue_span=style.choice([0.25, 0.4, 0.6, -0.3]),
    )


def _make_params_grow(seed: int, attempt: int) -> Params:
    style = random.Random(seed + 500_000)
    rng = random.Random(seed * 7919 + attempt + 1)
    a = rng.uniform(0, TAU)
    return Params(
        seed=seed,
        attempt=attempt,
        n_rings=1,
        radii=[440.0],
        gaps=[0.0],
        omegas=[0.0],
        phases=[0.0],
        thickness=10.0,
        gravity=style.choice([1400.0, 1800.0, 2200.0]),
        ball_r=18.0,
        v0=(500.0 * math.cos(a), 500.0 * math.sin(a)),
        speedup=1.01,
        vmax=1500.0,
        hue0=style.random(),
        hue_span=0.0,
        fmt="ball_grow",
        growth=style.uniform(5.0, 9.0),
    )


def _simulate_grow(p: Params, max_seconds: float, tail: float) -> Sim | None:
    """One closed ring. The ball grows on every bounce until it fills the ring."""
    dt = 1.0 / (FPS * SUBSTEPS)
    wall = p.radii[0] - p.thickness / 2
    x, y = 0.0, -20.0
    vx, vy = p.v0
    r = p.ball_r
    nb = 0
    events: list[dict] = []
    frames, broken_f, radius_f, bounces_f = [], [], [], []
    finish: float | None = None
    step = 0
    t = 0.0
    min_inward = 260.0

    while True:
        if step % SUBSTEPS == 0:
            frames.append((x, y))
            broken_f.append(0 if finish is None else 1)
            radius_f.append(r)
            bounces_f.append(nb)
            if finish is not None and t >= finish + tail:
                break
            if finish is None and t > max_seconds:
                return None
        t += dt
        step += 1
        if finish is not None:
            continue
        vy += p.gravity * dt
        x += vx * dt
        y += vy * dt
        d = math.hypot(x, y)
        if d + r < wall or d == 0:
            continue
        nx, ny = x / d, y / d
        vn = vx * nx + vy * ny
        if vn <= 0:
            continue
        vx = (vx - 2 * vn * nx) * p.speedup
        vy = (vy - 2 * vn * ny) * p.speedup
        inward = -(vx * nx + vy * ny)
        if inward < min_inward:
            vx -= nx * (min_inward - inward)
            vy -= ny * (min_inward - inward)
        speed = math.hypot(vx, vy)
        if speed > p.vmax:
            vx *= p.vmax / speed
            vy *= p.vmax / speed
        nb += 1
        r += p.growth
        if r >= wall - 1:
            r, x, y = wall, 0.0, 0.0
            finish = t
            events.append({"t": t, "kind": "bounce", "ring": 0, "x": x, "y": y})
            events.append({"t": t, "kind": "break", "ring": 0, "x": x, "y": y})
        else:
            x, y = nx * (wall - r), ny * (wall - r)
            events.append({"t": t, "kind": "bounce", "ring": 0, "x": x, "y": y})

    return Sim(p, frames, broken_f, events, finish, radius_f, bounces_f)


def simulate(p: Params, max_seconds: float = 40.0, tail: float = 1.8) -> Sim | None:
    if p.fmt == "ball_grow":
        return _simulate_grow(p, max_seconds, tail)
    dt = 1.0 / (FPS * SUBSTEPS)
    x, y = 0.0, -20.0
    vx, vy = p.v0
    broken = 0
    events: list[dict] = []
    frames: list[tuple[float, float]] = []
    broken_f: list[int] = []
    bounces_f: list[int] = []
    nb = 0
    finish: float | None = None
    step = 0
    t = 0.0
    min_inward = 260.0

    while True:
        if step % SUBSTEPS == 0:
            frames.append((x, y))
            broken_f.append(broken)
            bounces_f.append(nb)
            if finish is not None and t >= finish + tail:
                break
            if finish is None and t > max_seconds:
                return None
        vy += p.gravity * dt
        x += vx * dt
        y += vy * dt
        t += dt
        step += 1

        if broken >= p.n_rings:
            continue
        k = broken
        wall = p.radii[k] - p.thickness / 2
        d = math.hypot(x, y)
        if d + p.ball_r < wall or d == 0:
            continue
        nx, ny = x / d, y / d
        vn = vx * nx + vy * ny
        if vn <= 0:
            continue
        rel = (math.atan2(y, x) - (p.phases[k] + p.omegas[k] * t)) % TAU
        margin = math.asin(min(1.0, p.ball_r / wall))
        if margin < rel < p.gaps[k] - margin:
            events.append({"t": t, "kind": "break", "ring": k, "x": x, "y": y})
            broken += 1
            if broken == p.n_rings:
                finish = t
            continue
        # reflect
        vx -= 2 * vn * nx
        vy -= 2 * vn * ny
        vx *= p.speedup
        vy *= p.speedup
        inward = -(vx * nx + vy * ny)
        if inward < min_inward:  # stop the ball from rolling along the wall
            vx -= nx * (min_inward - inward)
            vy -= ny * (min_inward - inward)
        speed = math.hypot(vx, vy)
        if speed > p.vmax:
            vx *= p.vmax / speed
            vy *= p.vmax / speed
        x, y = nx * (wall - p.ball_r), ny * (wall - p.ball_r)
        nb += 1
        events.append({"t": t, "kind": "bounce", "ring": k, "x": x, "y": y})

    return Sim(p, frames, broken_f, events, finish, [p.ball_r] * len(frames), bounces_f)


def quality_ok(sim: Sim) -> tuple[bool, str]:
    """Reject runs that would make a boring Short."""
    if sim.params.fmt == "ball_grow":
        if not 14.0 <= sim.finish_t <= 34.0:
            return False, f"finish_t={sim.finish_t:.1f}s outside 14-34s"
        return True, "ok"
    if not 16.0 <= sim.finish_t <= 34.0:
        return False, f"finish_t={sim.finish_t:.1f}s outside 16-34s"
    breaks = [e["t"] for e in sim.events if e["kind"] == "break"]
    if breaks[0] > 6.0:
        return False, f"first break too late ({breaks[0]:.1f}s)"
    longest = max(b - a for a, b in zip(breaks, breaks[1:]))
    if longest > 8.0:
        return False, f"dull stretch of {longest:.1f}s without a break"
    return True, "ok"


def find_good_sim(seed: int, fmt: str = "ring_escape", max_attempts: int = 200) -> Sim:
    for attempt in range(max_attempts):
        sim = simulate(make_params(seed, attempt, fmt))
        if sim is not None and quality_ok(sim)[0]:
            return sim
    raise RuntimeError(f"{fmt} seed {seed}: no acceptable run in {max_attempts} attempts")
