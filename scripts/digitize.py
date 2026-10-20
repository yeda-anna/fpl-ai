"""Turn the supplied logo image into the app's logo and icons.

    python3 scripts/digitize.py path/to/logo.png

The image (the hexagonal mark the owner supplied, drawn on a design tool's grid
canvas) is used as it is — nothing is redrawn or restyled. The canvas and its grid
lines are almost colourless while the mark is strongly coloured, so the mark is
lifted off by saturation (its anti-aliased edges un-mixed from the canvas colour),
squared up with a margin and set on a dark tile of the app's own night colour
(`--bg` in styles.css), so it sits in the dark UI like the rest of the app:
  frontend/logo.webp       the logo everywhere in the app (the <symbol id="logo">)
  frontend/logo-mark.png   the mark alone, transparent, for anywhere a tile won't do
  frontend/icon-32.png     the browser-tab favicon
  frontend/icon-180.png    iOS home screen; icon-192.png and icon-512.png for the manifest
Needs Pillow and numpy (the system python3 has them; the app's venv doesn't).
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "frontend")
SAT_BG, SAT_FULL = 12, 40           # saturation: up to SAT_BG is canvas or grid, from SAT_FULL fully the mark
MARGIN = 0.12                       # space round the mark, as a share of the tile's side
TILE = (10, 18, 20)                 # the tile behind the mark: the app's --bg (#0a1214)


def lift(im: Image.Image) -> Tuple[Image.Image, Tuple[int, int, int]]:
    """The mark alone on a transparent ground, cropped to its edges, and the canvas colour."""
    a = np.asarray(im.convert("RGB")).astype(float)
    sat = a.max(2) - a.min(2)
    canvas = np.median(a[sat < SAT_BG], axis=0)                       # the canvas colour, grid lines outvoted
    alpha = np.clip((sat - SAT_BG) / float(SAT_FULL - SAT_BG), 0.0, 1.0)
    safe = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip((a - (1.0 - alpha[..., None]) * canvas) / safe, 0, 255)   # un-mix the edge from the canvas
    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    ys, xs = np.nonzero(alpha > 0.02)
    return Image.fromarray(out, "RGBA").crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)), tuple(int(round(v)) for v in canvas)


def square(mark: Image.Image, side: int, ground: Optional[Tuple[int, int, int]]) -> Image.Image:
    """The mark centred on a square tile with a margin; `ground` None keeps it transparent."""
    tile = Image.new("RGBA", (side, side), (0, 0, 0, 0) if ground is None else tuple(ground) + (255,))
    room = side * (1 - 2 * MARGIN)
    k = room / max(mark.size)
    m = mark.resize((max(1, round(mark.width * k)), max(1, round(mark.height * k))), Image.LANCZOS)
    tile.alpha_composite(m, ((side - m.width) // 2, (side - m.height) // 2))
    return tile


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    mark, canvas = lift(Image.open(sys.argv[1]))
    square(mark, 512, None).save(os.path.join(FRONT, "logo-mark.png"), optimize=True)
    square(mark, 256, TILE).convert("RGB").save(os.path.join(FRONT, "logo.webp"), "WEBP", quality=90, method=6)
    for n in (32, 180, 192, 512):
        square(mark, n, TILE).convert("RGB").save(os.path.join(FRONT, "icon-%d.png" % n), optimize=True)
    print("canvas", canvas, "mark", mark.size)


if __name__ == "__main__":
    main()
