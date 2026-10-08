# CLAUDE.md — Mug's Game FC

Instructions for Claude Code (and any other coding agent) working in this
repository. Read this first; the `docs/` folder has the detail.

## What this is

Mug's Game FC is a Fantasy Premier League planner. A FastAPI backend pulls the
official FPL API, projects expected points (xPts) for every player, and runs a
mixed-integer solver over transfers, captaincy and chips. A no-build vanilla-JS
single-page app renders it in a neon look, animated with GSAP and anime.js,
with five tabs and a mobile app shell.

Live: https://fpl-ai-production-966c.up.railway.app · Repo: yeda-anna/fpl-ai

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
npm --prefix tests test        # 93 checks, phone 390×844 + desktop 1440×900 + reduced motion
./.venv/bin/python tests/test_free_transfers.py   # free-transfer rules, no server needed
python3 scripts/check_contrast.py                 # WCAG AA for the neon palette
node --check frontend/app.js && node --check frontend/motion.js   # quick syntax check
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
| `backend/analysis.py` | Chips, Rate My Team, compare, weekly picks, mini-leagues |
| `backend/scout.py` | Price changes, set pieces, DEFCON, predicted line-ups, rules-based Copilot |
| `frontend/index.html` | Shell: top bar, neon sky, the five-tab dock, the landing screen (neon pitch scene), logo, scripts |
| `frontend/styles.css` | Design system: the neon tokens, glass, components, landing, dock, breakpoints |
| `frontend/app.js` | Tabs and sub-pages, routing, the remembered Team ID, every view, the menu, minute edits |
| `frontend/motion.js` | All animation: GSAP (timelines, DrawSVG, MotionPath, counters, indicators) and anime.js (sky pulses, icon drawing, springs) |
| `frontend/vendor/` | GSAP 3.15 (+ DrawSVGPlugin, MotionPathPlugin) and anime.js 4.5, vendored — see its README |
| `tests/e2e.js` | Playwright end-to-end suite |
| `scripts/calibrate.py` | Projection sanity check |
| `scripts/check_contrast.py` | WCAG AA check for the palette |
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
  `motion.js` using the two vendored libraries in `frontend/vendor/` (GSAP with
  DrawSVG and MotionPath, anime.js). Don't add a third; upgrade by replacing the
  files and noting the version in `frontend/vendor/README.md`.
- Cache-busting is automatic: the server rewrites `/static/*.css|js` links in
  `index.html` to `?v=<content hash>`, serves the page and every `/api/` answer
  `no-store`, and `app.js` reloads when `/version` reports a newer build. Never hand-write `?v=` numbers,
  and keep new CSS/JS referenced as `/static/<file>` (sub-folders are fine:
  `/static/vendor/…`) so they're fingerprinted too.
- **One neon look, no theme picker.** Colours come from the `:root` tokens only
  (`docs/DESIGN.md`), split **60:30:10** — near-black violet, dark glass, and
  three neons: lime (`--neon-l`, "do this"), cyan (`--neon-c`, lines and
  information), magenta (`--neon-m`, the ball and celebration). Text on a neon
  fill uses `--on-accent`, never white. Every text token must pass AA — run
  `python3 scripts/check_contrast.py`.
- **The HUD layer** (sci-fi console: corner brackets, mono readouts, the
  `SYS//…` eyebrow, scanlines, the hologram pitch, the landing boot lines) sits
  on top of the neon — see "The HUD layer" in `docs/DESIGN.md`. New panels get
  the corners by joining the `.card,.tile,.plan,.path,.sheet` selector, not with
  new hex values.
- Neon lives on strokes, edges and things you can press — never as a wash behind
  running text. Cards stay dark and nearly solid so the sky's wires never run
  behind words.
- **Five tabs** (Home, Plan, Players, Leagues, Ask) with sub-pages in the section
  switcher — add a new page as a sub-page in `TABS` (`app.js`), not as a sixth
  tab, and give it an address (`#tab/sub`). Keep old addresses mapped in `LEGACY`.
- **The Team ID is asked once per device** on the landing screen and kept in
  `localStorage` (`fplai_team`); returning visitors go straight to their team.
  Team views `await teamReady()` so the first read after a page load is fresh.
- Live `backdrop-filter` only on floating chrome: `.nav-bar, .dock, .sheet,
  .land-card, .adv-body, .toast`. In-page cards never blur.
- Single-column grids use `minmax(0,1fr)`, never bare `1fr` (it blows out on phones).
- Phone layout must not widen the viewport: the e2e suite scans every element
  against 390px. Long strings need `overflow-wrap:anywhere`.
- Keep request races in mind: a view that can fire overlapping requests must
  ignore stale responses (see the `XP.seq` pattern in `viewXpts`).
- Respect `prefers-reduced-motion`: the CSS rule turns every animation off and
  every `Motion` function must leave things in their finished state when
  `Motion.reduced` is true or its library didn't load. Clear inline transforms
  when an animation ends (GSAP `clearProps`) so hover effects keep working.

**Brand and content**
- Name: **Mug's Game FC**. Tagline: "Fantasy football is a mug's game. Might as
  well do the maths." Logo: a club mug with a football dunked in it, drawn as a
  neon sign (cyan mug, magenta ball, lime steam).
- Tone: light British humour and Indian dark humour on the landing screen and
  under the loader ("putting the kettle on", "Sharma ji’s son finished this ages
  ago"). Lines live in `QUIPS` in `app.js`, aimed at the manager's own luck —
  never at a religion, caste, region, community, body or real person. **Never**
  in errors or anything a manager acts on.
- **One roast, by request:** Home's title is the team's own name from FPL, and
  Home → My squad opens with a dark football roast of the last gameweek
  (`SCORE_ROASTS` in `app.js`), picked by score against the average and seeded by
  team and gameweek. It may quote the score and the gap to the average, but it
  lives only in the page head, never gives advice, and the numbers in the tiles
  stay plain. There are no roasts under suggestions; don't add more without asking.
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
