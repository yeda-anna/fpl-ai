# Design system

Everything visual lives in `frontend/styles.css` and reads from CSS custom
properties ("tokens") declared at the top. Change a token, not a component.

## Palette — 60 : 30 : 10

Every theme follows the same split.

| Share | Role | Used for |
| --- | --- | --- |
| **60%** | Background — the theme's base colour | page, backdrop, chrome tint |
| **30%** | Content — tinted glass over the base | cards, rows, borders, pitch |
| **10%** | Highlight — a primary and a secondary | primary buttons, active tab, selected path, key figures, badges, glow |

The primary highlight is lime `#D4FC79` in every theme but Dark Roast, where it
is saffron `#FFB454`. The secondary (`--accent-2`) is sky `#8FD3F4` in the green,
navy and charcoal themes, hot pink in Open Mic and ember in Dark Roast. The
secondary is what glows.

Rules:

- Highlights are pale. Text **on** a highlight uses `--on-accent` (the theme's
  darkest colour), never white.
- Use the primary for "do this" (CTA, active, captain) and the secondary for
  glow and "information" (the Copilot bubble, the verdict border, rings).
- Keep highlights scarce. If a screen has more than one or two lime blocks,
  something should be demoted to glass.
- `--up`, `--down` and `--warn` sit outside the brand palette on purpose.

## Themes

Picked from the palette button in the top bar (desktop) or **More → Theme**
(phone). Stored in `localStorage.fplai_theme`; `dark`/`light` from older
versions map to `forest`/`chalk`. A first visit opens in `openmic`.

| Theme | 60% base | 30% glass tint | Ink | Feel |
| --- | --- | --- | --- | --- |
| `openmic` (default) | `#140B26` | lilac `rgba(226,214,255,…)` | `#FBF8FF` | a stage-lit comedy room: violet, lime and hot pink |
| `roast` | `#1D120C` | cream `rgba(255,228,196,…)` | `#FFF8EE` | Dark Roast: espresso, saffron and ember |
| `forest` | `#1B4332` | mint `rgba(214,255,226,…)` | `#F4FFF6` | the original house colours |
| `midnight` | `#0E1726` | sky `rgba(200,226,255,…)` | `#F2F7FF` | floodlit navy |
| `graphite` | `#17191C` | neutral `rgba(255,255,255,…)` | `#F5F6F7` | matte charcoal, quietest |
| `chalk` | `#F2FBEC` | white `rgba(255,255,255,…)` | `#1B4332` | light; accent turns forest |
| `auto` | — | — | — | `chalk` when the system is light, otherwise `openmic`; follows changes live |

Adding a theme:

1. Add a `[data-theme="<id>"]` block in `styles.css` overriding the background,
   glass, ink, semantic, shadow, chrome (`--chrome`, `--chrome-strong`,
   `--chrome-solid`), pitch and `--theme-color` tokens, plus the stage tokens
   (`--glow --glow-2 --beam --beam-2 --beam-op --meter-a --meter-b --grad-grade
   --ring-a --ring-b --roast-wash --roast-line`). Forest is the fallback for
   anything you leave out.
2. Add it to `THEMES` in `app.js` (name, one-line note, 60/30/10 swatch, and
   `color` = its base for the browser bar).
3. Add its base to the colour map in the pre-paint `<script>` in `index.html`.
4. Run `python3 scripts/check_contrast.py`, then the e2e suite (it walks every
   theme; update the expected theme count and `COLORS` map in `tests/e2e.js`).

### Gradients

| Token | Value | Use |
| --- | --- | --- |
| `--grad-cta` | forest: `135deg, #D4FC79 → #96E6A1` (each theme sets its own) | primary buttons, active segments, the roast flame chip |
| `--grad-info` | forest: `135deg, #84FAB0 → #8FD3F4` (Open Mic: pink → violet) | Copilot bubble, info chips |
| `--meter-a` → `--meter-b` | forest: `#84FAB0 → #D4FC79` | progress and score bars |
| `--grad-grade` | forest: `150deg, #D4FC79 → #84FAB0 → #8FD3F4` | the Rate My Team grade letter |
| `--ring-a` → `--ring-b` | forest: `#D4FC79 → #8FD3F4` | the Rate My Team score ring |

### Contrast

All text tokens meet WCAG AA (4.5:1) in every theme, measured against the
worst case: the brightest glass (`--glass-3`) over `--base-hi`. Text on a
highlight (`--on-accent`) is measured against both ends of each highlight
gradient. `python3 scripts/check_contrast.py` does all of it and exits 1 on a
miss.

| Theme | ink-3 (smallest text) | down | warn |
| --- | --- | --- | --- |
| openmic | 6.14 | 6.50 | 8.70 |
| roast | 5.71 | 5.77 | 8.88 |
| forest | 4.90 | 4.82 | 5.20 |
| midnight | 4.88 | 6.24 | 7.55 |
| graphite | 4.76 | 6.41 | 7.76 |
| chalk | 4.84 | 5.05 | 5.88 |

Forest is the tight one: its base is a mid green, so its ink, `--down` and
`--warn` are lighter than the other dark themes'. Re-check after any colour
change.

## Tokens

| Group | Tokens |
| --- | --- |
| Background | `--base --base-hi --base-lo --orb-a…d --orb-op --grain-op --theme-color` |
| Stage | `--glow --glow-2 --beam --beam-2 --beam-op --meter-a --meter-b --grad-grade --ring-a --ring-b --roast-wash --roast-line` |
| Glass | `--glass --glass-2 --glass-3 --glass-fill --glass-line --glass-line-2 --rim --glass-hi --solid --row --row-hi --well` |
| Text | `--ink --ink-2 --ink-3` |
| Highlight | `--accent --accent-hi --accent-ink --accent-2 --accent-wash --on-accent --grad-cta --grad-info --glow` |
| Semantic | `--up --down --warn` + `-wash` variants |
| Depth | `--sh-1 --sh-2 --sh-3 --sh-accent --scrim` |
| Chrome | `--chrome --chrome-strong --chrome-solid` |
| Pitch | `--pitch-a --pitch-b --pitch-line` |

`manifest.json` uses Open Mic (`#140B26`) as the install colour; the live
browser-bar colour follows the chosen theme.

## Glass — crisp frosted

Panels look like clean frosted panes: evenly lit, one hairline of light along
the top edge, a soft shadow underneath. Glow is allowed on edges, on things you
can press and on highlights (see **Stage** below) — never as a coloured wash
behind running text.

- **Fill:** `--glass-fill`, a gentle top-to-bottom gradient (slightly brighter
  at the top) of the theme's glass tint.
- **Edge:** a 1px `--glass-line` border, plus the **rim**: a `:before` hairline
  in `--rim` across the top, brightest in the middle and fading at the ends.
  Used on `.card`, `.tile`, `.path`, `.sheet`, `.ob-card`, `.more-panel`,
  `.tabbar` and `.theme-pop`.
- **Depth:** two-layer shadows (`--sh-1`/`--sh-2`): a tight contact shadow
  plus a wide soft one. Hover lifts 2px and brightens the border.
- **Blur:** live `backdrop-filter` only on floating chrome — `.nav-bar`,
  `.tabbar`, `.more-panel`, `.sheet`, `.ob-card`, `.adv-body`, `.theme-pop`,
  `.toast`.
  These use a tinted `--chrome` fill so they stay readable, and fall back to
  `--chrome-solid` where blur isn't supported. In-page cards never blur;
  dozens of blurred cards make scrolling janky on phones.
- **Backdrop:** radial gradient (`--base-hi → --base → --base-lo`), four slow
  orbs (`--orb-op` .06–.22), two sweeping stage-light beams and a grain layer.
- **Focus:** keyboard focus shows a 2px `--accent-ink` ring; mouse clicks don't.

## Stage — glow, light and motion

Everything below reads the tokens, so each theme lights itself. It all lives in
the "Stage" section at the end of `styles.css` plus the stage block in `app.js`.
`prefers-reduced-motion` switches all of it off (content simply appears; only the
loading ring keeps turning, slowly).

| Effect | How | Where |
| --- | --- | --- |
| **Stage lights** | two `.beam` conic wedges rotating slowly from the top, `mix-blend-mode:screen`, strength `--beam-op` | backdrop |
| **Pointer glow** | a masked radial gradient on `.card` / `.tile` `:after`, centred on `--mx/--my` set from `pointermove` (hover devices only) | cards, tiles |
| **Breathing glow** | `breathe` keyframes on the primary button and the selected plan; `mark-glow` on the logo tile; `cap-pulse` ring on the captain badge | CTAs, logo, pitch |
| **Entrances** | new cards, tiles, plans and gameweek chips get `.fx-in` with a stagger (`--i`, max 11) from a `MutationObserver`; fill mode is `backwards` so hover transforms still work | every view |
| **Count-up** | the first text node of `.tile .val`, `.stat-v`, `.path .pv`, `.gw-score`, `.gw-c .v`, `.cu` animates to its value in 700 ms; skipped when it isn't a plain figure | dashboard, solver, rate |
| **Players walk on** | `pop-in` per shirt, delayed by row (`--r`) and column (`--c`) | pitch |
| **Bars and ring** | `grow-x` on meters, `grow-y` on sparklines, `ring-fill` on the Rate My Team ring (`--p` = score) | rate, tables |
| **Verdict border** | `@property --ang` rotated by `ang`, drawn as a conic gradient behind `.roast-hero` and as a masked ring on `.ob-card` | dashboard, welcome |
| **Tab capsule** | `#tabbar` gets `--tx/--tw` from the active button; `.tabbar:after` slides with an overshoot curve | phone dock |
| **Heading glint** | `.sweep` on `#view-title` on every navigation | page head |
| **Theme cross-fade** | `html.theming` for 600 ms makes colours transition | theme picker |
| **Confetti** | one `<canvas id="fx">`, coloured from `--accent --accent-2 --warn --up --ink`; fired for a +15 week, a Rate My Team A, a solver plan that gains, and five taps on the logo | global |
| **Toast** | `#toast`, top of the screen, 2.8 s | roast switch, easter egg |

Keep new motion on `transform`/`opacity` where you can, give anything that
loops a reason, and never animate layout. If you add an infinite animation,
check the reduced-motion rule covers it (it matches `*, *:before, *:after`).

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
- Light British humour and Indian dark humour in empty states, loading lines
  and the welcome screen ("putting the kettle on", "just having a nose",
  "Sharma ji’s son finished this ages ago").
- **Roasts**: a deadpan roast under each suggestion, in the register of stage
  roast comedy — short setup, flat delivery, a punchline that lands on the
  manager's own choices; chess blunders, cricket, engineering college and Indian
  households are fair game. All lines are original and live in `roast.js`
  (templated with `{c1}`, `{out}` … slots). They are never attributed to a real
  comedian and never reuse anyone's material.
- The rules for a roast: aim at the manager's own luck, rank and decisions,
  never at a religion, caste, region, community, body, family tragedy or real
  person, and never at anything serious. It is a **separate aside** (`.roast`,
  flame chip, labelled "Roast:" for screen readers) under the suggestion — never
  inside the advice, a number or an error. **Roast mode** (More → Theme) turns
  every roast, quip and verdict off; keep it working when you add one.
- Plain and exact in errors, numbers, buttons and advice. A manager acting on a
  number should never have to decode a joke.
- No club crests, sponsors, real kit designs, or other products' logos and copy.
  Shirts are plain silhouettes in club colours.

## Checklist for a UI change

1. Colours from tokens only — no new hex literals in components (the pitch and
   the chips on it are the exception: they stay grass-green in every theme).
2. Text on a highlight uses `--on-accent`.
3. Nothing to bump — the server fingerprints CSS/JS by content (see
   `ARCHITECTURE.md` → Freshness).
4. Run `npm --prefix tests test` — 0 failures, then look at the phone and
   desktop screenshots in `tests/screenshots/`, one per theme.
5. New colours: `python3 scripts/check_contrast.py` — all six themes.
6. New motion: check it with "reduce motion" on, and that it doesn't pin a
   `transform` that hover needs (use `animation-fill-mode: backwards`).
7. New suggestion: give it a roast (`roast.js` + `roastHtml()`), as a separate
   aside, and check Roast mode off removes it.
