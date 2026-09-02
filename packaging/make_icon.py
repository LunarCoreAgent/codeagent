#!/usr/bin/env python3
"""Render the codeagent logo: a planet with a satellite ring.

Outputs (into packaging/):
    icon.png   1024x1024 master
    icon.icns  macOS app icon (via iconutil)
    icon.ico   Windows multi-size icon

Design: deep-space rounded square, gradient planet, glowing tilted ring
with a satellite dot, a few stars. Drawn at 4x and downscaled (antialias).
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 4  # supersample factor
SIZE = 1024
W = SIZE * S

# palette
BG_TOP = (16, 18, 28)
BG_BOT = (28, 32, 52)
PLANET_HI = (96, 156, 255)   # #609cff
PLANET_LO = (88, 60, 200)    # #583cc8
RING = (150, 190, 255)
SAT = (255, 214, 120)


def lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def render() -> Image.Image:
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

    # --- background: vertical gradient in a rounded square (macOS style) ---
    bg = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    grad = Image.new("RGB", (1, W))
    for y in range(W):
        grad.putpixel((0, y), lerp(BG_TOP, BG_BOT, y / W))
    bg.paste(grad.resize((W, W)), (0, 0))
    bg.putalpha(rounded_mask(W, int(W * 0.22)))
    img.alpha_composite(bg)

    d = ImageDraw.Draw(img)

    # --- stars ---
    stars = [(0.20, 0.22, 3), (0.80, 0.18, 2.4), (0.72, 0.78, 2.8),
             (0.26, 0.74, 2.2), (0.86, 0.52, 2.0), (0.14, 0.48, 2.0)]
    for fx, fy, r in stars:
        x, y, rr = fx * W, fy * W, r * S
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(220, 230, 255, 200))

    cx, cy, R = W / 2, W / 2.08, W * 0.215  # planet center & radius
    tilt = math.radians(-18)                 # ring tilt
    ring_rx, ring_ry = R * 2.05, R * 0.62    # ring ellipse axes

    def ring_point(theta: float) -> tuple[float, float]:
        # ellipse point rotated by tilt around planet center
        ex, ey = ring_rx * math.cos(theta), ring_ry * math.sin(theta)
        return (
            cx + ex * math.cos(tilt) - ey * math.sin(tilt),
            cy + ex * math.sin(tilt) + ey * math.cos(tilt),
        )

    def draw_ring_arc(t0: float, t1: float, width: int, color: tuple) -> None:
        pts = [ring_point(t0 + (t1 - t0) * i / 120) for i in range(121)]
        d.line(pts, fill=color, width=width, joint="curve")

    ring_w = int(W * 0.022)

    # --- ring: back half (behind planet) ---
    draw_ring_arc(math.pi, 2 * math.pi, ring_w, (*RING, 140))

    # --- planet: radial gradient sphere ---
    planet = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    pd = ImageDraw.Draw(planet)
    steps = 64
    for i in range(steps, 0, -1):
        r = R * i / steps
        # light from upper-left
        t = i / steps
        pd.ellipse(
            [cx - r - R * 0.18 * (1 - t), cy - r - R * 0.18 * (1 - t),
             cx + r - R * 0.18 * (1 - t), cy + r - R * 0.18 * (1 - t)],
            fill=(*lerp(PLANET_HI, PLANET_LO, t), 255),
        )
    # limb shadow bottom-right
    shadow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(10, 8, 30, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(W * 0.02))
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    planet.paste(shadow, (int(R * 0.35), int(R * 0.35)), shadow)
    planet.putalpha(mask)
    img.alpha_composite(planet)

    # --- ring: front half (over planet) with glow ---
    glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pts = [ring_point((2 * math.pi) * i / 120) for i in range(121)]
    gd.line(pts[:61], fill=(*RING, 110), width=ring_w * 3, joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(ring_w))
    img.alpha_composite(glow)
    draw_ring_arc(0, math.pi, ring_w, (*RING, 235))

    # --- satellite on the ring (front-right) ---
    sx, sy = ring_point(math.radians(28))
    sr = W * 0.028
    halo = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        [sx - sr * 2.2, sy - sr * 2.2, sx + sr * 2.2, sy + sr * 2.2],
        fill=(*SAT, 70),
    )
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(sr)))
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(*SAT, 255))
    d.ellipse([sx - sr * 0.45, sy - sr * 0.45, sx + sr * 0.45, sy + sr * 0.45],
              fill=(255, 244, 214, 255))

    return img.resize((SIZE, SIZE), Image.LANCZOS)


def make_icns(png: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        iconset = Path(td) / "icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 64, 128, 256, 512):
            img = Image.open(png).resize((size, size), Image.LANCZOS)
            img.save(iconset / f"icon_{size}x{size}.png")
            img2x = Image.open(png).resize((size * 2, size * 2), Image.LANCZOS)
            img2x.save(iconset / f"icon_{size}x{size}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
                       check=True)


def make_ico(png: Path, out: Path) -> None:
    img = Image.open(png)
    img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128),
                         (256, 256)])


def main() -> int:
    master = HERE / "icon.png"
    render().save(master)
    print(f"OK → {master}")
    if sys.platform == "darwin":
        make_icns(master, HERE / "icon.icns")
        print(f"OK → {HERE / 'icon.icns'}")
    make_ico(master, HERE / "icon.ico")
    print(f"OK → {HERE / 'icon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
