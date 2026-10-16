# Testing

## End-to-end (Playwright)

`tests/e2e.js` drives a headless Chromium through the whole app at two sizes,
phone 390×844 and desktop 1440×900, plus a reduced-motion pass and a run through the demo team and the leagues list. 134 checks.

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

- **The opening film:** the page is named Papa Ranjeet; GSAP, both plugins,
  anime.js, Motion, Theatre.js and AutoAnimate load from `/static/vendor`, with
  `FX`, `Magic` and `Intro`; the film plays on launch with its timecode running
  and flies the drones traced from the portrait (`PORTRAIT`), whose picture has
  loaded, and the logo is the portrait (`logo.webp`);
  **Skip** ends it, it plays again on a fresh launch and gets out of the way by
  itself, the menu turns it off (and then the app opens straight away), it runs
  to its end on desktop, and there is none under reduced motion.
- **Landing:** a first visit opens it; it has the pitch scene and a quip;
  an empty ID and an unknown team each get a clear message; a real ID goes
  straight to Home → My squad, is saved in `localStorage`, names the team pill,
  and the first read asks FPL afresh (`fresh=1`).
- Home is titled with the team's name from FPL; My squad opens with a roast of
  the week's score (and the same line on the way back); other Home pages keep
  their own line; other tabs keep their own title.
- **Five tabs** in the dock and no "More". Every tab and every sub-page renders
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
its tour, that nothing is saved to `fplai_team`, that Grade works for team 0,
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
- Any solver change: solve team 1 at horizons 1, 5 and 8 and from scratch
  (`paths: 3`) and check every plan is `feasible`.
- Headless only. Don't drive the user's own browser.
