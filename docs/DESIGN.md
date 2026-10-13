# Design system

Everything visual lives in `frontend/styles.css` (tokens, components, layout),
`frontend/motion.js` (`FX`, animation), `frontend/magic.js` (`Magic`, the Magic UI
effects) and `frontend/intro.js` (`Intro`, the opening film). Colours are custom properties
("tokens") declared once in `:root`. Change a token, not a component.

## One look: race day

After a racing-game leaderboard: a dark teal night, flat surfaces, italic
**Chakra Petch** type, and everything you can press slanted like a speed stripe.
There is one theme and no theme picker.

| Role | Tokens |
| --- | --- |
| **The night** | `--bg #0a1214` (with a faint `--bg-hi #12201f` glow at the top), `--bg-2` |
| **Surfaces**: cards, tiles, rows, sheets | `--surface #172327`, `--surface-2 #1f2e33`, `--surface-3 #2a3b40` — flat and solid, no borders, no glass |
| **Text** | `--ink #f2f6f5`, `--ink-2 #cfd8da`, `--ink-3 #93a3a7` (labels); `--dim` is decoration only |
| **Colour** | lime `--lime #d2ff2e` (+ `--lime-soft #efffc4`), green `--green #2ee88f`, purple `--purple #6d5cff` / `--purple-2 #8b7bff`, `--bar-gray` |

What each colour means:

- **Lime** is "do this": the main button (a lime-soft/lime split, like a racing
  "TRADE" button), the open tab in the dock and top bar, the captain, gains and
  key figures (`--accent`, `--accent-ink`).
- **Green** is progress and information: the season race bar, the pitch scene's
  lines on the landing, good fixtures, `--up`.
- **Purple** is "selected" and measurement: the chosen sub-page in the section
  switcher, the chosen gameweek, the vice-captain, projection bars and sparklines.

Rules:

- **The slant.** Buttons, chips, tabs and badges lean (`--skew: -12deg`). Buttons
  draw their shape as a skewed `::before` behind an upright label, so the focus
  ring follows the slant (`--fill` sets the colour); small chips and strips use a
  parallelogram `clip-path`. New pressable things join the selector list in "the
  slant" block of `styles.css`.
- **Italic for voice.** Titles, labels, numbers and buttons are italic
  Chakra Petch; long running text (descriptions, legends, the tour) stays upright.
- **Flat.** No glass, no glows behind words, no borders on cards. Depth comes
  from the three surface steps.
- Text on a lime, green, warn or down fill uses `--on-accent` (`#0a1214`); on
  purple, `--on-purple` (white).
- Contrast: `python3 scripts/check_contrast.py` checks every text token on
  `--surface-2` (and the main ones on `--surface-3`), and the text on each fill,
  and exits 1 below WCAG AA.

| Text on | ink | ink-2 | ink-3 | accent | up | down | warn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `--surface-2` | 12.88 | 9.68 | 5.37 | 12.08 | 8.72 | 5.56 | 9.16 |

### Pieces

| Piece | How |
| --- | --- |
| **Page head** | an italic breadcrumb (`Plan / Transfers · GW8`), the title, "*n* gameweeks left", and the **season race bar**: a segment a gameweek, lime to green up to now, the next one outlined, the rest grey (`raceBar()` in `app.js`) |
| **Ticker** | the deadline line, with a small pulse icon |
| **Section switcher** | a slanted strip on `--surface`; the open sub-page on a purple slanted pill that slides |
| **Dock** (phone) | a `--surface-2` slab; the open tab on a lime slanted stripe |
| **Buttons** | `.btn` on `--surface-2`; `.btn.primary` and `.cta` in the lime split, italic, letter-spaced |
| **Tiles** | a muted italic label, a big italic number |
| **Tables** | rows straight on the surface with hairlines between, italic bold numbers |
| **Chips** | `.pill` position badges (GKP warn, DEF purple, MID green, FWD lime), `.tag` gain chips, `.fdr` fixture squares — all slanted |
| **Bars** | `.meter`: purple over a hatched grey track, slanted like a portfolio split; sparklines in purple |
| **Pitch** | dark turf with lime markings and a glow from the touchline; player cards on `--surface-2` with lime xPts; captain a lime badge, vice purple |
| **Sheets** | `--surface-2`, round; on a phone a bottom tray with a grabber |
| **Avatars** | a small skewed square in a purple gradient |

The font is vendored: Chakra Petch 400–700 (upright and italic, latin subset)
from `@fontsource/chakra-petch`, OFL, in `frontend/vendor/fonts/`.

## The opening film

Every launch opens with a few seconds of titles while the app loads underneath
(`intro.js`, a [Theatre.js](https://www.theatrejs.com/docs/latest) sequence):

| Time | What happens | Theatre object |
| --- | --- | --- |
| 0 – 0.6 s | letterbox bars close in; REC light, the drone count and timecode | `Bars`, `Hud` |
| 0 – 0.9 s | a retro grid floor (Magic UI Retro Grid) where the drones wait in rows | `Floor` |
| 0.4 – 3.0 s | the drones lift off in a wave (back rows last), swoop up and fly to their places | `Swarm.gather` |
| 2.65 – 3.05 s | they light up in the portrait's colours with a flash; then they hover | `Swarm.ignite/glow/hover`, `Flash` |
| 2.95 – 3.65 s | the drones dim as the portrait itself (`portrait.webp`) comes up beneath them | `Swarm.photo` |
| 3.1 – 4.0 s | the name decodes (HyperText) as its letters track in | `Title` |
| 3.75 – 4.85 s | the tagline types itself — a villain's one-liner, a different one each launch (`QUIPS.intro`): "Free transfer? Yahan kuch bhi free nahi milta." | `Line` |
| 4.85 – 10.85 s | the tagline holds, the drones hovering over the portrait | — |
| 10.85 – 11.45 s | the camera pushes into the portrait and the film irises open onto the app | `Camera`, `Iris` |

- The drones are `PORTRAIT` (`portrait.js`, generated): every light in the
  portrait, with its colour from a 32-colour palette. A canvas draws each as a
  glowing sprite, flying a curve from its slot on the pad to its place in the
  portrait (the `#inMark` box, which holds the picture), eased per drone from
  `Swarm.gather`. The picture's edges are feathered so it has no frame.
- The keyframes are numbers in `KEYS` (`intro.js`): `[seconds, value, easing to
  the next]`. They're turned into Theatre's project state at load — the JSON that
  Theatre Studio would export — so a change to the film is a change to `KEYS`.
  Theatre Studio itself (AGPL) is a development tool and is not shipped.
- Each object's `onValuesChange` writes custom properties (`--bars`, `--zoom`,
  `--hole` …) on `#intro`; the CSS in the "opening film" block does the rest. The
  playhead (`sequence.pointer.position`) drives the timecode and the scrubber.
- Skip at any time: tap anywhere, Esc/Enter/Space, or "Skip intro" — it jumps to
  the outro rather than cutting. The menu's **Opening film** switch turns it off
  for the device (`fplai_intro`), and "Watch it now" replays it.
- It never plays under reduced motion, when it's switched off, or when the app
  reloads itself (a new build, a back/forward restore) — a script in `<head>`
  decides before the first paint (`no-intro`). A page that took over 9 seconds
  to arrive skips it too, and a 15-second CSS failsafe hides it if scripts fail.
- The drones keep the portrait's own colours; the film's chrome (title, tagline,
  progress line, Skip) and its grid floor use the race-day colours.
- The app never waits on it: views render underneath, and their entrances are
  held (`FX.hold(Intro.reveal)`) until the iris starts to open, so the app
  materialises as the film ends.

## Magic UI, rebuilt

[Magic UI](https://magicui.design) is React + Tailwind, so its components are
rebuilt in plain JS (`magic.js`) and CSS (the "Magic UI" block of `styles.css`),
following the originals (MIT, `frontend/vendor/magicui-LICENSE.md`).

| Component | Where |
| --- | --- |
| HyperText | page titles when they change, the film's title, the name in the top bar on hover |
| Typing Animation | the landing boot lines; the film's log entry |
| Ripple, Orbiting Circles | round the landing logo; the film's logo |
| Border Beam | every loading card, the chosen plan in Plan → Transfers |
| Shimmer Button | kept in the markup of "Let's go" and "Suggest transfers" but hidden: on a slanted button it reads as noise |
| Animated Beam | from the player out to the player in, in the transfer timeline and Grade's upgrades |
| Retro Grid | the film's floor |
| Scroll Progress | a lime-to-green line under the top bar (Motion's `scroll()`) |
| Blur Fade, Number Ticker, Animated List | cards, figures, and the Copilot's and Grade's reasons (Motion, in `motion.js`) |

## Navigation

Five tabs, nothing hidden behind "More". Sub-pages are picked from the section
switcher under the title.

| Tab | Sub-pages |
| --- | --- |
| **Home** (titled with your team's name) | My squad · Grade · Picks |
| **Plan** | Transfers · Chips |
| **Players** | Projections · Compare · Prices · Line-ups · Set pieces · DEFCON |
| **Leagues** | Mini-league |
| **Ask** | Copilot |

- Desktop: the tabs sit in the top bar. Phone (≤ 1023px): a floating dock.
- Every sub-page has its own address (`#plan/chips`). Old single-view addresses
  (`#solver`, `#xpts`, `#rate` …) are mapped to the new places, and `#model`
  opens the menu.
- The ⓘ button opens the menu sheet: change team, refresh the app, forget the
  team, the opening film's switch, and How it works.

## Landing: the Team ID, asked once

The first visit on a device opens the landing screen: a pitch drawn in lines, the logo,
and one field for the FPL Team ID. Once entered, the ID is stored in
`localStorage` (`fplai_team`, `fplai_team_name`) and every later visit goes
straight to Home → My squad without asking. The team pill and the menu change or
forget it. "Just browsing" skips it and lands on Picks; team-only pages then
offer to add a team.

## Motion

Five libraries, vendored in `frontend/vendor/` (no CDN), each doing what it's
best at: GSAP for SVG drawing and timelines, anime.js for icons,
Motion for springs, in-view and scroll, AutoAnimate for lists that change, and
Theatre.js for the opening film. It lives in `motion.js` (`FX`), `magic.js` and
`intro.js`, and every function is safe to call when a library failed to load or
the visitor prefers reduced motion. (The global `Motion` is the motion.dev
library; our layer is `FX`.)

| Effect | Library | Where |
| --- | --- | --- |
| Landing: pitch lines and the goal **draw themselves**, the logo powers on, then the ball flies along a dotted path into the net, the net ripples and **GOAL!** flashes — on a loop | GSAP timeline + DrawSVGPlugin + MotionPathPlugin; anime.js | landing |
| The tab icon **draws itself** when its tab lights up | anime.js | dock, top bar |
| The dock capsule and the section pill **slide** to the active item with a little overshoot | GSAP `elastic` | dock, switcher |
| The season race bar's segments pop up one after another on every tab change | GSAP stagger | page head |
| Views fade up; new cards, tiles and plans **blur-fade in one after another** — the ones further down as you scroll to them (Magic UI Blur Fade) | Motion `animate` + `stagger` + `inView`, inline styles cleared after (so hover transforms still work) | every view |
| Figures **tick up** to their value on a spring, when they come into view (Magic UI Number Ticker) | Motion spring | tiles, solver, grade |
| Buttons give a **springy press** | Motion spring | all buttons |
| The projections table **glides into its new order** when you sort or filter (each player keeps his row); new rows from "Show 40 more" fade in | AutoAnimate on keyed rows (`syncRows`) | Players → Projections |
| The Copilot keeps a **log**: each answer is an entry, newest on top; older ones slide down and fold | AutoAnimate | Ask |
| Reasons **drop in one by one** (Magic UI Animated List) | Motion spring + stagger | Ask, Grade |
| A lime-to-green line under the top bar fills as you scroll (Magic UI Scroll Progress) | Motion `scroll()` | top bar |
| The opening film | Theatre.js sequence | launch |
| A wrong Team ID gets a head-shake | GSAP | landing |
| Confetti for a +15 week, an A grade, a plan that gains, and five taps on the logo | canvas | global |

Cheap loops stay in CSS: the loader (a lime dash running along a path), bars,
sparklines and race-bar segments growing, and the players walking onto the pitch.
There is no meteor shower, no sky animation, no scanlines and no corner brackets:
the background is still.

`prefers-reduced-motion`: the CSS rule turns every animation off, there is no
opening film, and `FX.reduced` makes the JS effects leave things in their
finished state. Nothing counts up, nothing is ever hidden waiting for an
animation. (AutoAnimate checks the preference itself.)

Keep new motion on `transform`/`opacity` (and a little `filter` for the blur
fade), never animate layout, never animate one element with two libraries at
once, and clear inline styles when an animation ends (GSAP `clearProps`, Motion
`.then`, anime.js `onComplete`).

## Surfaces and focus

- **Fill:** flat `--surface` cards on the `--bg` night; `--surface-2` for sheets,
  inputs' neighbours and secondary buttons; `--surface-3` for hovers and chips.
- **Blur:** live `backdrop-filter` only on floating chrome — `.nav-bar`, `.dock`,
  `.toast`. Cards and sheets are solid.
- **Focus:** a lime ring; on slanted buttons it's drawn round the slanted shape.
  Inputs show focus by turning their border lime. Mouse clicks don't show it.

## Layout and breakpoints

| Width | Behaviour |
| --- | --- |
| ≤ 1180px | multi-column grids collapse; the team pill shows only its avatar |
| ≤ 1023px | **app shell**: top bar, floating dock with five tabs, bottom-sheet details |
| ≤ 760px | phone sizing: tighter padding, smaller type, fluid pitch; the section switcher spans the width and scrolls |
| ≤ 380px | small-phone tweaks |

Hard rules: single-column grids use `minmax(0,1fr)`; nothing may be wider than a
390px viewport (`.page{overflow-x:clip}`, `overflow-wrap:anywhere` on long
strings). The e2e suite scans for this.

## Logo

The **drone portrait** the owner supplied — a face made of points of light in
magenta, violet and blue — used as it is. `scripts/digitize.py <image>` writes
`portrait.webp` (the whole picture, for the film), `logo.webp` (a square crop
round the face), `icon-180.png` (iOS home screen), `icon-192/512.png` (the
manifest and favicon) and `portrait.js` (the film's ~2,600 drones, traced from
the picture's own lights). The `<symbol id="logo">` in `index.html` holds
`logo.webp`; every logo in the app is a `<use>` of it, clipped to its slot (a
rounded square in the top bar, a circle on the landing card and the avatar),
without a glow (`.neon-logo`). Don't edit the generated files by hand.

## Voice

- Name: **Papa Ranjeet**. Tagline: "Football’s a funny old game. Might as well do the
  maths."
- Light British humour and Indian dark humour on the landing screen, under the
  loader ("putting the kettle on", "Sharma ji’s son finished this ages ago") and
  in the film's tagline, a one-liner in the manner of a 70s Hindi-film villain
  ("Hit lega? Le le. Points main le jaaunga."). They're written for the app,
  not quotes from any actor or film.
  The lines live in `QUIPS` in `app.js`, aimed at the manager's own luck, never
  at a religion, caste, region, community, body or real person.
- **The week's verdict.** On Home the title is the team's own name from FPL, and
  My squad opens with a dark football roast of the last gameweek in place of a
  description: one line from `SCORE_ROASTS`, picked by the score against the
  average (great, above, level, below, awful, no average yet, no games yet) and
  seeded by team and gameweek so it doesn't change on a re-render. It's set in
  italics in the page head and fades in once the score is known. It may quote
  the score; it never gives advice.
- Plain and exact in errors, numbers, buttons and advice. A manager acting on a
  number should never have to decode a joke.
- No club crests, sponsors, real kit designs, or other products' logos and copy.
  Shirts are plain silhouettes in club colours.

## Checklist for a UI change

1. Colours from tokens only — no new hex literals in components (the pitch cards
   and SVG art are the exceptions).
2. Text on a lime/green/warn/down fill uses `--on-accent`; on purple, `--on-purple`. Pressable things slant (join "the slant" block).
3. Nothing to bump — the server fingerprints CSS/JS by content, vendor files
   included (see `ARCHITECTURE.md` → Freshness).
4. New colours: `python3 scripts/check_contrast.py`.
5. New motion: put it in `motion.js` (or `magic.js` for a Magic UI effect), make
   it a no-op when `reduced` or the library is missing, and check it with
   "reduce motion" on.
6. Run `npm --prefix tests test` — 0 failures — then look at the phone and
   desktop screenshots in `tests/screenshots/`.
