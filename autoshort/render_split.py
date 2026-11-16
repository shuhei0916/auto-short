"""Renderer for the split format."""
from __future__ import annotations

import colorsys
import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

from .render import BG, _font, _lerp
from .sim import CX, CY, FPS, H, W
from .split import ARENA_R

SS = 2


def _rgb(h: float, s: float = 0.8, v: float = 1.0) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def render_split(sim, audio: Path, out: Path, hook: str) -> None:
    p = sim.params
    f_label, f_big = _font(54), _font(150)
    size = 84
    while size > 40 and _font(size).getlength(hook) > 880:
        size -= 4
    f_hook = _font(size)
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
        d.ellipse([(CX + x - r) * SS, (CY + y - r) * SS, (CX + x + r) * SS, (CY + y + r) * SS], fill=fill)

    r = p.ball_r
    try:
        for i in range(len(sim.frames)):
            img = Image.new("RGB", (W * SS, H * SS), BG)
            d = ImageDraw.Draw(img)
            since_finish = (i - finish_f) / FPS
            glow = max(0.0, 1.0 - since_finish / 0.8) if i >= finish_f else 0.0
            ring_col = _lerp((60, 62, 92), (255, 255, 255), glow)
            w = 8 + 10 * glow
            R = ARENA_R
            d.ellipse([(CX - R - w / 2) * SS, (CY - R - w / 2) * SS, (CX + R + w / 2) * SS, (CY + R + w / 2) * SS],
                      outline=ring_col, width=int(w * SS))

            balls = sim.frames[i]
            for k, (x, y, gen) in enumerate(balls):
                col = _rgb(p.hue0 + p.hue_step * gen, 0.75, 1.0)
                if i >= finish_f:
                    col = _lerp(col, (255, 255, 255), glow)
                circle(d, x, y, r, col)

            frame = img.reduce(SS)
            d = ImageDraw.Draw(frame)
            kw = dict(anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
            d.text((W / 2, 290), hook, font=f_hook, fill=(255, 255, 255), **kw)
            d.text((W / 2, 1500), "FULL" if i >= finish_f else "BALLS", font=f_label, fill=(200, 200, 210), **kw)
            d.text((W / 2, 1610), str(sim.counts[i]), font=f_big, fill=(255, 255, 255), **kw)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        code = proc.wait()
        log.close()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed, see {out.with_suffix('.ffmpeg.log')}")
    out.with_suffix(".ffmpeg.log").unlink(missing_ok=True)
