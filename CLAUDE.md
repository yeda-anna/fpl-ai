# CLAUDE.md — Mug's Game FC

Instructions for Claude Code (and any other coding agent) working in this
repository. Read this first; the `docs/` folder has the detail.

## What this is

Mug's Game FC is a Fantasy Premier League planner. A FastAPI backend pulls the
official FPL API, projects expected points (xPts) for every player, and runs a
mixed-integer solver over transfers, captaincy and chips. A no-build vanilla-JS
single-page app renders it, with a glass design and a mobile app shell.

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
npm --prefix tests test        # 64 checks, phone 390×844 + desktop 1440×900
node --check frontend/app.js   # quick syntax check
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
| `frontend/index.html` | Shell: top bar, tab dock, More sheet, welcome screen, icon sprite, logo |
| `frontend/styles.css` | Design system: tokens, glass, components, breakpoints, logo animation |
| `frontend/app.js` | All ten views, navigation, team prompt, minute edits |
| `tests/e2e.js` | Playwright end-to-end suite |
| `scripts/calibrate.py` | Projection sanity check |
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
- No build step, no framework, no CDN dependencies. Plain JS in `app.js`.
- After changing `styles.css` or `app.js`, **bump the `?v=N` cache-buster** on both
  `<link>`/`<script>` tags in `index.html`.
- Colours come from tokens only (`docs/DESIGN.md`). The palette follows
  **60:30:10** — forest `#1B4332` background, mint `#96E6A1`/`#84FAB0` content,
  lime `#D4FC79`/sky `#8FD3F4` highlights. Text on a highlight is always forest
  (`--on-accent`), never white.
- Live `backdrop-filter` only on floating chrome: `.nav-bar, .tabbar, .more-panel,
  .sheet, .ob-card, .adv-body`. In-page cards stay flat translucent glass.
- Single-column grids use `minmax(0,1fr)`, never bare `1fr` (it blows out on phones).
- Phone layout must not widen the viewport: the e2e suite scans every element
  against 390px. Long strings need `overflow-wrap:anywhere`.
- Keep request races in mind: a view that can fire overlapping requests must
  ignore stale responses (see the `XP.seq` pattern in `viewXpts`).
- Respect `prefers-reduced-motion` (a global rule already stops animations).

**Brand and content**
- Name: **Mug's Game FC**. Tagline: "Fantasy football is a mug's game. Might as
  well do the maths." Logo: a club mug with a football dunked in it, animated.
- Tone: light British humour in taglines, empty states and loading lines
  ("just having a nose", "putting the kettle on"). **Never** in errors, numbers
  or anything a manager acts on.
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
