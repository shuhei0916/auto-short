"""CLI: python -m autoshort make|batch|upload"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from .audio import build_audio
from .render import render_video
from .schedule import HISTORY_DIR, meta_path_for
from .sim import FORMATS, find_good_sim

HOOKS = {"ring_escape": [
    "CAN IT ESCAPE {n} RINGS?",
    "{n} RINGS. ONE BALL.",
    "HOW FAST CAN IT BREAK OUT?",
    "WAIT FOR THE LAST RING...",
    "GUESS THE ESCAPE TIME",
], "ball_grow": [
    "IT GROWS EVERY BOUNCE",
    "HOW MANY BOUNCES TO FILL IT?",
    "GUESS THE FINAL COUNT",
    "BIGGER EVERY BOUNCE...",
]}
TITLES = {"ring_escape": [
    "Can the ball escape {n} spinning rings?",
    "{n} rings vs 1 ball - how long does it take?",
    "Guess how long until it escapes ({n} rings)",
    "The last ring is the hardest... ({n} rings)",
], "ball_grow": [
    "The ball grows every bounce - guess the final count",
    "How many bounces until it fills the circle?",
    "Bigger every bounce... until there is no room left",
]}
BLURBS = {
    "ring_escape": "Every bounce plays a note. Every gap it finds destroys a ring.",
    "ball_grow": "Every bounce plays a note and makes the ball bigger. It ends when there is no room left.",
}


def format_for(seed: int) -> str:
    """Formats alternate by seed so each gets equal exposure for comparison."""
    return FORMATS[seed % len(FORMATS)]


def make(seed: int, out_dir: Path, fmt: str | None = None, history: Path = HISTORY_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fmt = fmt or format_for(seed)
    sim = find_good_sim(seed, fmt)
    p = sim.params
    rng = random.Random(seed)
    hook = rng.choice(HOOKS[fmt]).format(n=p.n_rings)
    title = rng.choice(TITLES[fmt]).format(n=p.n_rings)

    base = out_dir / f"{fmt}_{seed:05d}"
    wav, mp4 = base.with_suffix(".wav"), base.with_suffix(".mp4")
    build_audio(sim, wav)
    render_video(sim, wav, mp4, hook)
    wav.unlink()

    meta = {
        "format": fmt,
        "seed": seed,
        "title": f"{title} #shorts",
        "description": BLURBS[fmt] + "\n"
        "A new simulation every day.\n\n#shorts #satisfying #simulation #bouncingball #physics",
        "tags": ["satisfying", "simulation", "bouncing ball", "physics", "asmr", "shorts"],
        "hook": hook,
        "duration": round(sim.duration, 2),
        "finish_t": round(sim.finish_t, 2),
        "bounces": sum(e["kind"] == "bounce" for e in sim.events),
        "params": p.to_dict(),
        "uploaded": None,
    }
    meta_path_for(mp4, history).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"{mp4}  {sim.duration:.1f}s  (rendered in {time.time() - t0:.0f}s)")
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(prog="autoshort")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("make", help="render one video")
    m.add_argument("--seed", type=int, required=True)
    m.add_argument("--format", choices=FORMATS, help="default: alternates by seed")
    m.add_argument("--out", type=Path, default=Path("out"))

    b = sub.add_parser("batch", help="render several videos")
    b.add_argument("--start-seed", type=int, required=True)
    b.add_argument("--count", type=int, default=5)
    b.add_argument("--out", type=Path, default=Path("out"))

    u = sub.add_parser("upload", help="upload a rendered video to YouTube")
    u.add_argument("video", type=Path)
    u.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    u.add_argument("--publish-at", help="RFC3339 time, e.g. 2026-11-20T12:00:00Z (forces private until then)")

    d = sub.add_parser("daily", help="render the next videos and schedule them on YouTube")
    d.add_argument("--count", type=int, default=2)
    d.add_argument("--out", type=Path, default=Path("out"))
    d.add_argument("--no-upload", action="store_true")

    sub.add_parser("analytics", help="write analytics/latest.json from YouTube stats")

    a = ap.parse_args()
    if a.cmd == "make":
        make(a.seed, a.out, a.format)
    elif a.cmd == "batch":
        for s in range(a.start_seed, a.start_seed + a.count):
            make(s, a.out)
    elif a.cmd == "daily":
        from datetime import datetime, timezone

        from .schedule import next_seed, next_slots, taken_slots, to_rfc3339

        seed = next_seed(HISTORY_DIR)
        slots = next_slots(datetime.now(timezone.utc), a.count, taken=taken_slots(HISTORY_DIR))
        for i, slot in enumerate(slots):
            video = make(seed + i, a.out)
            if not a.no_upload:
                from .upload import upload

                upload(video, publish_at=to_rfc3339(slot))
    elif a.cmd == "analytics":
        from .analytics import collect

        collect()
    elif a.cmd == "upload":
        from .upload import upload

        upload(a.video, a.privacy, a.publish_at)


if __name__ == "__main__":
    main()
