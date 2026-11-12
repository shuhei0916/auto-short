"""Renderer for the plinko format."""
from __future__ import annotations

import colorsys
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

from .plinko import BALL_R, CX, FPS, PEG_R, TOP_Y, bin_x, board
from .render import BG, _font, _lerp
from .sim import H, W

SS = 2


def _rgb(h: float, s: float = 0.75) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def render_plinko(sim, audio: Path, out: Path, hook: str) -> None:
    p = sim.params
    pegs, bins_top, floor = board(p.rows)
    nb = p.rows + 1
    bin_col = [_rgb(p.hue0 + p.hue_span * k / max(1, nb - 1)) for k in range(nb)]
    f_label, f_big = _font(54), _font(150)
    size = 84
    while size > 40 and _font(size).getlength(hook) > 880:
        size -= 4
    f_hook = _font(size)
    land_frames = sorted(b["land"] for b in sim.balls)
    finish_f = int(sim.finish_t * FPS)

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
        d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=fill)

    left, right = bin_x(p.rows, 0) - 42, bin_x(p.rows, nb - 1) + 42
    peak = max(sim.final_counts)
    try:
        for i in range(sim.n_frames):
            img = Image.new("RGB", (W * SS, H * SS), BG)
            d = ImageDraw.Draw(img)
            for px, py in pegs:
                circle(d, px, py, PEG_R, (70, 72, 100))
            for k in range(nb + 1):  # bin dividers + floor
                x = (bin_x(p.rows, 0) - 42 + k * 84) * SS
                d.line([x, bins_top * SS, x, floor * SS], fill=(60, 62, 90), width=4 * SS)
            d.line([left * SS, floor * SS, right * SS, floor * SS], fill=(60, 62, 90), width=6 * SS)

            landed = 0
            for j, b in enumerate(sim.balls):
                col = bin_col[b["bin"]]
                if i >= b["land"]:
                    landed += 1
                    sx, sy = b["slot"]
                    circle(d, sx, sy, BALL_R, col)
                elif i >= b["start"]:
                    x, y = b["pts"][i - b["start"]]
                    for q in range(1, 5):  # short trail
                        if i - b["start"] - q >= 0:
                            tx, ty = b["pts"][i - b["start"] - q]
                            circle(d, tx, ty, BALL_R * (1 - q * 0.17), _lerp(BG, col, 0.5 - q * 0.1))
                    circle(d, x, y, BALL_R, (255, 255, 255))

            if i >= finish_f:  # finale: bell curve outline rises over the piles
                f = min(1.0, (i - finish_f) / 45)
                pts = []
                for k in range(nb):
                    h = sim.final_counts[k] / peak * 240 * f
                    pts.append(((bin_x(p.rows, k)) * SS, (floor - 40 - h) * SS))
                d.line(pts, fill=(255, 255, 255), width=5 * SS, joint="curve")

            frame = img.reduce(SS)
            d = ImageDraw.Draw(frame)
            kw = dict(anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
            d.text((W / 2, 290), hook, font=f_hook, fill=(255, 255, 255), **kw)
            label = "LANDED" if i >= finish_f else "BALLS"
            d.text((W / 2, 1500), label, font=f_label, fill=(200, 200, 210), **kw)
            txt = str(p.n_balls) if i >= finish_f else str(sum(1 for b in sim.balls if b["start"] <= i))
            d.text((W / 2, 1610), txt, font=f_big, fill=(255, 255, 255), **kw)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        code = proc.wait()
        log.close()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed, see {out.with_suffix('.ffmpeg.log')}")
    out.with_suffix(".ffmpeg.log").unlink(missing_ok=True)
