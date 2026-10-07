# Testing

## End-to-end (Playwright)

`tests/e2e.js` drives a headless Chromium through the whole app at two sizes:
phone 390×844 and desktop 1440×900. 88 checks.

```bash
# terminal 1 — the server (offline mode is fine once .cache/ is primed)
FPL_CACHE_ONLY=1 ./run.sh

# terminal 2
npm --prefix tests ci        # first time: installs Playwright + Chromium
npm --prefix tests test      # exits non-zero on any failure
BASE_URL=https://fpl-ai-production-966c.up.railway.app/ npm --prefix tests test   # against live
```

Screenshots land in `tests/screenshots/` (git-ignored); pass a directory as
the first argument to `node tests/e2e.js` to put them elsewhere.

What it covers:

- Welcome screen asks for a Team ID on every launch, remembers the last one
  ("welcome back", prefilled), shows a clear error for an unknown team, and
  **Skip** leaves you browsing; team-only tools offer to add a team.
- Phone shell: tab dock shown and desktop links hidden (and the reverse on
  desktop); the More sheet opens, navigates and highlights the More tab.
- Every view renders without an error box: Dashboard, Expected Points, Solver,
  Chip Strategies, Copilot, Rate My Team, Compare, Minileagues, Scout (all
  tabs), How It Works.
- **Overflow scan**: no element on the phone wider than 390px, on every view.
- Expected Points: table renders; a minutes edit lowers xPts and resets.
- Solver: returns plans, controls sit above the pitch, the pitch steps through
  gameweeks, switching plans works.
- Copilot answers; minileague analysis completes; the player bottom sheet opens.
- Theme picker: opens from More and from the top bar, lists four themes plus
  Match system, each theme applies and sets the browser-bar colour, closes on an
  outside tap and on Escape, survives a relaunch; old `light`/`dark` settings
  map to Chalk/Forest. Screenshots of the dashboard in every theme.
- Freshness: the page carries a build id equal to `/version`, CSS/JS URLs are
  content-hashed, `/` and `/api/*` are `no-store`, the first read of your team
  after a page load sends `fresh=1` and later reads don't, and **More → Refresh
  app** reloads to a clean launch.
- House humour: the welcome screen, every loading state and the dashboard mood
  line carry a quip.
- No console errors and no failed requests (besides the deliberate unknown
  team).

## Free-transfer rules (no server needed)

```bash
./.venv/bin/python tests/test_free_transfers.py
```

Replays synthetic histories through the same code the app uses: a transfer a
week, skipped weeks banking one, hits, the five-transfer cap, and — the case
that was wrong — a Wildcard or Free Hit week, which keeps what was banked and
adds nothing.

## Solver hits (no server, no FPL API)

```bash
./.venv/bin/python tests/test_solver_hits.py
```

Builds a synthetic league and checks that the solver takes paid transfers in any
gameweek, not just the last: with every owned player at 0 xPts it spends the
whole hit allowance in GW1; hit budgets of 0, 1 and 2 give different plans; a
hit week leaves one free transfer; and every plan, with or without a Wildcard,
matches FPL's `min(5, max(0, ft − made) + 1)` rule. About 15 s (CBC).

## Quick checks

```bash
node --check frontend/app.js
./.venv/bin/python -c "import sys; sys.path.insert(0,'backend'); import main"
curl -s localhost:8787/healthz
curl -s -o /dev/null -w '%{http_code}\n' localhost:8787/api/entry/999999999   # expect 404
```

## Model checks

```bash
./.venv/bin/python scripts/calibrate.py --horizon 5 --players "Haaland:MCI,Saka:ARS"
./.venv/bin/python scripts/calibrate.py --reference my_numbers.csv
```

See `MODEL.md` for what "healthy" looks like.

## Rules

- Any UI change: e2e must stay at **0 failures**, and look at the phone
  screenshots — the suite can't judge taste.
- Any model change: run the calibration before and after and put both numbers in
  the commit message.
- Any solver change: solve team 1 at horizons 1, 5 and 8 and from scratch
  (`paths: 3`) and check every plan is `feasible`.
- Headless only. Don't drive the user's own browser.
