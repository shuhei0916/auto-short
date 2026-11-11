"""CLI: python -m autoshort make|batch|upload"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from .audio import build_audio
from .render import render_video
from .sim import find_good_sim

HOOKS = [
    "CAN IT ESCAPE {n} RINGS?",
    "{n} RINGS. ONE BALL.",
    "HOW FAST CAN IT BREAK OUT?",
    "WAIT FOR THE LAST RING...",
    "GUESS THE ESCAPE TIME",
]
TITLES = [
    "Can the ball escape {n} spinning rings?",
    "{n} rings vs 1 ball - how long does it take?",
    "Guess how long until it escapes ({n} rings)",
    "The last ring is the hardest... ({n} rings)",
]


def make(seed: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sim = find_good_sim(seed)
    p = sim.params
    rng = random.Random(seed)
    hook = rng.choice(HOOKS).format(n=p.n_rings)
    title = rng.choice(TITLES).format(n=p.n_rings)

    base = out_dir / f"ring_escape_{seed:05d}"
    wav, mp4 = base.with_suffix(".wav"), base.with_suffix(".mp4")
    build_audio(sim, wav)
    render_video(sim, wav, mp4, hook)
    wav.unlink()

    meta = {
        "format": "ring_escape",
        "seed": seed,
        "title": f"{title} #shorts",
        "description": "Every bounce plays a note. Every gap it finds destroys a ring.\n"
        "A new simulation every day.\n\n#shorts #satisfying #simulation #bouncingball #physics",
        "tags": ["satisfying", "simulation", "bouncing ball", "physics", "asmr", "shorts"],
        "hook": hook,
        "duration": round(sim.duration, 2),
        "finish_t": round(sim.finish_t, 2),
        "bounces": sum(e["kind"] == "bounce" for e in sim.events),
        "params": p.to_dict(),
        "uploaded": None,
    }
    base.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"{mp4}  {sim.duration:.1f}s  rings={p.n_rings}  (rendered in {time.time() - t0:.0f}s)")
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(prog="autoshort")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("make", help="render one video")
    m.add_argument("--seed", type=int, required=True)
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

    a = ap.parse_args()
    if a.cmd == "make":
        make(a.seed, a.out)
    elif a.cmd == "batch":
        for s in range(a.start_seed, a.start_seed + a.count):
            make(s, a.out)
    elif a.cmd == "daily":
        from datetime import datetime, timezone

        from .schedule import next_seed, next_slots, taken_slots, to_rfc3339

        a.out.mkdir(parents=True, exist_ok=True)
        seed = next_seed(a.out)
        slots = next_slots(datetime.now(timezone.utc), a.count, taken=taken_slots(a.out))
        for i, slot in enumerate(slots):
            video = make(seed + i, a.out)
            if not a.no_upload:
                from .upload import upload

                upload(video, publish_at=to_rfc3339(slot))
    elif a.cmd == "upload":
        from .upload import upload

        upload(a.video, a.privacy, a.publish_at)


if __name__ == "__main__":
    main()
