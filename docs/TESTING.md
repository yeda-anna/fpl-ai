# Testing

## End-to-end (Playwright)

`tests/e2e.js` drives a headless Chromium through the whole app at two sizes:
phone 390×844 and desktop 1440×900. 108 checks.

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
- Theme picker: opens from More and from the top bar, lists six themes plus
  Match system, each theme applies and sets the browser-bar colour, closes on an
  outside tap and on Escape, survives a relaunch; a first visit opens in Open
  Mic; old `light`/`dark` settings map to Chalk/Forest. Screenshots of the
  dashboard in every theme.
- Freshness: the page carries a build id equal to `/version`, CSS/JS URLs are
  content-hashed, `/` and `/api/*` are `no-store`, the first read of your team
  after a page load sends `fresh=1` and later reads don't, and **More → Refresh
  app** reloads to a clean launch.
- House humour: the welcome screen and every loading state carry a quip; the
  dashboard shows the week's verdict banner and "Roast me again" changes it; a
  roast sits under the captain picks, the Expected Points table, each solver
  plan, chip plan, Copilot answer, Rate My Team grade and fix, comparison,
  league and Scout tab — always outside the advice and labelled for screen
  readers.
- Roast mode: the switch in the theme picker is on by default, turning it off
  removes every roast, quip and verdict and is remembered, and turning it on
  brings them back.
- Motion: counters land on the true value; Rate My Team draws a grade ring.
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

## Look and motion (by eye)

The suite can't judge whether it looks right. After a UI change, run it, then
open the screenshots in `tests/screenshots/` — the dashboard in every theme on
phone and desktop. Also check by hand with the OS "reduce motion" setting on:
everything should simply be there, no entrances, glows or sweeps.

```bash
python3 scripts/check_contrast.py      # WCAG AA for every theme; exits 1 on a miss
```

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
