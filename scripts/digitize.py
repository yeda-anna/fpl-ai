"""Digitize a portrait photo into drones: the data for the opening film and the logo.

    python3 scripts/digitize.py path/to/photo.jpg

Needs Pillow and numpy only. Writes:
  frontend/portrait.js   every drone's place in the portrait, for the film (intro.js)
  frontend/icon.svg      the logo on a night tile (the app icon)
  and the <symbol id="logo"> block in frontend/index.html (the logo everywhere else)
Then render the PNG icons with `node scripts/render_icons.js`.

How a photo becomes drones:
  1. Cut the person out: skin, very dark hair and clothes, and the cream piping
     on the shirt, inside a head-and-shoulders shape; small specks dropped, holes
     filled, and only the shape that reaches the bottom of the frame kept.
  2. Find what makes the face: features are spots darker than the light around
     them (brows, eyes, moustache, mouth, smile lines) — measured against local
     light so a shadowed cheek doesn't count; light is how lit the skin is.
  3. Place drones with blue-noise darts (no two closer than a radius that shrinks
     where a layer matters most): cyan round the silhouette, magenta on the
     features, white on the lit skin, violet through the hair, lime on the piping
     and a few dim ones on the shirt.
The source photo is not committed; only the drones are.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "frontend")
LAYERS = ["outline", "feature", "light", "hair", "trim", "shirt"]
# literal colours for the SVG logo (the neon tokens: cyan, magenta, ink, violet, lime)
FILL = {"outline": "#22F0FF", "feature": "#FF3DCB", "light": "#F6F4FF", "hair": "#8E78FF", "trim": "#C8FF3D", "shirt": "#5A46C8"}

Pt = Tuple[float, float, float]


def blur(x: np.ndarray, r: float) -> np.ndarray:
    k = np.arange(-int(3 * r) - 1, int(3 * r) + 2)
    g = np.exp(-k ** 2 / (2 * r * r))
    g /= g.sum()
    p = len(k) // 2
    x = np.pad(x, p, mode="edge")
    x = np.apply_along_axis(lambda v: np.convolve(v, g, "valid"), 1, x)
    return np.apply_along_axis(lambda v: np.convolve(v, g, "valid"), 0, x)


def morph(m: np.ndarray, k: int, op: str) -> np.ndarray:
    """box dilation ('dil') or erosion ('ero') of radius k"""
    H, W = m.shape
    p = np.pad(m.astype(np.int32), k, mode="edge")
    c = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n = 2 * k + 1
    s = c[n:n + H, n:n + W] - c[:H, n:n + W] - c[n:n + H, :W] + c[:H, :W]
    return s > 0 if op == "dil" else s == n * n


def cut_out(a: np.ndarray) -> np.ndarray:
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    H, W = R.shape
    skin = (R > G + 10) & (R > B + 18)
    dark = (np.maximum(np.maximum(R, G), B) < 48) & (B < R + 6)
    cream = (R > 150) & (G > 140) & (B > 110)
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W * 0.511, H * 0.389                      # the head, as a share of the frame
    head = ((xx - cx) / (W * 0.254)) ** 2 + ((yy - cy) / (H * 0.368)) ** 2 <= 1
    shoulders = (yy > H * 0.68 + 0.32 * np.maximum(0, xx - W * 0.756)) & (yy > H * 0.68 + 0.4 * np.maximum(0, W * 0.265 - xx))
    m = (skin | dark | cream) & (head | shoulders)
    m = morph(morph(m, 4, "ero"), 4, "dil")
    m = morph(morph(m, 6, "dil"), 6, "ero")
    keep = np.zeros_like(m)
    stack = [(H - 20, W // 2)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < H and 0 <= x < W and m[y, x] and not keep[y, x]:
            keep[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return keep


def maps(src: str) -> Tuple[Dict[str, np.ndarray], int, int]:
    im = Image.open(src).convert("RGB")
    a0 = np.asarray(im.filter(ImageFilter.GaussianBlur(2))).astype(float)
    mask = cut_out(a0)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.2))).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    H, W = mask.shape
    lum = .299 * R + .587 * G + .114 * B
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W * 0.508, H * 0.504
    oval = ((xx - cx) / (W * 0.174)) ** 2 + ((yy - cy) / (H * 0.295)) ** 2 <= 1
    skin = (R > G + 10) & (R > B + 18) & mask
    face = morph(morph(skin & oval, 10, "dil"), 10, "ero") & mask & oval
    core = morph(face, 3, "ero")
    trim = (R > 150) & (G > 140) & (B > 110) & mask & ~face
    dog = blur(lum, 9) - blur(lum, 1.5)
    ratio = blur(lum, 1.5) / (blur(lum, 16) + 8)        # darker than the light around it: shadow doesn't count
    feat = np.maximum(np.clip((dog - 10) / 26.0, 0, 1), np.clip((0.78 - ratio) / 0.3, 0, 1)) * core
    light = np.clip((lum - 72) / 115.0, 0, 1) ** 1.25 * core
    hair = mask & ~face & (lum < 70) & (yy < H * 0.705 + 0.3 * np.abs(xx - cx))
    shirt = mask & ~face & ~hair & ~trim
    edge = mask & ~morph(mask, 1, "ero") & (xx > 3) & (yy < H - 4) & (xx < W - 4)
    return {"outline": edge.astype(float), "feature": feat * (1 - 0.0), "light": light * (1 - np.clip(feat * 2, 0, 1)),
            "hair": hair * (0.25 + 0.75 * np.clip((60 - lum) / 60, 0, 1)) * 0.6, "trim": trim.astype(float),
            "shirt": shirt * 0.35}, W, H


def darts(weight: np.ndarray, rmin: float, rmax: float, rng, box=None, n_cand: int = 120000) -> List[Pt]:
    """blue noise: dense (rmin) where the weight is high, sparse (rmax) where it's low"""
    if box:
        x0, y0, x1, y1 = box
        w2 = np.zeros_like(weight)
        w2[y0:y1, x0:x1] = weight[y0:y1, x0:x1]
        weight = w2
    ys, xs = np.nonzero(weight > 0.02)
    if not len(ys):
        return []
    idx = rng.choice(len(ys), size=min(n_cand, len(ys) * 3), replace=True)
    w = weight[ys[idx], xs[idx]]
    keep = rng.random(len(idx)) < w ** 0.8
    idx, w = idx[keep], w[keep]
    order = np.argsort(-w - rng.random(len(w)) * 0.3)
    pts: List[Pt] = []
    grid: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
    k = int(np.ceil(rmax / rmin))
    for o in order:
        y, x = ys[idx[o]] + rng.random() - .5, xs[idx[o]] + rng.random() - .5
        r = rmax - (rmax - rmin) * w[o]
        gx, gy = int(x // rmin), int(y // rmin)
        if any((px - x) ** 2 + (py - y) ** 2 < r * r
               for dx in range(-k, k + 1) for dy in range(-k, k + 1) for (px, py) in grid.get((gx + dx, gy + dy), ())):
            continue
        grid.setdefault((gx, gy), []).append((x, y))
        pts.append((x, y, float(w[o])))
    return pts


def sample(m: Dict[str, np.ndarray], s: float, box=None) -> Dict[str, List[Pt]]:
    rng = np.random.default_rng(7)
    radii = {"outline": (6.5, 6.5), "feature": (3.4, 7), "light": (4.6, 12), "hair": (9, 15), "trim": (6, 6), "shirt": (16, 22)}
    return {k: darts(m[k], radii[k][0] * s, radii[k][1] * s, rng, box) for k in LAYERS}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    m, W, H = maps(sys.argv[1])

    # the film: the whole frame, about 900 drones, packed as [x, y, layer, weight] on a 0..1000 grid
    film = sample(m, 1.0)
    S = 1000.0 / max(W, H)
    flat: List[int] = []
    for li, k in enumerate(LAYERS):
        for (x, y, w) in film[k]:
            flat += [round(x * S), round(y * S), li, round(w * 9)]
    n = len(flat) // 4
    with open(os.path.join(FRONT, "portrait.js"), "w", encoding="utf-8") as f:
        f.write("/* Footy — the drone portrait for the opening film. Generated by scripts/digitize.py; don't edit by hand.\n"
                "   %d drones as [x, y, layer, weight] on a %dx%d grid; layers: %s. */\n"
                "'use strict';\nconst PORTRAIT = {w:%d, h:%d, layers:%s, d:%s};\n"
                % (n, round(W * S), round(H * S), ", ".join(LAYERS), round(W * S), round(H * S), json.dumps(LAYERS), json.dumps(flat, separators=(",", ":"))))

    # the logo: a square crop round the head, fewer and bolder drones
    side = int(H * 0.86)
    x0 = int(W * 0.511 - side / 2)
    y0 = int(H * 0.015)
    box = (x0, y0, x0 + side, y0 + side)
    logo = sample(m, 2.0, box)
    size = {"outline": 1.55, "feature": 1.85, "light": 1.35, "hair": 1.1, "trim": 1.4, "shirt": .9}
    circles = []
    for k in LAYERS:
        if k == "shirt":
            continue
        for (x, y, w) in logo[k]:
            u, v = (x - x0) / side * 100, (y - y0) / side * 100
            r = size[k] * (0.85 + 0.3 * w)
            circles.append('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s"/>' % (u, v, r, FILL[k]))
    dots = "".join(circles)
    print("film drones:", n, " logo drones:", len(circles))

    sym = '<symbol id="logo" viewBox="0 0 100 100">%s</symbol>' % dots
    p = os.path.join(FRONT, "index.html")
    html = open(p, encoding="utf-8").read()
    html, k = re.subn(r'<symbol id="logo" viewBox="[^"]*">.*?</symbol>', lambda _: sym, html, count=1, flags=re.S)
    assert k == 1, "no <symbol id=\"logo\"> in index.html"
    open(p, "w", encoding="utf-8").write(html)

    icon = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n'
            '  <defs>\n'
            '    <radialGradient id="bg" cx=".5" cy=".4" r=".8"><stop offset="0" stop-color="#1A1040"/><stop offset="1" stop-color="#05030F"/></radialGradient>\n'
            '    <filter id="glow" x="-10%%" y="-10%%" width="120%%" height="120%%"><feGaussianBlur stdDeviation="1.1" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>\n'
            '  </defs>\n'
            '  <rect width="100" height="100" rx="24" fill="url(#bg)"/>\n'
            '  <rect x="1.5" y="1.5" width="97" height="97" rx="22.5" fill="none" stroke="#22F0FF" stroke-opacity=".45" stroke-width="2"/>\n'
            '  <g transform="translate(7 7) scale(.86)" filter="url(#glow)">%s</g>\n'
            '</svg>\n' % dots)
    open(os.path.join(FRONT, "icon.svg"), "w", encoding="utf-8").write(icon)


if __name__ == "__main__":
    main()
