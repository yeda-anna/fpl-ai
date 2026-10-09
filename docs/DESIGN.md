# Design system

Everything visual lives in `frontend/styles.css` (tokens, components, layout),
`frontend/motion.js` (`FX`, animation), `frontend/magic.js` (`Magic`, the Magic UI
effects) and `frontend/intro.js` (`Intro`, the opening film). Colours are custom properties
("tokens") declared once in `:root`. Change a token, not a component.

## One look: neon

A stadium at night. There is one theme and no theme picker: every screen, every
device, the same look.

| Share | Role | Tokens |
| --- | --- | --- |
| **60%** | The night: near-black violet | `--base #07051A`, `--base-hi #140C33`, `--base-lo #030210` |
| **30%** | Dark glass: cards, rows, wells | `--glass-fill`, `--glass*`, `--row*`, `--well`, `--solid` |
| **10%** | Three neons | lime `--neon-l #C8FF3D`, cyan `--neon-c #22F0FF`, magenta `--neon-m #FF3DCB` |

What each neon means:

- **Lime** is "do this": primary buttons, the active tab, the selected plan, the
  captain, key figures (`--accent`, `--accent-ink`).
- **Cyan** is lines and information: the pitch markings, the sky's wires, focus
  rings, pointer glow, the title line (`--accent-2`, `--glow-2`).
- **Magenta** is the ball and celebration: the goal, glows, the grade ring's end
  (`--glow`).

Rules:

- Neon is light, so it lives on **strokes, edges and things you can press** —
  never as a wash behind running text. Cards are dark and nearly solid so the
  sky's wires never run behind words.
- Text on a neon fill uses `--on-accent` (`#0A0620`), never white.
- `--up`, `--down` and `--warn` sit outside the neons on purpose.
- Contrast: every text token passes WCAG AA against the worst case (the
  brightest glass over `--base-hi`), and `--on-accent` passes on every highlight
  gradient. `python3 scripts/check_contrast.py` checks it and exits 1 on a miss.

| Token | ink | ink-2 | ink-3 | accent | up | down | warn |
| --- | --- | --- | --- | --- | --- | --- | --- |
| contrast | 13.83 | 9.52 | 6.47 | 12.78 | 11.64 | 7.05 | 10.41 |

### Gradients

| Token | Value | Use |
| --- | --- | --- |
| `--grad-cta` | `135deg, lime → cyan` | primary buttons, the active section pill |
| `--grad-info` | `135deg, #FF8BE3 → #8EA6FF` | the Copilot bubble |
| `--meter-a → --meter-b` | cyan → lime | progress and score bars |
| `--grad-grade` | lime → cyan → magenta | the Rate My Team grade letter |
| `--ring-a → --ring-b` | lime → magenta | the Rate My Team score ring |
| `#neonStroke` (SVG) | lime → cyan → magenta | the line under each page title |

## The HUD layer

Over the neon sits a sci-fi console: the app reads like a ship's HUD without
changing a single page or flow. It lives in the "HUD" block of `styles.css`.

| Piece | How |
| --- | --- |
| **Target-lock corners** on `.card`, `.tile`, `.plan`, `.path`, `.sheet` | `--hud-corners`: eight thin linear gradients painted as the top background layer, coloured by `--bk` (cyan; lime on hover; dark on a lime fill) |
| **Readouts** | `--hud` (system monospace stack) in uppercase with letter-spacing for labels, card titles, tabs, the switcher, table heads, tags and buttons. Body copy and numbers in tiles stay in the main face |
| **Eyebrow** | `#view-eyebrow` above the title: `SYS//<TAB>/<SUB> · GW<n>`, set by `syncHead()`, with a blinking lime status light and a glint sweeping across (Magic UI Animated Shiny Text) |
| **Decoding titles** | the page title scrambles and resolves left to right when it changes (Magic UI HyperText) |
| **Screen texture** | `body:after` CRT scanlines; `.backdrop .dots` dot grid; `.backdrop .beam` a slow scan beam |
| **Hologram pitch** | `.turf:before` scanlines and `.turf .sweep`, a light band running down the turf |
| **Boot sequence** | `#boot` on the landing card, typed one character at a time (Magic UI Typing Animation) in `FX.landingIn` |
| **Orbit** | round the landing logo: rings breathing out (Magic UI Ripple) and two satellites (Magic UI Orbiting Circles) |

Rules: the texture stays faint (scanlines and grid never compete with text);
corner brackets are decoration only, never a wash; radii are tight (`--r-sm`
4px … `--r-xl` 14px). Every loop here is CSS and switches off under
`prefers-reduced-motion`.

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
| Meteors | a shower across the night sky behind every page (18 on a phone, up to 36 on a wide screen). Each one falls to the grid floor and strikes it (`Magic.impact`): a flash, two shockwaves rolling out flat across the floor, sparks thrown up and a glowing crater that cools, while the floor flares for a moment. More over the landing pitch |
| Ripple, Orbiting Circles | round the landing logo; the film's logo |
| Border Beam | every loading card, the chosen plan in Plan → Transfers |
| Shimmer Button | "Let's go" and "Suggest transfers" (the spark races while the solver works) |
| Animated Beam | from the player out to the player in, in the transfer timeline and Grade's upgrades |
| Retro Grid | the floor of the night sky; the film's floor |
| Animated Shiny Text | the eyebrow above each title |
| Scroll Progress | a neon line under the top bar (Motion's `scroll()`) |
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

- Desktop: the tabs sit in the top bar. Phone (≤ 1023px): a floating neon dock.
- Every sub-page has its own address (`#plan/chips`). Old single-view addresses
  (`#solver`, `#xpts`, `#rate` …) are mapped to the new places, and `#model`
  opens the menu.
- The ⓘ button opens the menu sheet: change team, refresh the app, forget the
  team, the opening film's switch, and How it works.

## Landing: the Team ID, asked once

The first visit on a device opens the landing screen: a neon pitch, the logo,
and one field for the FPL Team ID. Once entered, the ID is stored in
`localStorage` (`fplai_team`, `fplai_team_name`) and every later visit goes
straight to Home → My squad without asking. The team pill and the menu change or
forget it. "Just browsing" skips it and lands on Picks; team-only pages then
offer to add a team.

## Motion

Five libraries, vendored in `frontend/vendor/` (no CDN), each doing what it's
best at: GSAP for SVG drawing and timelines, anime.js for the sky and icons,
Motion for springs, in-view and scroll, AutoAnimate for lists that change, and
Theatre.js for the opening film. It lives in `motion.js` (`FX`), `magic.js` and
`intro.js`, and every function is safe to call when a library failed to load or
the visitor prefers reduced motion. (The global `Motion` is the motion.dev
library; our layer is `FX`.)

| Effect | Library | Where |
| --- | --- | --- |
| Landing: pitch lines and the goal **draw themselves**, the logo flickers on like a neon sign, then the ball flies along a dotted path into the net, the net ripples and **GOAL!** flashes — on a loop | GSAP timeline + DrawSVGPlugin + MotionPathPlugin; anime.js flicker | landing |
| The sky: three neon wires across the background, each with a **pulse of light** travelling along it | anime.js `svg.createDrawable` | backdrop |
| The tab icon **draws itself** when its tab lights up | anime.js | dock, top bar |
| The dock capsule and the section pill **slide** to the active item with a little overshoot | GSAP `elastic` | dock, switcher |
| The neon line under the title redraws on every tab change | GSAP DrawSVG | page head |
| Views fade up; new cards, tiles and plans **blur-fade in one after another** — the ones further down as you scroll to them (Magic UI Blur Fade) | Motion `animate` + `stagger` + `inView`, inline styles cleared after (so hover transforms still work) | every view |
| Figures **tick up** to their value on a spring, when they come into view (Magic UI Number Ticker) | Motion spring | tiles, solver, grade |
| Buttons give a **springy press** | Motion spring | all buttons |
| The projections table **glides into its new order** when you sort or filter (each player keeps his row); new rows from "Show 40 more" fade in | AutoAnimate on keyed rows (`syncRows`) | Players → Projections |
| The Copilot keeps a **log**: each answer is an entry, newest on top; older ones slide down and fold | AutoAnimate | Ask |
| Reasons **drop in one by one** (Magic UI Animated List) | Motion spring + stagger | Ask, Grade |
| A neon line under the top bar fills as you scroll (Magic UI Scroll Progress) | Motion `scroll()` | top bar |
| The opening film | Theatre.js sequence | launch |
| A wrong Team ID gets a head-shake | GSAP | landing |
| The neon logo in the top bar flickers every few seconds | anime.js | top bar |
| Confetti for a +15 week, an A grade, a plan that gains, and five taps on the logo | canvas | global |

Cheap loops stay in CSS: the loader (a neon dash running along a path), the
breathing glow on the primary button and the selected plan, the captain's ring,
bars and sparklines growing, and the players walking onto the pitch.

`prefers-reduced-motion`: the CSS rule turns every animation off, there is no
opening film, and `FX.reduced` makes the JS effects leave things in their
finished state. Nothing counts up, nothing is ever hidden waiting for an
animation. (AutoAnimate checks the preference itself.)

Keep new motion on `transform`/`opacity` (and a little `filter` for the blur
fade), never animate layout, never animate one element with two libraries at
once, and clear inline styles when an animation ends (GSAP `clearProps`, Motion
`.then`, anime.js `onComplete`).

## Glass and light

- **Fill:** `--glass-fill`, dark violet and nearly solid, with a 1px
  `--glass-line` border and the **rim**: a `:before` hairline across the top.
- **Pointer glow:** on hover devices, a neon edge (cyan into magenta) follows
  the pointer around `.card` and `.tile` (`--mx/--my`, a masked radial gradient).
- **Blur:** live `backdrop-filter` only on floating chrome — `.nav-bar`, `.dock`,
  `.sheet`, `.land-card`, `.adv-body`, `.toast`. In-page cards never blur.
- **Pitch:** dark turf with cyan neon markings and a cyan glow around the card.
- **Focus:** a cyan ring with a soft glow; mouse clicks don't show it.

## Layout and breakpoints

| Width | Behaviour |
| --- | --- |
| ≤ 1180px | multi-column grids collapse; the team pill shows only its avatar |
| ≤ 1023px | **app shell**: top bar, floating neon dock with five tabs, bottom-sheet details |
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
with a soft neon glow (`.neon-logo`). Don't edit the generated files by hand.

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
2. Text on a neon fill uses `--on-accent`.
3. Nothing to bump — the server fingerprints CSS/JS by content, vendor files
   included (see `ARCHITECTURE.md` → Freshness).
4. New colours: `python3 scripts/check_contrast.py`.
5. New motion: put it in `motion.js` (or `magic.js` for a Magic UI effect), make
   it a no-op when `reduced` or the library is missing, and check it with
   "reduce motion" on.
6. Run `npm --prefix tests test` — 0 failures — then look at the phone and
   desktop screenshots in `tests/screenshots/`.
