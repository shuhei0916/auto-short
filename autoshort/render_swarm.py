"""Renderer for the swarm format."""
from __future__ import annotations

import colorsys
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

from .render import BG, _font, _lerp
from .sim import H, W
from .swarm import CX, CY, FPS


def _rgb(h: float, s: float = 0.7) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def render_swarm(sim, audio: Path, out: Path, hook: str) -> None:
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
    try:
        for i, balls in enumerate(sim.frames):
            n = sim.counts[i]
            since = (i - finish_f) / FPS
            bg = BG
            if 0 <= since < 0.3:
                bg = _lerp(BG, _rgb(p.hue0), 0.3 * (1 - since / 0.3))
            img = Image.new("RGB", (W * 2, H * 2), bg)
            d = ImageDraw.Draw(img)
            pulse = 1.0 + (0.25 * (1 - since / 0.5) if 0 <= since < 0.5 else 0.0)
            ring_col = _lerp((70, 72, 100), (255, 255, 255), min(1.0, n / p.target))
            R = p.wall + 6
            d.ellipse([(CX - R) * 2, (CY - R) * 2, (CX + R) * 2, (CY + R) * 2], outline=ring_col, width=10)
            # newest balls on top; colour by index so the cloud stays layered
            for k, (x, y) in enumerate(balls):
                col = _rgb(p.hue0 + p.hue_span * k / p.target)
                r = p.ball_r * pulse
                cx, cy = (CX + x) * 2, (CY + y) * 2
                d.ellipse([cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2], fill=col)
                d.ellipse([cx - r * 1.1, cy - r * 1.1, cx + r * 1.1, cy + r * 1.1], fill=(255, 255, 255))
            frame = img.reduce(2)
            d = ImageDraw.Draw(frame)
            kw = dict(anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
            d.text((W / 2, 290), hook, font=f_hook, fill=(255, 255, 255), **kw)
            d.text((W / 2, 1500), "PACKED" if i >= finish_f else "BALLS", font=f_label, fill=(200, 200, 210), **kw)
            d.text((W / 2, 1610), str(n), font=f_big, fill=(255, 255, 255), **kw)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        code = proc.wait()
        log.close()
    if code != 0:
        raise RuntimeError(f"ffmpeg failed, see {out.with_suffix('.ffmpeg.log')}")
    out.with_suffix(".ffmpeg.log").unlink(missing_ok=True)
