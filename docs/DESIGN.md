# Design system

Everything visual lives in `frontend/styles.css` (tokens, components, layout)
and `frontend/motion.js` (animation). Colours are custom properties
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
| **Eyebrow** | `#view-eyebrow` above the title: `SYS//<TAB>/<SUB> · GW<n>`, set by `syncHead()`, with a blinking lime status light |
| **Glitch** | `h1.glitch` — a short chromatic jitter when the title changes |
| **Screen texture** | `body:after` CRT scanlines; `.backdrop .dots` dot grid; `.backdrop .beam` a slow scan beam |
| **Hologram pitch** | `.turf:before` scanlines and `.turf .sweep`, a light band running down the turf |
| **Boot sequence** | `#boot` on the landing card, typed in by GSAP (`steps()` ease) in `Motion.landingIn` |
| **Radar ring** | `.land-logo:before/:after` — a conic sweep and a dashed ring spinning the other way |

Rules: the texture stays faint (scanlines and grid never compete with text);
corner brackets are decoration only, never a wash; radii are tight (`--r-sm`
4px … `--r-xl` 14px). Every loop here is CSS and switches off under
`prefers-reduced-motion`.

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
  team, and How it works.

## Landing: the Team ID, asked once

The first visit on a device opens the landing screen: a neon pitch, the logo,
and one field for the FPL Team ID. Once entered, the ID is stored in
`localStorage` (`fplai_team`, `fplai_team_name`) and every later visit goes
straight to Home → My squad without asking. The team pill and the menu change or
forget it. "Just browsing" skips it and lands on Picks; team-only pages then
offer to add a team.

## Motion

Two libraries, vendored in `frontend/vendor/` (no CDN), each doing what it's best
at. All of it lives in `motion.js`, and every function is safe to call when a
library failed to load or the visitor prefers reduced motion.

| Effect | Library | Where |
| --- | --- | --- |
| Landing: pitch lines and the goal **draw themselves**, the logo flickers on like a neon sign, then the ball flies along a dotted path into the net, the net ripples and **GOAL!** flashes — on a loop | GSAP timeline + DrawSVGPlugin + MotionPathPlugin; anime.js flicker | landing |
| The sky: three neon wires across the background, each with a **pulse of light** travelling along it | anime.js `svg.createDrawable` | backdrop |
| The tab icon **draws itself** when its tab lights up | anime.js | dock, top bar |
| The dock capsule and the section pill **slide** to the active item with a little overshoot | GSAP `elastic` | dock, switcher |
| The neon line under the title redraws on every tab change | GSAP DrawSVG | page head |
| Views fade up; new cards, tiles and plans **rise in one after another** | GSAP stagger with `clearProps` (so hover transforms still work) | every view |
| Figures **count up** to their value | GSAP | tiles, solver, grade |
| Buttons give a **springy press** | anime.js `spring` | all buttons |
| A wrong Team ID gets a head-shake | GSAP | landing |
| The neon logo in the top bar flickers every few seconds | anime.js | top bar |
| Confetti for a +15 week, an A grade, a plan that gains, and five taps on the logo | canvas | global |

Cheap loops stay in CSS: the loader (a neon dash running along a path), the
breathing glow on the primary button and the selected plan, the captain's ring,
bars and sparklines growing, and the players walking onto the pitch.

`prefers-reduced-motion`: the CSS rule turns every animation off, and
`Motion.reduced` makes the JS effects leave things in their finished state.
Nothing counts up, nothing is ever hidden waiting for an animation.

Keep new motion on `transform`/`opacity`, never animate layout, and clear inline
transforms when an animation ends (GSAP `clearProps`, anime.js `onComplete`).

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

A club mug with a football dunked in it, drawn as a **neon sign**: cyan mug,
magenta ball, lime steam. Stroke-only inline SVG (`.neon-logo`) in the top bar
and on the landing card, plus a `#logo` symbol (same paths, literal colours) for
`<use>`. The steam rises on a CSS loop; GSAP draws the landing copy in.
`frontend/icon.svg` is the app icon: the same neon mug on a night tile.

## Voice

- Name: **Mug's Game FC**. Tagline: "Fantasy football is a mug's game. Might as
  well do the maths."
- Light British humour and Indian dark humour on the landing screen and under
  the loader ("putting the kettle on", "Sharma ji’s son finished this ages ago").
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
5. New motion: put it in `motion.js`, make it a no-op when `reduced` or the
   library is missing, and check it with "reduce motion" on.
6. Run `npm --prefix tests test` — 0 failures — then look at the phone and
   desktop screenshots in `tests/screenshots/`.
