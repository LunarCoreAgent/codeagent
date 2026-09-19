#!/usr/bin/env python3
"""Remove a baked white background from logo artwork, keeping interior detail.

Algorithm:
1. Flood-fill from the four canvas corners over near-white pixels
   (all channels > FLOOD_MIN) — that region becomes fully transparent.
   Only background connected to the corners is removed; enclosed content
   (e.g. bright areas inside the emblem) is never touched.
2. Edge feather: surviving neutral near-white pixels (low saturation,
   luminance in [FEATHER_LO, FEATHER_HI]) get partial alpha proportional
   to their distance from white, so anti-aliased edges do not leave a
   white halo on dark backgrounds. Colored pixels are never modified.

Usage:
    python3 remove_white_bg.py <src.png> <dst.png> [erode_px] [mask_radius]

erode_px: 额外向内腐蚀边缘的像素数（默认 0）。白底抗锯齿会在形状边缘
留下一圈淡色污染（白边），腐蚀 + 轻微模糊可彻底去掉。
mask_radius: 若给定（>0），在去白边后再套一个圆角矩形蒙版（内缩 3px、
    圆角半径=mask_radius），从源头切掉四边贴画布的淡色边线，使 logo-art
    本身也拥有干净透明边缘。1024 基准下推荐 225（22% 圆角）。
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

FLOOD_MIN = 251      # 洪水填充认定的"白"（三通道均大于该值）
FEATHER_HI = 250     # 羽化区间上限（>=该值的中性像素趋近全透）
FEATHER_LO = 228     # 羽化区间下限（<=该值完全保留）
SAT_LIMIT = 0.12     # 仅处理低饱和（中性）像素，彩色高光不动


def remove_white(
    src: Path, dst: Path, erode_px: int = 0, mask_radius: int = 0
) -> None:
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    px = img.load()

    # 1) 四角洪水填充：背景白 → 透明
    seen = bytearray(w * h)
    q = deque([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])
    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y * w + x]:
            continue
        r, g, b, a = px[x, y]
        if a == 0 or not (r > FLOOD_MIN and g > FLOOD_MIN and b > FLOOD_MIN):
            continue
        seen[y * w + x] = 1
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for y in range(h):
        for x in range(w):
            if seen[y * w + x]:
                r, g, b, a = px[x, y]
                px[x, y] = (r, g, b, 0)

    # 2) 边缘羽化：存活的中性近白像素按白度给部分透明
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum <= FEATHER_LO:
                continue
            mx, mn = max(r, g, b), min(r, g, b)
            sat = 0.0 if mx == 0 else (mx - mn) / mx
            if sat > SAT_LIMIT:
                continue
            keep = (FEATHER_HI - lum) / (FEATHER_HI - FEATHER_LO)  # lum=HI→0
            na = int(a * min(max(keep, 0.0), 1.0))
            if na != a:
                px[x, y] = (r, g, b, na)

    # 3) 边缘腐蚀：去掉白底抗锯齿留下的淡色污染圈，再轻模糊保持顺滑
    if erode_px > 0:
        a_chan = img.split()[3]
        a_chan = a_chan.filter(ImageFilter.MinFilter(erode_px * 2 + 1))
        a_chan = a_chan.filter(ImageFilter.GaussianBlur(erode_px * 0.35))
        img.putalpha(a_chan)

    # 4) 圆角蒙版：切掉四边贴画布的淡色边线，使 logo-art 本身也干净
    if mask_radius > 0:
        inset = 3
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle(
            [inset, inset, w - 1 - inset, h - 1 - inset],
            radius=mask_radius - inset, fill=255,
        )
        m = m.filter(ImageFilter.GaussianBlur(0.6))
        img.putalpha(ImageChops.multiply(img.split()[3], m))

    # 5) 预乘 alpha：把低 alpha 像素的 RGB 压暗，杜绝"幽灵浅色 RGB"
    #    在某些合成器上造成的残留白边
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 255:
                f = a / 255.0
                px[x, y] = (int(r * f), int(g * f), int(b * f), a)

    img.save(dst)
    print(f"OK → {dst} ({w}x{h}, erode={erode_px}px)")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4, 5):
        raise SystemExit(__doc__)
    remove_white(
        Path(sys.argv[1]), Path(sys.argv[2]),
        int(sys.argv[3]) if len(sys.argv) >= 4 else 0,
        int(sys.argv[4]) if len(sys.argv) >= 5 else 0,
    )
