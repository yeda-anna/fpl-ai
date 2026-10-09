# Footy ⚽🛸

Football’s a funny old game. Might as well do the maths.

A Fantasy Premier League planner: expected points for every player, a
multi-gameweek transfer solver, chip planning, team rating, mini-league
analysis and a rules-based Copilot — all running on your own machine against
live FPL data.

**Live:** https://fpl-ai-production-966c.up.railway.app

## Run

    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    ./run.sh                  # http://127.0.0.1:8787
    PORT=9000 ./run.sh        # another port

### Deploy (Railway)

`railway.json` sets the start command and health check, so a push is all it
takes: `uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`.
`Procfile` carries the same command for other hosts. `/healthz` answers
instantly; the model builds in the background on startup.

The first time you open it on a device, the app asks for your FPL Team ID and
saves it in your browser; after that it goes straight to your team (change or
forget it from the team pill or the ⓘ menu). You can also skip and just browse.
The ID is the number in the address bar on your Points page:
`fantasy.premierleague.com/entry/<ID>/event/5`.

### On your phone

The layout becomes an app below 1024px wide: a floating neon dock with all
five tabs (Home, Plan, Players, Leagues, Ask), sub-pages in a switcher under the
title, and details opening as bottom sheets. Use **Add to Home Screen** to launch
it full-screen like a native app.

### Offline mode

`FPL_CACHE_ONLY=1 ./run.sh` serves only what's already in `.cache/` and never
calls the FPL API — useful for development on networks that can't reach it.

## What's inside

| Tool | What it does |
| --- | --- |
| Dashboard | Rank, last gameweek vs average, best XI on the pitch, captain picks, differentials, value picks, dream team |
| Expected Points | Every player across the horizon. Click any minutes figure to set your own — every other tool then uses it |
| Solver | Mixed-integer program over squad, XI, captain, vice and transfers for every gameweek at once; returns up to three distinct plans with a template rating |
| Chip Strategies | Each chip scored in every gameweek, respecting FPL's two chip windows, then combined into the best plan |
| Copilot | Plain-English questions answered straight from the model and solver |
| Rate My Team | Score out of 100 against the best squad your own budget could buy |
| Compare | Two players side by side, week by week |
| Minileagues | Rival ownership, effective ownership, and Monte Carlo win probability |
| Scout | Price-change odds, set-piece takers, defensive-contribution leaders, predicted line-ups |

## The model

**Rules come from FPL, not from code.** Scoring (including 2026/27's 10-point
goalkeeper goal), squad and club limits, budget, banked-transfer cap, sell-on
fee, formation limits and chip windows are all read from
`bootstrap-static` (`game_config`, `game_settings`, `element_types`, `chips`).

**Club strength** starts from ClubElo ratings (via the FPL-Core-Insights match
files) and is pulled toward this season's xG and xG conceded as games are
played. The goals-per-Elo-point slope is fitted from the current season.

**Minutes** come from FPL's per-gameweek `event/{gw}/live` data, weighted toward
recent weeks. The model learns each player's minutes when he starts, eases
injury returners back in (about 60′, then 75′), lets doubtful flags recover
over the horizon, regresses longer-range weeks toward a player's usual role,
and zeroes weeks where a loanee can't face his parent club (`scout_risks`).

**Points** follow a Poisson model of each fixture with home advantage, the
player's share of his club's xG and xA (shrunk toward a price-based prior when
his sample is thin), and FPL's published scoring.

**Solver** uses CBC via PuLP, stops within 0.5% of optimal, and re-solves with
each found plan ruled out to give genuinely different alternatives.

## Data sources

- Fantasy Premier League API — players, fixtures, squads, live gameweek
  stats, price-change progress, set pieces, scoring and game rules
- [FPL-Core-Insights](https://github.com/olbauday/FPL-Core-Insights) — club Elo
  ratings from its match files

Responses are cached under `.cache/`. If the API is unreachable the last good
copy is served.

## Look and feel

**Neon, in orbit.** One look, no theme picker: near-black violet, dark glass and
three neons — lime for "do this", cyan for lines and information, magenta for the
ball and celebration — split **60 : 30 : 10**. Every text colour passes WCAG AA
(`python3 scripts/check_contrast.py`).

- **An opening film** on every launch, a few seconds long and skippable: a
  couple of thousand drones wait in rows on a neon grid floor, lift off in a
  wave, swarm and lock into place as the logo portrait, light up in its colours
  and dissolve into the picture itself. The name decodes, the log types "Matchday GW8. Morale: questionable.",
  and the camera pushes in as the film irises open onto the app, which has
  loaded underneath. Keyframed with
  [Theatre.js](https://www.theatrejs.com/docs/latest); it can be turned off in
  the menu and never plays under reduced motion.
- **Landing:** the first visit on a device asks for your FPL Team ID over a neon
  pitch that draws itself while the ball flies into the net and meteors cross
  the sky. The ID is saved in your browser, so every later visit goes straight
  to your team.
- **Five tabs**, nothing hidden behind "More": **Home** (My squad · Grade ·
  Picks), **Plan** (Transfers · Chips), **Players** (Projections · Compare ·
  Prices · Line-ups · Set pieces · DEFCON), **Leagues** and **Ask**.
- **Your name up in lights:** Home is titled with your team's name from FPL, and
  My squad opens with a dark football roast of your last gameweek's score.
- **A sci-fi HUD** over the neon: target-lock corners on every panel, monospace
  readouts, a `SYS//PLAN/TRANSFERS · GW8` locator above each title, faint
  scanlines and a scan beam, a hologram pitch, and a boot sequence on the
  landing screen.
- **Motion**, vendored (no CDN), each library with its own job:
  [GSAP](https://gsap.com/docs/v3/) draws the neon SVG paths and flies the ball;
  [anime.js](https://animejs.com/documentation) runs light pulses along the
  sky's wires and draws the tab icons; [Motion](https://motion.dev) blur-fades
  cards in as you scroll to them, ticks figures up on springs, springs buttons
  back and fills the scroll-progress line;
  [AutoAnimate](https://auto-animate.formkit.com) glides the projections table
  into its new order when you sort or filter, and slides the Copilot's log down
  as new answers arrive. [Magic UI](https://magicui.design)'s effects — hyper
  text, typing, meteors, ripple, orbiting circles, border beams, the shimmer
  button, animated beams from player out to player in, the retro grid floor —
  are rebuilt in plain JS and CSS. `prefers-reduced-motion` turns all of it off.

The full system — tokens, motion, navigation, breakpoints, the drone-portrait logo
and the house voice — is in [`docs/DESIGN.md`](docs/DESIGN.md).

## Tests

    FPL_CACHE_ONLY=1 ./run.sh          # in one terminal
    npm --prefix tests ci              # once
    npm --prefix tests test            # 105 headless checks, phone + desktop + reduced motion
    ./.venv/bin/python scripts/calibrate.py --players "Haaland:MCI,Saka:ARS"

See [`docs/TESTING.md`](docs/TESTING.md).

## Documentation

| Doc | What's in it |
| --- | --- |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | components, data flow, caching, startup |
| [MODEL](docs/MODEL.md) | how xPts are built, every constant |
| [SOLVER](docs/SOLVER.md) | the MIP: variables, constraints, objective, alternatives |
| [API](docs/API.md) | every route and parameter |
| [DESIGN](docs/DESIGN.md) | palette, tokens, glass, layout, logo, voice |
| [DATA_SOURCES](docs/DATA_SOURCES.md) | FPL endpoints, FPL-Core-Insights, TTLs |
| [TESTING](docs/TESTING.md) | e2e suite, quick checks, calibration |
| [DEPLOYMENT](docs/DEPLOYMENT.md) | Railway, smoke tests, rollback, env vars |
| [CHANGELOG](docs/CHANGELOG.md) | what changed and when |

## Working on it with Claude

- [`CLAUDE.md`](CLAUDE.md) — project instructions: commands, file map and the
  rules of the road (Python 3.9, rules from FPL, tokens only, no build step,
  nothing wider than a phone). [`AGENTS.md`](AGENTS.md) points other agents there.
- [`.claude/agents/`](.claude/agents) — specialists: `model-analyst`,
  `solver-engineer`, `ui-designer`, `qa-tester`, `fpl-data-scout`,
  `release-manager`.
- [`.claude/skills/`](.claude/skills) — procedures: `run-locally`, `e2e-test`,
  `calibrate-xpts`, `deploy-railway`, `brand-and-design`, `add-feature`.
- [`.claude/settings.json`](.claude/settings.json) — safe commands allowed,
  commits/pushes/deploys ask first, force-push and `.env` reads denied.

## Layout

    backend/fpl_api.py   FPL endpoints + disk cache
    backend/rules.py     game rules read from bootstrap-static
    backend/priors.py    Elo prior and recent-form data
    backend/xpts.py      expected-points engine
    backend/solver.py    multi-gameweek MIP optimiser
    backend/analysis.py  chips, rating, compare, picks, mini-leagues
    backend/scout.py     prices, set pieces, DEFCON, line-ups, Copilot
    backend/main.py      FastAPI routes + static hosting
    frontend/            single-page app, no build step: app.js (views, tabs), motion.js (FX: GSAP, anime.js, Motion,
                         AutoAnimate), magic.js (Magic UI, rebuilt), intro.js (the Theatre.js opening film), vendor/
    scripts/check_contrast.py  WCAG AA check for the palette
    tests/               Playwright end-to-end suite
    scripts/calibrate.py projection sanity check
    docs/                the documentation above
    .claude/             agents, skills and settings for Claude Code
