# Design system

Everything visual lives in `frontend/styles.css` and reads from CSS custom
properties ("tokens") declared at the top. Change a token, not a component.

## Palette — 60 : 30 : 10

| Share | Role | Colours | Used for |
| --- | --- | --- | --- |
| **60%** | Background | forest `#1B4332` (with `#24573F` / `#123224` for depth) | page, backdrop, chrome tint |
| **30%** | Content | mint `#96E6A1`, sea green `#84FAB0` | glass cards, rows, borders, pitch, positive numbers |
| **10%** | Highlight | lime `#D4FC79`, sky `#8FD3F4` | primary buttons, active tab, selected path, key figures, badges |

Rules:

- Highlights are pale. Text **on** a highlight is always forest
  (`--on-accent: #1B4332`), never white.
- Use lime for "do this" (CTA, active, captain) and sky for "information"
  (badges, the Copilot bubble, secondary charts).
- Keep highlights scarce. If a screen has more than one or two lime blocks,
  something should be demoted to mint glass.
- Negative numbers use `--down` (`#FFB3B3` dark / `#C2414B` light) and warnings
  `--warn` (`#FFD479`). They sit outside the brand palette on purpose.

### Gradients

| Token | Value | Use |
| --- | --- | --- |
| `--grad-cta` | `135deg, #D4FC79 → #96E6A1` | primary buttons, active segments |
| `--grad-info` | `135deg, #84FAB0 → #8FD3F4` | Copilot bubble, info chips |
| meter | `90deg, #84FAB0 → #D4FC79` | progress and score bars |
| grade | `150deg, #D4FC79 → #84FAB0 → #8FD3F4` | Rate My Team score ring |

### Light theme

Same proportions on a pale lime base: `--base #F2FBEC`, white glass, forest ink
(`#1B4332`, `#3D6B55`, `#55796A`). The accent turns forest so buttons stay
legible; `--accent-wash` keeps a lime tint behind active items.

### Contrast

All body and small text meets WCAG AA (4.5:1) on its background in both
themes. The tight ones: `--ink-3 #A8D4B9` (4.79:1 on hovered rows),
`--down #FFB3B3` (4.63:1), light `--ink-3 #55796A` (4.73:1). Re-check if you
change any of them.

## Tokens

| Group | Tokens |
| --- | --- |
| Background | `--base --base-hi --base-lo --orb-a…d --orb-op --grain-op` |
| Glass | `--glass --glass-2 --glass-3 --glass-line --glass-line-2 --glass-hi --solid --row --row-hi --well` |
| Text | `--ink --ink-2 --ink-3` |
| Highlight | `--accent --accent-hi --accent-ink --accent-2 --accent-wash --on-accent --grad-cta --grad-info --glow` |
| Semantic | `--up --down --warn` + `-wash` variants |
| Depth | `--sh-1 --sh-2 --sh-3 --sh-accent --scrim` |
| Chrome | `--chrome --chrome-strong` |
| Pitch | `--pitch-a --pitch-b --pitch-line` |

`theme-color` in `index.html`, `manifest.json` and `setTheme()` in `app.js`
must match `--base` (`#1B4332` dark, `#F2FBEC` light).

## Glass

- Live `backdrop-filter: blur()` only on floating chrome: `.nav-bar`,
  `.tabbar`, `.more-panel`, `.sheet`, `.ob-card`, `.adv-body`. These also get a
  tinted `--chrome` fill so they stay readable where blur isn't rendered.
- In-page cards are flat translucent glass (`--glass` + `--glass-line` +
  `--glass-hi`). Dozens of blurred cards make scrolling janky on phones.
- The backdrop is a radial gradient (`--base-hi → --base → --base-lo`) with
  four slowly drifting blurred orbs and a grain layer.

## Layout and breakpoints

| Width | Behaviour |
| --- | --- |
| ≥ 1700px | full labels in the top navigation |
| ≤ 1699px | compact navigation |
| ≤ 1180px | multi-column grids collapse |
| ≤ 1023px | **app shell**: top bar, floating tab dock (Home, Points, Solver, Copilot, More), More sheet, bottom-sheet details |
| ≤ 760px | phone sizing: tighter padding, smaller type, fluid pitch tokens |
| ≤ 380px | small-phone tweaks |

Hard rules: single-column grids use `minmax(0,1fr)`; nothing may be wider than
a 390px viewport (`.page{overflow-x:clip}`, `overflow-wrap:anywhere` on long
strings). The e2e suite scans for this.

## Logo

A club mug with a football dunked in it — deliberately not a robot, spark or
brain. Inline SVG, three copies in `index.html` (nav, welcome card, sprite)
with unique clip ids `mgClipNav`, `mgClipOb`, `mgClipSym`.

Colours: forest body and handle, sea-green band with a sky highlight, lime
mug face from `--grad-cta`, forest ball panels.

Animation (`mgSteam`, `mgBob`, `mgClink`, `mgHop`, `mgDunk`): steam rises, the
ball bobs; on hover the mug clinks and the ball hops; the welcome screen dunks
the ball once. `prefers-reduced-motion` stops all of it.

`frontend/icon.svg` is the app icon (lime → mint tile, forest mug).

## Voice

- Name: **Mug's Game FC**. Tagline: "Fantasy football is a mug's game. Might as
  well do the maths."
- Light British humour in empty states, loading lines and the welcome screen
  ("putting the kettle on", "just having a nose").
- Plain and exact in errors, numbers, buttons and advice. A manager acting on a
  number should never have to decode a joke.
- No club crests, sponsors, real kit designs, or other products' logos and copy.
  Shirts are plain silhouettes in club colours.

## Checklist for a UI change

1. Colours from tokens only — no new hex literals in components.
2. Text on lime/sky uses `--on-accent`.
3. Nothing to bump — the server fingerprints CSS/JS by content (see
   `ARCHITECTURE.md` → Freshness).
4. Run `npm --prefix tests test` — 0 failures, then look at the phone and
   desktop screenshots in `tests/screenshots/`.
