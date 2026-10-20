# Testing

## CI: the gate on every pull request

`main` deploys to production as soon as it changes, so every pull request into
`main` runs `.github/workflows/ci.yml` (GitHub Actions), and so does every push
to `main`. Four jobs, each a required check on `main`:

| Check | What it runs | Red means |
| --- | --- | --- |
| `unit (py3.9)` | `pip install -r requirements.txt`, `python -m compileall -q backend tests scripts`, then every unit test with `FPL_CACHE_ONLY=1` | A test failed, or the code uses something Python 3.9 doesn't have (`match`, a runtime `X \| Y`, a 3.10+ API) |
| `unit (py3.12)` | the same on 3.12, what Railway runs | A test failed on production's Python |
| `frontend` | `node --check` on every `frontend/*.js` (not `vendor/`), then `scripts/check_contrast.py` | A syntax error that would ship straight to phones, or a colour below WCAG AA |
| `build` | `scripts/check_start_command.py`, then builds the image with the pinned **Railpack** CLI (Railway's builder), runs it with `FPL_CACHE_ONLY=1` and runs `scripts/smoke.sh` against it | `Procfile` and `railway.json` start the app differently, a dependency or Python version won't install, or the built app doesn't boot and serve its page |

Everything is offline: no job calls the FPL API. The Playwright suite isn't in
CI yet — it needs live FPL data; phase 2 of `plans/ci-build-deploy-gate.md`
runs it against a Railway preview of each PR. Until then, run it locally as
below and put the counts in the PR.

A red `build` job prints the Railpack plan, the build log and the app's own
logs (`App logs` step). To repeat it locally you need Docker:

```bash
docker run --rm --privileged -d --name buildkit moby/buildkit:v0.34.0
BUILDKIT_HOST=docker-container://buildkit railpack build . --name fpl-ai:ci
docker run -d --name app -p 8000:8000 -e PORT=8000 -e FPL_CACHE_ONLY=1 fpl-ai:ci
scripts/smoke.sh http://127.0.0.1:8000
```

`scripts/smoke.sh <url> [--live]` works on any running copy: `/healthz` is 200
with `"ok": true` (retried for up to 60 s while it boots), `/` carries a build
id that `/version` agrees with, and the first content-hashed `/static/…?v=`
asset in the page loads. `--live` adds `/api/entry/999999999` → 404, which
needs real FPL data (offline with an empty cache it can't build the model).
Railpack and BuildKit are pinned by version (Railpack also by checksum) and
every action by commit, in `ci.yml`; bump them there.

## End-to-end (Playwright)

`tests/e2e.js` drives a headless Chromium through the whole app at two sizes,
phone 390×844 and desktop 1440×900, plus a reduced-motion pass and a run through the demo team, the leagues list, the Matches page and the usage counts. 164 checks.

```bash
# terminal 1 — the server (offline mode is fine once .cache/ is primed)
FPL_CACHE_ONLY=1 ./run.sh

# terminal 2
npm --prefix tests ci        # first time: installs Playwright + Chromium
npm --prefix tests test      # exits non-zero on any failure
BASE_URL=https://fpl-ai-production-966c.up.railway.app/ TEAM_ID=1234567 npm --prefix tests test   # against live
```

Screenshots land in `tests/screenshots/` (git-ignored); pass a directory as
the first argument to `node tests/e2e.js` to put them elsewhere.

What it covers:

- **The page loads:** it is named Papa Ranjeet; GSAP, both plugins, anime.js,
  Motion and AutoAnimate load from `/static/vendor`, with `FX` and `Magic`;
  there is no opening film (no film markup, no Theatre.js) and the app is there
  at once; the logo is the supplied portrait (`logo.webp`).
- **Landing:** a first visit opens it; it has the pitch scene and a quip;
  an empty ID and an unknown team each get a clear message; a real ID goes
  straight to Home → My squad, is saved in `localStorage`, names the team pill,
  and the first read asks FPL afresh (`fresh=1`).
- Home is titled with the team's name from FPL; My squad opens with a roast of
  the week's score (and the same line on the way back); other Home pages keep
  their own line; other tabs keep their own title.
- **Six tabs** in the dock and no "More". Every tab and every sub-page renders
  without an error box, fits a 390px phone (**overflow scan**) and has its own
  address (`#tab/sub`).
- The tools still work: re-sorting the projections moves the rows in place
  (AutoAnimate, the table is kept), a minutes edit lowers xPts and resets, the
  solver returns plans and steps through gameweeks, the Copilot answers and
  keeps a log (newest entry first), a mini-league is analysed, the player sheet
  opens.
- The menu opens with How it works; **Refresh app** reloads and the saved team
  skips the landing screen; old addresses (`#solver`) land in the right place;
  **Forget team** clears the device and asks again; **Just browsing** lands on
  Picks and team-only pages offer to add a team.
- Desktop: tab links shown and dock hidden; the page carries a build id equal to
  `/version`; every CSS/JS file, vendor libraries included, is content-hashed;
  `/` and `/api/*` are `no-store`; scripts arrive gzipped; each tab renders; a
  returning visitor skips the landing screen.
- Counters (spring tickers) land on the true value; the season race bar sits
  under the title with the gameweeks left; the night is calm (no meteors, no
  scanlines); with reduced motion everything is visible at once and nothing
  counts up.
- No console errors and no failed requests (besides the deliberate unknown
  team).
- **Usage counts:** the first open of the day sends one visit (new, with a real
  team) holding only `kind`, `returning` and `mode`; a page view sends only the
  page name; the browser keeps just two dates; a second open the same day sends
  no visit; `#stats` asks for the key and turns a wrong one away. With
  `STATS_KEY=… npm --prefix tests test` (the key the server was started with) it
  also checks the tiles, the 30-day chart, pages and features, the 390px fit and
  "Don't count this browser".

## Unit tests, all at once (no server, no network)

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'    # every file below, ~10 s
```

Most of the unit tests run the real backend code on **a made-up 20-club league**
(`tests/fakes.py`): FPL-shaped `bootstrap-static` and `fixtures` payloads, built
from each player's id, so they come out the same on every run. Nothing touches the
network or the `.cache/` folder.

| File | What it proves |
| --- | --- |
| `test_rules.py` | Scoring, squad limits, formations and both chip windows are read from bootstrap-static; an empty payload falls back to the documented rules |
| `test_solver.py` | Every plan is a squad FPL would accept in every week (15, 2-5-5-3, three a club, money in the bank) with a legal XI, captain ≠ vice, hits at 4 points, FPL's free-transfer roll-over, a different route when the best one is ruled out, Wildcards free and building from scratch spending nothing |
| `test_analysis.py` | Best XI is legal and unbeaten; the Free Hit XI keeps the club limit and skips the injured; Rate My Team scores stay 0–100 and match the grade; compare, weekly picks, chips (used chips aren't offered, two chips never share a week) and mini-league odds (sum to 100, repeatable, a failed rival is skipped) |
| `test_scout.py` | Copilot intent matching, price risers/fallers, set-piece takers, DEFCON thresholds, predicted XIs, and Copilot answers drawn from your own squad |
| `test_season.py` | The season rank chart's data: a smaller rank is a climb, weeks in order, unranked weeks dropped, best/worst/latest, and `/api/entry` carrying `season` in step with `history` |
| `test_api.py` | Every route through FastAPI's test client on the demo team: shapes the frontend reads, `no-store` headers, a minutes override and a hand-entered transfer flowing through, and unknown teams as readable 404s |
| `test_telemetry.py` | Structured logs: every line is single-line JSON with Railway's level names, uvicorn shares the handler with its access log off, a request is logged by route template and never with the Team ID in its path (404 info, unhandled exception a 500 at error, `/healthz` debug), FPL fetches log their endpoint kind (an outage is a warning when a stale copy is served, an error when not), and a solve logs its time, status and `feasible` |

| `test_ci_scripts.py` | The CI gate's own scripts: `check_start_command.py` reads both files, ignores spacing and reports a mismatch or a missing command; `smoke.sh` passes a healthy app (and waits for one that's still booting) and fails, with a readable reason, on a bad `/healthz`, a page error, a missing build id, a `/version` that disagrees, a missing asset, and — with `--live` — an unknown team that isn't a 404. Runs a tiny local server; skips if bash or curl is missing |

`test_api.py` holds one `expectedFailure`: `/api/meta` returns a 500 when the
Elo prior can't be fetched. Remove the decorator once that's fixed.

## Usage counts (no server needed)

```bash
./.venv/bin/python tests/test_usage.py
```

Visits split new/returning and by team mode, only the app's own page names are
counted, features by route template and only when they answer, the file holds counts
and nothing else, old days drop off, a broken file starts again. `tests/test_api.py`
adds the routes: the beacon (204, 422 for an unknown kind), feature counting through
the middleware, and the key on `/api/stats` (404 when off, 403 wrong, 200 right).

## Match predictions (no server needed)

```bash
./.venv/bin/python tests/test_matches.py
```

The scoreline table sums to 1 and Dixon-Coles lifts 0-0 and 1-1 (more draws than
independent Poisson); outcome chances add to 1, follow strength and mirror when
home and away swap; **the predicted score always agrees with the predicted result**;
a clear favourite is picked to win by a goal or more and two even, low-scoring
sides to draw; scorelines are ordered; clean sheets, goals and both-to-score move
the right way; a gameweek of fixtures comes back in kick-off order with teams,
odds and the real score for finished matches; the round's summary; an empty
gameweek. `tests/test_api.py` checks the route on the made-up league (next
gameweek by default, played weeks carry real scores, an out-of-range gameweek is a 422).

The e2e suite's Matches run checks, on the offline data, that the page shows every
match, each predicted score agrees with its pick, odds add to 100%, an out-of-range
gameweek is refused, the stepper moves and returns, played matches show the real
score, the page fits a phone, all six dock tabs fit 390px (each ≥ 44px), and six
top-bar links fit 1024px without crowding.

## A manager's mini-leagues (no server needed)

```bash
./.venv/bin/python tests/test_leagues.py
```

On payloads shaped like FPL's own (`/entry/{id}/` and the 50-a-page standings):
which standings page a rank sits on; private vs FPL-own vs head-to-head leagues;
the leader, the gap to the leader, the points behind the manager above and ahead
of the one below — and that a neighbour on a page that wasn't read is **not**
guessed; a manager on page 3 is found by reading page 3 and not page 2; a league
that fails to load keeps what the profile says; only the first 15 private leagues
are read in full; no leagues at all.

The e2e suite's leagues run calls the real endpoints offline (a real team, the
demo team, an unknown team) and then stubs the leagues answer to check the list,
the summary tiles, the phone fit, and that **Analyse** opens that league with the
manager always included (`entry=`).

## The planner's rules (no server needed)

```bash
./.venv/bin/python tests/test_model_rules.py
```

On a made-up four-club league: a club that has stopped creating chances becomes
a weaker attack (within the bounds) and no live data means no form adjustment;
a player in form projects above his season rate and one out of form below it;
real goals nudge the rate only a little; chance to score is `1 − e^(−xG)`;
benched recent weeks cut expected minutes; a 50%-doubtful player isn't bought at
75% (but is at "anyone") and is listed as passed over; a doubtful player already
owned stays in the XI but doesn't wear the armband until his odds recover.

## The demo team (no server needed)

```bash
./.venv/bin/python tests/test_demo.py
```

The demo squad (`backend/demo.py`) is legal under the rules it's given (squad
size, positions, club limit, budget, even when tight), keeps an injured star,
only uses players the model can project, is the same every time, and its
invented season ends in a shocker so Home's roast has something to say.

The e2e suite's demo run checks the landing's demo button, the roasted Home with
its tour, that nothing is saved to `fplai_team`, that My squad charts the
season (a point a gameweek, the current rank at the end, a row a week in the
table, arrow keys stepping through the weeks), that Grade works for team 0,
that an app reload stays in the demo and that leaving it returns to the landing.

## Transfers since the last deadline (no server needed)

```bash
./.venv/bin/python tests/test_pending_transfers.py
```

A transfer made for the coming gameweek replaces the player in his slot and moves
the bank; transfers already in the picks are ignored; chained transfers apply in
order.

## Free-transfer rules (no server needed)

```bash
./.venv/bin/python tests/test_free_transfers.py
```

Replays synthetic histories through the same code the app uses: a transfer a
week, skipped weeks banking one, hits, the five-transfer cap, and — the case
that was wrong — a Wildcard or Free Hit week, which keeps what was banked and
adds nothing.

## Before/after screenshots (UI pull requests)

`scripts/serve_fake.py` serves any checkout on the made-up league, network off, so
`main` and a branch can run side by side; `scripts/screenshots.js` shoots one view on
both at phone and desktop and **fails** on console errors, a view that never draws or
anything wider than 390px. The `pr-screenshots` skill (`.claude/skills/pr-screenshots/`)
walks through it, up to putting the images in the PR description.

```bash
git worktree add ../shots-main origin/main
./.venv/bin/python scripts/serve_fake.py --port 8791 --repo ../shots-main &   # before
./.venv/bin/python scripts/serve_fake.py --port 8790 &                        # after (this checkout)
npm --prefix tests install
node scripts/screenshots.js --before http://127.0.0.1:8791 --after http://127.0.0.1:8790 \
     --view home/squad --focus '.season-card' --out tests/screenshots/pr
```

Names and numbers on the fake league are test data. `tests/test_serve_fake.py` keeps
the server working as the backend changes.

## Look and motion (by eye)

The suite can't judge whether it looks right. After a UI change, run it, then
open the screenshots in `tests/screenshots/` — the landing screen and every tab
on phone and desktop. Also check by hand with the OS "reduce motion" setting on:
everything should simply be there, no entrances, glows or sweeps.

```bash
python3 scripts/check_contrast.py      # WCAG AA for the palette; exits 1 on a miss
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
- Any solver change: run `tests/test_solver.py`, then solve team 1 at horizons
  1, 5 and 8 and from scratch (`paths: 3`) and check every plan is `feasible`.
- Any backend change: the unit tests (`-m unittest discover -s tests`) stay green.
- Headless only. Don't drive the user's own browser.
