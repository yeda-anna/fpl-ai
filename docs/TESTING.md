# Testing

## End-to-end (Playwright)

`tests/e2e.js` drives a headless Chromium through the whole app at two sizes,
phone 390×844 and desktop 1440×900, plus a reduced-motion pass. 110 checks.

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
- **Landing:** a first visit opens it; it has the neon pitch scene and a quip;
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
- Counters (spring tickers) land on the true value; a meteor shower crosses
  the sky behind the pages; with reduced motion everything is visible at once,
  nothing counts up and there are no meteors.
- No console errors and no failed requests (besides the deliberate unknown
  team).

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
