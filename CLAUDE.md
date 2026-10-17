# CLAUDE.md — Papa Ranjeet

Instructions for Claude Code (and any other coding agent) working in this
repository. Read this first; the `docs/` folder has the detail.

## What this is

Papa Ranjeet is a Fantasy Premier League planner. A FastAPI backend pulls the
official FPL API, projects expected points (xPts) for every player, and runs a
mixed-integer solver over transfers, captaincy and chips. A no-build vanilla-JS
single-page app renders it in a race-day look (dark teal, italic Chakra Petch,
slanted lime buttons) — it opens with a short
Theatre.js film of drones flying into the logo, and moves with GSAP, anime.js, Motion, AutoAnimate and effects
rebuilt from Magic UI — with five tabs and a mobile app shell.

Live: https://paparanjeet.up.railway.app · Repo: yeda-anna/fpl-ai

## Run it

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./run.sh                       # http://127.0.0.1:8787
FPL_CACHE_ONLY=1 ./run.sh      # offline: serve only what's in .cache/
```

The first online run fills `.cache/` with FPL responses. After that, offline
mode works for anything you've already loaded (a team, a league).

## Test it

```bash
npm --prefix tests ci          # once: installs Playwright
npm --prefix tests test        # 134 checks, phone 390×844 + desktop 1440×900 + reduced motion + the demo
./.venv/bin/python tests/test_free_transfers.py   # free-transfer rules, no server needed
./.venv/bin/python tests/test_pending_transfers.py # transfers since the deadline, no server needed
./.venv/bin/python tests/test_demo.py             # the demo team is a legal squad, no server needed
./.venv/bin/python tests/test_model_rules.py      # form, chance to score, fitness, opponent form, no server needed
./.venv/bin/python tests/test_leagues.py          # a manager's mini-leagues, no server needed
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'   # every unit test at once (rules, solver, analysis, scout, API routes on a made-up league), no server or network
python3 scripts/check_contrast.py                 # WCAG AA for the palette
for f in app motion magic intro; do node --check frontend/$f.js; done   # quick syntax check
./.venv/bin/python scripts/calibrate.py   # model sanity vs FPL's own ep_next
```

Start the server first (offline mode is fine). Every UI change must keep the
suite at **0 failures** — see `docs/TESTING.md`.

## Map

| Path | What it does |
| --- | --- |
| `backend/main.py` | FastAPI routes, engine cache (rebuilt every 15 min), minute overrides, team loading |
| `backend/fpl_api.py` | FPL endpoints + disk cache with per-endpoint TTLs; `FPL_CACHE_ONLY` |
| `backend/rules.py` | Scoring, squad limits, formations, chip windows **read from bootstrap-static** |
| `backend/priors.py` | Elo prior (FPL-Core-Insights) and recent per-gameweek minutes |
| `backend/xpts.py` | The expected-points engine |
| `backend/solver.py` | Multi-gameweek MIP (PuLP/CBC), alternative paths via no-good cuts |
| `backend/analysis.py` | Chips, Rate My Team, compare, weekly picks, mini-league analysis |
| `backend/leagues.py` | A manager's mini-leagues from their FPL profile: every league, their place, the leader and the gap |
| `backend/scout.py` | Price changes, set pieces, DEFCON, predicted line-ups, rules-based Copilot |
| `backend/demo.py` | The demo team (ID 0, "Gut Feeling FC") for visitors who don't play FPL: a legal squad picked on vibes and an invented season |
| `frontend/index.html` | Shell: the opening film's stage, top bar, the page head with the season race bar, the five-tab dock, the landing screen (pitch scene), logo, scripts |
| `frontend/styles.css` | Design system: the tokens, the Chakra Petch faces, "the slant", components, the Magic UI effects, the film, landing, dock, breakpoints |
| `frontend/app.js` | Tabs and sub-pages, routing, the remembered Team ID, every view, the menu, minute edits |
| `frontend/motion.js` | `FX`, the animation layer: GSAP (landing timeline, DrawSVG, MotionPath, indicators, the race bar), anime.js (icon drawing, the landing logo), Motion (blur-fade entrances, number tickers, springs, scroll progress, animated lists), AutoAnimate (lists that re-order) |
| `frontend/magic.js` | `Magic`: Magic UI components rebuilt in plain JS — HyperText, TypingAnimation, Ripple, OrbitingCircles, BorderBeam, ShimmerButton (hidden), AnimatedBeam, RetroGrid |
| `frontend/intro.js` | `Intro`: the opening film, a Theatre.js sequence (keyframes in `KEYS`) played on launch: a drone swarm drawn on a canvas |
| `frontend/portrait.js` | `PORTRAIT`: the film's drones, traced from the lights in the portrait — generated, don't edit |
| `frontend/portrait.webp`, `logo.webp`, `icon-*.png` | The drone-portrait image the owner supplied, its square face crop (the logo) and the home-screen icons — generated |
| `frontend/vendor/` | GSAP 3.15 (+ DrawSVGPlugin, MotionPathPlugin), anime.js 4.5, Motion 13.4, Theatre.js core 0.7, AutoAnimate 0.10, Chakra Petch (fonts/) — vendored, see its README |
| `tests/e2e.js` | Playwright end-to-end suite |
| `tests/fakes.py` | A made-up 20-club league in FPL's own shape, for the unit tests (no network) |
| `scripts/calibrate.py` | Projection sanity check |
| `scripts/check_contrast.py` | WCAG AA check for the palette |
| `scripts/digitize.py` | From the supplied image: `portrait.webp`, `logo.webp`, the PNG icons and `portrait.js` |
| `docs/` | Architecture, model, solver, API, design, data, testing, deployment |
| `.claude/agents/` | Specialist sub-agents for this repo |
| `.claude/skills/` | Step-by-step procedures (run, test, calibrate, deploy, design, add a feature) |

## Rules of the road

**Python**
- Keep backend code **Python 3.9-compatible** (the local Mac venv is 3.9; Railway
  runs 3.12). Use `from __future__ import annotations`, `typing.Optional/Dict/List`.
  No `match`, no `X | Y` unions at runtime, no 3.10+ stdlib-only APIs.
- Never hardcode FPL game rules. Points, squad size, club limit, budget, banked
  transfers, sell-on fee, formations and chip windows come from `rules.Rules`
  (bootstrap-static). The `GOAL_PTS`/`CS_PTS`/… constants at the top of `xpts.py`
  are legacy and unused.
- Network calls go through `fpl_api.get()` so caching and offline mode keep working.
- Unknown teams must return **404** with a readable `detail`, not a 500.
- The solver must check `feasible` before trusting a plan. A plan built from an
  empty squad must not spend free transfers (see `solver.py`).

**Frontend**
- No build step, no framework, no CDN. Plain JS in `app.js`; animation in
  `motion.js` (`FX`), `magic.js` (`Magic`) and `intro.js` (`Intro`), using the
  vendored libraries in `frontend/vendor/`, each with its own job: GSAP (+
  DrawSVG, MotionPath) for SVG drawing and timelines, anime.js for icons, Motion for springs, in-view and scroll, AutoAnimate for lists that
  change, Theatre.js core for the opening film. Magic UI is React, so its
  effects are rebuilt in `magic.js` + CSS — never pull in React for it. Don't
  add another library without asking; upgrade by replacing the files and noting
  the version in `frontend/vendor/README.md`. The global `Motion` is the
  motion.dev library — our layer is `FX`.
- Cache-busting is automatic: the server rewrites `/static/*.css|js` links in
  `index.html` to `?v=<content hash>`, serves the page and every `/api/` answer
  `no-store`, and `app.js` reloads when `/version` reports a newer build. Never hand-write `?v=` numbers,
  and keep new CSS/JS referenced as `/static/<file>` (sub-folders are fine:
  `/static/vendor/…`) so they're fingerprinted too.
- **One look, race day, no theme picker.** Colours come from the `:root` tokens
  only (`docs/DESIGN.md`): a dark teal night (`--bg`), three flat surfaces
  (`--surface`, `-2`, `-3`), and three colours — lime (`--lime`, "do this": the
  main button, the open tab, the captain), green (`--green`, progress and
  information), purple (`--purple`, the selected sub-page, projection bars).
  Type is italic **Chakra Petch** (vendored in `frontend/vendor/fonts/`). Text on
  a lime/green fill uses `--on-accent`; on purple `--on-purple`. Every text
  token must pass AA — run `python3 scripts/check_contrast.py`.
- **Pressable things slant** (`--skew`): buttons draw a skewed `::before` behind an
  upright label (set `--fill`), so join "the slant" block in `styles.css`; chips
  and strips use a parallelogram `clip-path`. Surfaces are flat and solid — no
  glass, no glow behind words, no borders on cards. There is no meteor shower,
  no sky animation, no scanlines and no corner brackets; don't bring them back
  without asking.
- **Five tabs** (Home, Plan, Players, Leagues, Ask) with sub-pages in the section
  switcher — add a new page as a sub-page in `TABS` (`app.js`), not as a sixth
  tab, and give it an address (`#tab/sub`). Keep old addresses mapped in `LEGACY`.
- **The Team ID is asked once per device** on the landing screen and kept in
  `localStorage` (`fplai_team`); returning visitors go straight to their team.
  Team views `await teamReady()` so the first read after a page load is fresh.
- **The demo team** is for visitors who don't play FPL: "See a demo team" on the
  landing loads team **0** (`backend/demo.py`), never saved to `fplai_team` (only
  `sessionStorage.fplai_demo`, so the app's own reloads keep it). Home → My squad
  opens with a tour card that explains FPL in a sentence and links each part of
  the app. Every team route must keep working for team 0 (`team_id is not None`,
  never a truthiness test).
- Live `backdrop-filter` only on floating chrome: `.nav-bar, .dock, .toast`.
  Cards and sheets never blur.
- Single-column grids use `minmax(0,1fr)`, never bare `1fr` (it blows out on phones).
- Phone layout must not widen the viewport: the e2e suite scans every element
  against 390px. Long strings need `overflow-wrap:anywhere`.
- Keep request races in mind: a view that can fire overlapping requests must
  ignore stale responses (see the `XP.seq` pattern in `viewXpts`).
- Respect `prefers-reduced-motion`: the CSS rule turns every animation off and
  every `FX`/`Magic` function must leave things in their finished state when
  `FX.reduced` is true or its library didn't load. Clear inline transforms
  when an animation ends (GSAP `clearProps`, Motion `.then`) so hover effects
  keep working. Don't animate an element with two libraries at once (the
  Copilot log is AutoAnimate's, so it isn't in `FX`'s entrance list).
- **The opening film** plays on every launch (not on in-app navigation, not on
  the app's own reloads), is skippable at any moment (tap, Esc/Enter/Space,
  "Skip intro"), can be turned off in the menu (`fplai_intro`), and never runs
  under reduced motion. The app loads underneath and must never wait on it:
  `Intro` is optional, and entrances are held only until the film opens onto
  the app (`FX.hold(Intro.reveal)`). About 11½ seconds: the tagline is typed by
  4.85 s and holds for six seconds before the push-in.

**Brand and content**
- Name: **Papa Ranjeet**. Tagline: "Football’s a funny old game. Might as well do the
  maths." Logo: the drone-portrait image the owner supplied, used as it is —
  not regenerated or restyled. `scripts/digitize.py <image>` writes
  `portrait.webp` (the film), `logo.webp` (a square face crop, the `#logo`
  symbol), the PNG icons and `portrait.js` (the film's drones, traced from the
  image's own lights). Never edit those by hand; rerun the script. Don't put any
  other real person's likeness in the app without asking.
- Tone: light British humour and Indian dark humour on the landing screen and
  under the loader ("putting the kettle on", "Sharma ji’s son finished this ages
  ago"), and the opening film's tagline — a one-liner in the manner of a 70s
  Hindi-film villain ("Free transfer? Yahan kuch bhi free nahi milta.") —
  written for the app, never presented as a real actor's or film's dialogue. Lines live in `QUIPS` in `app.js`, aimed at the manager's own luck —
  never at a religion, caste, region, community, body or real person. **Never**
  in errors or anything a manager acts on.
- **One roast, by request:** Home's title is the team's own name from FPL, and
  Home → My squad opens with a dark football roast of the last gameweek
  (`SCORE_ROASTS` in `app.js`), picked by score against the average and seeded by
  team and gameweek. It may quote the score and the gap to the average, but it
  lives only in the page head, never gives advice, and the numbers in the tiles
  stay plain. There are no roasts under suggestions; don't add more without asking.
  The demo team has its own list (`SCORE_ROASTS.demo`), aimed at the made-up
  manager's vibes picking, asked for by the owner.
- Shirts are plain silhouettes in club colours. No crests, sponsors, real kit
  designs or other sites' logos, mascots or UI copy.
- Don't commit raw FPL API responses (`.cache/` is git-ignored); fetch them live.

**Git and deploy**
- Railway deploys `main` automatically (`railway.json`). Health check: `/healthz`.
- Commit messages: imperative subject, a body that says *why*.
- Never force-push `main`.

## Where to look next

- New to the model? `docs/MODEL.md`, then `docs/SOLVER.md`.
- Touching the UI? `docs/DESIGN.md` and the `brand-and-design` skill.
- Adding an endpoint or a view? The `add-feature` skill.
- Shipping? The `deploy-railway` skill.
