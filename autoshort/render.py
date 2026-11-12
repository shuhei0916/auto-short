"""Renders a Sim to a 1080x1920 60fps MP4 (frames piped to ffmpeg)."""
from __future__ import annotations

import colorsys
import math
import random
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from .sim import CX, CY, FPS, H, TAU, W, Sim

SS = 2  # supersampling factor
BG = (10, 10, 18)
TRAIL = 28
FONT_CANDIDATES = [
    str(Path(__file__).resolve().parent.parent / "assets/fonts/Anton-Regular.ttf"),
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def _lerp(a, b, f):
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def ring_color(p, k: int) -> tuple[int, int, int]:
    h = (p.hue0 + p.hue_span * k / max(1, p.n_rings - 1)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def _particles(sim: Sim) -> list[dict]:
    rng = random.Random(sim.params.seed)
    p = sim.params
    out = []
    for e in sim.events:
        if e["kind"] != "break":
            continue
        R = p.radii[e["ring"]]
        count = int(40 + R / 5)
        for _ in range(count):
            a = rng.uniform(0, TAU)
            sp = rng.uniform(150, 650)
            out.append(
                {
                    "t0": e["t"],
                    "x": R * math.cos(a),
                    "y": R * math.sin(a),
                    "vx": sp * math.cos(a),
                    "vy": sp * math.sin(a),
                    "life": rng.uniform(0.5, 1.0),
                    "size": rng.uniform(3, 7),
                    "color": ring_color(p, e["ring"]),
                }
            )
    return out


def render_video(sim: Sim, audio: Path, out: Path, hook: str) -> None:
    p = sim.params
    colors = [ring_color(p, k) for k in range(p.n_rings)]
    particles = _particles(sim)
    breaks = [e for e in sim.events if e["kind"] == "break"]
    f_label, f_big = _font(54), _font(150)
    size = 84
    while size > 40 and _font(size).getlength(hook) > 880:  # keep clear of the Shorts UI
        size -= 4
    f_hook = _font(size)

    log = open(out.with_suffix(".ffmpeg.log"), "wb")
    proc = subprocess.Popen(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", str(audio),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
            str(out),
        ],
        stdin=subprocess.PIPE, stdout=log, stderr=log,
    )

    def circle(d, x, y, r, fill):
        cx, cy = (CX + x) * SS, (CY + y) * SS
        d.ellipse([cx - r * SS, cy - r * SS, cx + r * SS, cy + r * SS], fill=fill)

    try:
        for i, (bx, by) in enumerate(sim.frames):
            t = i / FPS
            broken = sim.broken[i]
            bg = BG
            last = [b for b in breaks if b["t"] <= t]
            if last and t - last[-1]["t"] < 0.15:  # brief flash on a break
                f = 1 - (t - last[-1]["t"]) / 0.15
                bg = _lerp(BG, colors[last[-1]["ring"]], 0.22 * f)

            img = Image.new("RGB", (W * SS, H * SS), bg)
            d = ImageDraw.Draw(img)

            for k in range(broken, p.n_rings):
                R = p.radii[k] * SS
                start = math.degrees(p.phases[k] + p.omegas[k] * t + p.gaps[k])
                end = start + 360 - math.degrees(p.gaps[k])
                box = [CX * SS - R, CY * SS - R, CX * SS + R, CY * SS + R]
                d.arc(box, start, end, fill=colors[k], width=int(p.thickness * SS))

            for q in particles:
                age = t - q["t0"]
                if 0 <= age < q["life"]:
                    f = 1 - age / q["life"]
                    px = q["x"] + q["vx"] * age
                    py = q["y"] + q["vy"] * age + 0.5 * 900 * age * age
                    circle(d, px, py, q["size"] * f, _lerp(bg, q["color"], f))

            grow = p.fmt == "ball_grow"
            ball_r = sim.radius[i]
            if grow:  # hue drifts with every bounce
                h = (p.hue0 + 0.017 * sim.bounces[i]) % 1.0
                tint = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, 0.75, 1.0))
            else:
                tint = colors[min(broken, p.n_rings - 1)]
            lo = max(0, i - TRAIL)
            for j in range(lo, i):
                f = (j - lo + 1) / (i - lo + 1)
                tx, ty = sim.frames[j]
                circle(d, tx, ty, sim.radius[j] * (0.35 + 0.6 * f), _lerp(bg, tint, 0.55 * f))
            circle(d, bx, by, ball_r, tint)
            circle(d, bx, by, max(ball_r * 0.72, ball_r - 14), (255, 255, 255))

            frame = img.reduce(SS)
            d = ImageDraw.Draw(frame)
            kw = dict(anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
            d.text((W / 2, 290), hook, font=f_hook, fill=(255, 255, 255), **kw)
            if grow:
                done = t >= sim.finish_t
                label = "FILLED IN" if done else "BOUNCES"
                d.text((W / 2, 1500), label, font=f_label, fill=(200, 200, 210), **kw)
                d.text((W / 2, 1610), str(sim.bounces[i]), font=f_big, fill=(255, 255, 255) if done else tint, **kw)
            elif t < sim.finish_t:
                left = p.n_rings - broken
                d.text((W / 2, 1500), "RINGS LEFT", font=f_label, fill=(200, 200, 210), **kw)
                d.text((W / 2, 1610), str(left), font=f_big, fill=tint, **kw)
            else:
                d.text((W / 2, 1500), "ESCAPED IN", font=f_label, fill=(200, 200, 210), **kw)
                d.text((W / 2, 1610), f"{sim.finish_t:.1f}s", font=f_big, fill=(255, 255, 255), **kw)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        code = proc.wait()
        log.close()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed, see {out.with_suffix('.ffmpeg.log')}")
    out.with_suffix(".ffmpeg.log").unlink(missing_ok=True)
