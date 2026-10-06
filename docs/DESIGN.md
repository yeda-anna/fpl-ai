# Design system

Everything visual lives in `frontend/styles.css` and reads from CSS custom
properties ("tokens") declared at the top. Change a token, not a component.

## Palette — 60 : 30 : 10

Every theme follows the same split. The highlights are the brand and never
change between themes.

| Share | Role | Used for |
| --- | --- | --- |
| **60%** | Background — the theme's base colour | page, backdrop, chrome tint |
| **30%** | Content — tinted glass over the base | cards, rows, borders, pitch |
| **10%** | Highlight — lime `#D4FC79`, sky `#8FD3F4` | primary buttons, active tab, selected path, key figures, badges |

Rules:

- Highlights are pale. Text **on** a highlight uses `--on-accent` (the theme's
  darkest colour), never white.
- Use lime for "do this" (CTA, active, captain) and sky for "information"
  (badges, the Copilot bubble, secondary charts).
- Keep highlights scarce. If a screen has more than one or two lime blocks,
  something should be demoted to glass.
- `--up`, `--down` and `--warn` sit outside the brand palette on purpose.

## Themes

Picked from the palette button in the top bar (desktop) or **More → Theme**
(phone). Stored in `localStorage.fplai_theme`; `dark`/`light` from older
versions map to `forest`/`chalk`.

| Theme | 60% base | 30% glass tint | Ink | Feel |
| --- | --- | --- | --- | --- |
| `forest` (default) | `#1B4332` | mint `rgba(214,255,226,…)` | `#F4FFF6` | the house colours |
| `midnight` | `#0E1726` | sky `rgba(200,226,255,…)` | `#F2F7FF` | floodlit navy |
| `graphite` | `#17191C` | neutral `rgba(255,255,255,…)` | `#F5F6F7` | matte charcoal, quietest |
| `chalk` | `#F2FBEC` | white `rgba(255,255,255,…)` | `#1B4332` | light; accent turns forest |
| `auto` | — | — | — | `chalk` when the system is light, otherwise `forest`; follows changes live |

Adding a theme:

1. Add a `[data-theme="<id>"]` block in `styles.css` overriding the background,
   glass, ink, semantic, shadow, chrome (`--chrome`, `--chrome-strong`,
   `--chrome-solid`), pitch and `--theme-color` tokens. Forest is the fallback
   for anything you leave out.
2. Add it to `THEMES` in `app.js` (name, one-line note, 60/30/10 swatch, and
   `color` = its base for the browser bar).
3. Add its base to the colour map in the pre-paint `<script>` in `index.html`.
4. Run the contrast check below, then the e2e suite (it walks every theme).

### Gradients

| Token | Value | Use |
| --- | --- | --- |
| `--grad-cta` | `135deg, #D4FC79 → #96E6A1` | primary buttons, active segments |
| `--grad-info` | `135deg, #84FAB0 → #8FD3F4` | Copilot bubble, info chips |
| meter | `90deg, #84FAB0 → #D4FC79` | progress and score bars |
| grade | `150deg, #D4FC79 → #84FAB0 → #8FD3F4` | Rate My Team score ring |

### Contrast

All text tokens meet WCAG AA (4.5:1) in every theme, measured against the
worst case: the brightest glass (`--glass-3`) over `--base-hi`.

| Theme | ink-3 (smallest text) | down | warn |
| --- | --- | --- | --- |
| forest | 4.90 | 4.82 | 5.20 |
| midnight | 4.88 | 6.24 | 7.55 |
| graphite | 4.76 | 6.41 | 7.76 |
| chalk | 4.57 | 4.77 | 5.55 |

Forest is the tight one: its base is a mid green, so its ink, `--down` and
`--warn` are lighter than the other dark themes'. Re-check after any colour
change.

## Tokens

| Group | Tokens |
| --- | --- |
| Background | `--base --base-hi --base-lo --orb-a…d --orb-op --grain-op --theme-color` |
| Glass | `--glass --glass-2 --glass-3 --glass-fill --glass-line --glass-line-2 --rim --glass-hi --solid --row --row-hi --well` |
| Text | `--ink --ink-2 --ink-3` |
| Highlight | `--accent --accent-hi --accent-ink --accent-2 --accent-wash --on-accent --grad-cta --grad-info --glow` |
| Semantic | `--up --down --warn` + `-wash` variants |
| Depth | `--sh-1 --sh-2 --sh-3 --sh-accent --scrim` |
| Chrome | `--chrome --chrome-strong --chrome-solid` |
| Pitch | `--pitch-a --pitch-b --pitch-line` |

`manifest.json` keeps forest (`#1B4332`) as the install colour; the live
browser-bar colour follows the chosen theme.

## Glass — crisp frosted

Panels look like clean frosted panes: evenly lit, one hairline of light along
the top edge, a soft shadow underneath. No coloured glows inside cards.

- **Fill:** `--glass-fill`, a gentle top-to-bottom gradient (slightly brighter
  at the top) of the theme's glass tint.
- **Edge:** a 1px `--glass-line` border, plus the **rim**: a `:before` hairline
  in `--rim` across the top, brightest in the middle and fading at the ends.
  Used on `.card`, `.tile`, `.path`, `.sheet`, `.ob-card`, `.more-panel`,
  `.tabbar` and `.theme-pop`.
- **Depth:** two-layer shadows (`--sh-1`/`--sh-2`): a tight contact shadow
  plus a wide soft one. Hover lifts 2px and brightens the border.
- **Blur:** live `backdrop-filter` only on floating chrome — `.nav-bar`,
  `.tabbar`, `.more-panel`, `.sheet`, `.ob-card`, `.adv-body`, `.theme-pop`.
  These use a tinted `--chrome` fill so they stay readable, and fall back to
  `--chrome-solid` where blur isn't supported. In-page cards never blur;
  dozens of blurred cards make scrolling janky on phones.
- **Backdrop:** radial gradient (`--base-hi → --base → --base-lo`), four slow
  orbs kept faint (`--orb-op` .06–.11 on dark themes) and a grain layer.
- **Focus:** keyboard focus shows a 2px `--accent-ink` ring; mouse clicks don't.

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
   desktop screenshots in `tests/screenshots/`, one per theme.
5. New colours: re-run the contrast check for all four themes.
