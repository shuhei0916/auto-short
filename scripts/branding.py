"""Renders the channel icon and banner into branding/. Run: python scripts/branding.py"""
from __future__ import annotations

import colorsys
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = str(ROOT / "assets/fonts/Anton-Regular.ttf")
OUT = ROOT / "branding"
BG = (10, 10, 18)
SS = 3


def hsv(h, s=0.75, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def glow(img: Image.Image, radius: int) -> Image.Image:
    """Adds a soft bloom so the neon strokes read at small sizes."""
    return Image.blend(img, Image.alpha_composite(img, img.filter(ImageFilter.GaussianBlur(radius))), 0.5)


def rings(d, cx, cy, radii, width, hue0, hue_span, gap_deg, rot0, rot_step):
    for k, r in enumerate(radii):
        c = hsv(hue0 + hue_span * k / max(1, len(radii) - 1))
        start = rot0 + rot_step * k
        d.arc([cx - r, cy - r, cx + r, cy + r], start + gap_deg, start + 360, fill=c + (255,), width=width)


def ball(d, x, y, r, rim):
    d.ellipse([x - r, y - r, x + r, y + r], fill=rim + (255,))
    ri = r * 0.72
    d.ellipse([x - ri, y - ri, x + ri, y + ri], fill=(255, 255, 255, 255))


def trail(d, pts, r, color):
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        f = (i + 1) / n
        rr = r * (0.3 + 0.65 * f)
        c = tuple(int(BG[j] + (color[j] - BG[j]) * 0.6 * f) for j in range(3))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c + (255,))


def icon(size=800):
    S = size * SS
    img = Image.new("RGBA", (S, S), BG + (255,))
    d = ImageDraw.Draw(img)
    c = S / 2
    rings(d, c, c, [S * 0.40, S * 0.30, S * 0.20], int(S * 0.035), 0.50, -0.30, 52, -60, 115)
    pts = [(c - S * 0.20 + S * 0.012 * i, c + S * 0.12 - S * 0.0009 * (i - 14) ** 2) for i in range(26)]
    trail(d, pts[:-1], S * 0.055, hsv(0.5))
    ball(d, *pts[-1], S * 0.065, hsv(0.5))
    img = glow(img, S // 90).resize((size, size), Image.LANCZOS)
    img.convert("RGB").save(OUT / "icon.png")


def banner(w=2560, h=1440):
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    cy = H / 2
    # Decorative rings on both sides; they fall outside the mobile-safe area.
    radii = [H * f for f in (0.25, 0.20, 0.15, 0.10)]
    rings(d, W * 0.10, cy, radii, int(H * 0.011), 0.50, -0.30, 48, 20, 70)
    rings(d, W * 0.90, cy, radii, int(H * 0.011), 0.92, -0.25, 48, 200, 70)
    # A bounce arc across the title.
    x0, x1 = W * 0.245, W * 0.755
    pts = []
    for i in range(70):
        t = i / 69
        x = x0 + (x1 - x0) * t
        y = cy + H * 0.06 - H * 0.20 * math.sin(math.pi * t)
        pts.append((x, y))
    for i, (x, y) in enumerate(pts[::3]):
        f = i / (len(pts) / 3)
        r = H * 0.004
        col = hsv(0.5 + 0.4 * f)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (200,))
    ball(d, *pts[-1], H * 0.018, hsv(0.9))
    img = glow(img, H // 160)
    d = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(FONT, int(H * 0.15))
    f_sub = ImageFont.truetype(FONT, int(H * 0.042))
    d.text((W / 2, cy - H * 0.01), "BOUNCE THEORY", font=f_title, fill=(255, 255, 255, 255), anchor="mm")
    d.text((W / 2, cy + H * 0.105), "NEW PHYSICS SIMULATION SHORTS EVERY DAY", font=f_sub,
           fill=(190, 195, 215, 255), anchor="mm")
    img = img.resize((w, h), Image.LANCZOS)
    img.convert("RGB").save(OUT / "banner.png")

    # Preview with the mobile-safe area (1546x423) outlined, for checking only.
    prev = img.convert("RGB").copy()
    pd = ImageDraw.Draw(prev)
    sw, sh = 1546, 423
    pd.rectangle([(w - sw) / 2, (h - sh) / 2, (w + sw) / 2, (h + sh) / 2], outline=(255, 0, 0), width=4)
    prev.save(OUT / "banner_safe_area_preview.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    icon()
    banner()
    print("wrote", *sorted(p.name for p in OUT.glob("*.png")))
