# Changelog

## 2026-10-06 — Always fresh

- Returning visitors no longer see an old stylesheet. `index.html` is served
  `no-cache` with an ETag; CSS/JS links are rewritten to content hashes and
  cached as immutable; `/version` lets an open or home-screen app notice a new
  deploy and reload itself when brought back to the foreground.
- The manual `?v=N` cache-buster is gone.
- e2e: three new checks (build id, fingerprinted assets, revalidation) — 67.

## 2026-10-06 — Forest & lime

- **New palette, 60:30:10.** Forest `#1B4332` background (60%), mint `#96E6A1`
  and sea green `#84FAB0` content (30%), lime `#D4FC79` and sky `#8FD3F4`
  highlights (10%). Text on highlights is forest. Light theme follows the same
  split on a pale lime base. AA contrast re-checked.
- Logo, app icon, manifest and `theme-color` recoloured to match.
- **Repository guidance:** `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`,
  six specialist agents (model analyst, solver engineer, UI designer, QA tester,
  FPL data scout, release manager) and six skills (run locally, e2e test,
  calibrate xPts, deploy to Railway, brand and design, add a feature).
- `docs/`: architecture, model, solver, API, design, data sources, testing,
  deployment and this changelog.
- `tests/`: the Playwright suite is now in the repo (`npm --prefix tests test`,
  `BASE_URL` for live runs, non-zero exit on failure).
- `scripts/calibrate.py`: level and correlation vs FPL's `ep_next`, per-player
  spot checks, MAE against a reference CSV.

## 2026-10-05 — Mug's Game FC (`f42b18b`)

- Rebranded from Lucky Socks to **Mug's Game FC**, with light British humour in
  taglines, empty states and loading lines.
- Animated mug-and-football logo: steam, bob, hover clink and hop, a welcome
  dunk. Respects reduced motion.

## 2026-10-05 — Lucky Socks: glass and the app shell (`e7916fb`)

- Quirky interim name **Lucky Socks** and a logo that doesn't look like "AI".
- Glassmorphism design with blur kept to floating chrome.
- Phone app shell below 1024px: top bar, floating tab dock, More sheet,
  bottom-sheet details; installable as a home-screen app.
- The Team ID is asked on every launch, remembered, and skippable.
- Fixed phone overflow (fluid pitch, `minmax(0,1fr)` grids) and a stale-result
  race in Expected Points search.

## 2026-10-03 — Railway (`e70777d`)

- Railway deployment via `railway.json` (Railpack, explicit start command
  `uvicorn main:app --app-dir backend …`, `/healthz`), `.python-version` 3.12.

## 2026-10-03 — FPL AI: redesign and model upgrades (`2f27324`)

- Redesigned UI (solver page with plan list, pitch and gameweek stepper).
- Rules read from `bootstrap-static` (2026/27 10-point goalkeeper goal, chip
  windows, banked transfers, sell-on fee).
- Elo prior from FPL-Core-Insights; recent per-gameweek minutes from
  `event/{gw}/live`; injury-return ramp; doubtful-flag recovery; regression to
  usual role; loan blocks from `scout_risks`.
- Solver alternatives via no-good cuts; 0.5% optimality gap.
- Fixed: from-scratch solves spending free transfers, a free-transfer replay
  off-by-one, inflated Rate My Team grades.

## 2026-09-20 — First version (`c55ac5c`)

- Local FPL planner: FastAPI backend over the FPL API with disk cache and
  offline mode.
- xPts engine, multi-gameweek MIP solver, chip strategies, Rate My Team,
  Compare, Minileagues, Scout, rules-based Copilot.
- Vanilla-JS single-page app.
