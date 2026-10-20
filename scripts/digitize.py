"""Turn the drone-portrait image into the logo and the home-screen icons.

    python3 scripts/digitize.py path/to/portrait.webp

The image (supplied by the owner) is used as it is — nothing is generated or restyled:
  frontend/logo.webp       a square crop round the face — the logo everywhere in the app
  frontend/icon-180.png    iOS home screen; icon-192.png and icon-512.png for the manifest
Needs Pillow only.
"""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "frontend")
# the face, as a share of the frame: the square the logo and the icons are cut from
FACE = (0.505, 0.43, 0.70)          # centre x, centre y, side (of the height)


def face_square(im: Image.Image) -> Image.Image:
    W, H = im.size
    side = int(H * FACE[2])
    x0 = int(W * FACE[0] - side / 2)
    y0 = int(H * FACE[1] - side / 2)
    return im.crop((x0, y0, x0 + side, y0 + side))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    im = Image.open(sys.argv[1]).convert("RGB")
    sq = face_square(im)
    sq.resize((256, 256), Image.LANCZOS).save(os.path.join(FRONT, "logo.webp"), "WEBP", quality=82, method=6)
    for n in (180, 192, 512):
        sq.resize((n, n), Image.LANCZOS).quantize(256, dither=Image.Dither.NONE).save(os.path.join(FRONT, "icon-%d.png" % n), optimize=True)


if __name__ == "__main__":
    main()
