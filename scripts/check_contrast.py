"""WCAG contrast check for the colours in frontend/styles.css (one theme, in :root).

Run:  python3 scripts/check_contrast.py          (exit 1 if anything is under AA)

Text tokens are measured against the lightest surface that carries running text
(--surface-2: sheets, inputs, buttons); the two main text tokens also against
--surface-3 (secondary buttons, hovers). Text on a fill is measured against the
fill: --on-accent (dark) on lime, lime-soft, green, warn and down; --on-purple
(white) on purple.
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
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError(v)


def lum(c):
    def ch(x):
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def tokens(css):
    out = {}
    for m in re.finditer(r":root\s*\{([^}]*)\}", css):
        out.update((k, v.strip()) for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)))
    return out


def main():
    t = tokens(open(CSS, encoding="utf-8").read())
    c = lambda k: parse_color(t[k])
    checks = []
    for tok in ("--ink", "--ink-2", "--ink-3", "--accent-ink", "--up", "--down", "--warn"):
        checks.append((tok, "--surface-2"))
    for tok in ("--ink", "--ink-2"):
        checks.append((tok, "--surface-3"))
    for fill in ("--lime", "--lime-soft", "--green", "--warn", "--down"):
        checks.append(("--on-accent", fill))
    checks.append(("--on-purple", "--purple"))
    failures = 0
    for fg, bg in checks:
        r = ratio(c(fg), c(bg))
        flag = "ok" if r >= AA else "FAIL"
        failures += r < AA
        print("%-13s on %-12s %5.2f  %s" % (fg, bg, r, flag))
    print("\nAA (%.1f:1) %s" % (AA, "met everywhere" if not failures else "FAILED in %d places" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
