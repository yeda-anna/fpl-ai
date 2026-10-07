"""WCAG contrast check for the colours in frontend/styles.css (one neon theme, in :root).

Run:  python3 scripts/check_contrast.py          (exit 1 if anything is under AA)

Text tokens are measured against the worst case a reader meets: the brightest
glass (--glass-3) over the lightest part of the background (--base-hi). Text on a
highlight (--on-accent) is measured against both ends of each highlight gradient.
"""
import os
import re
import sys

CSS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "styles.css")
AA = 4.5


def parse_color(v):
    v = v.strip()
    m = re.match(r"#([0-9a-fA-F]{6})$", v)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"rgba?\(([^)]+)\)", v)
    if m:
        p = [x.strip() for x in m.group(1).split(",")]
        return (float(p[0]), float(p[1]), float(p[2]), float(p[3]) if len(p) > 3 else 1.0)
    raise ValueError(v)


def over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def lum(c):
    def ch(x):
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blocks(css):
    out = {}
    for m in re.finditer(r"(\[data-theme=[^{]+|:root[^{]*)\{([^}]*)\}", css):
        sel, body = m.group(1), m.group(2)
        toks = dict((k, v.strip()) for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))
        for name in re.findall(r'data-theme="(\w+)"', sel) or (["neon"] if sel.startswith(":root") else []):
            out.setdefault(name, {}).update(toks)
    return out


def main():
    css = open(CSS, encoding="utf-8").read()
    themes = blocks(css)
    base = themes["neon"]
    failures = 0
    print("%-9s %7s %7s %7s %7s %7s %7s %7s | %s" % ("theme", "ink", "ink-2", "ink-3", "accent", "up", "down", "warn", "on-accent vs CTA / info gradients"))
    names = [n for n in themes if n != "neon"] or ["neon"]          # a single theme lives in :root
    for name in names:
        t = dict(base); t.update(themes.get(name, {}))
        bg = over(parse_color(t["--glass-3"]), parse_color(t["--base-hi"]))
        row = []
        for tok in ("--ink", "--ink-2", "--ink-3", "--accent-ink", "--up", "--down", "--warn"):
            r = ratio(parse_color(t[tok]), bg)
            row.append(r)
            if r < AA:
                failures += 1
                print("  FAIL %s %s %.2f" % (name, tok, r))
        on = parse_color(t["--on-accent"])
        grads = []
        for g in ("--grad-cta", "--grad-info"):
            for hx in re.findall(r"#[0-9a-fA-F]{6}", t[g]):
                r = ratio(on, parse_color(hx))
                grads.append(r)
                if r < AA:
                    failures += 1
                    print("  FAIL %s on-accent on %s %s %.2f" % (name, g, hx, r))
        print("%-9s %s | min %.2f" % (name, " ".join("%7.2f" % r for r in row), min(grads)))
    print("\nAA (%.1f:1) %s" % (AA, "met everywhere" if not failures else "FAILED in %d places" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
