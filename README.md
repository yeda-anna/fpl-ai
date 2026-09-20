# FPL Copilot — local clone

A local rebuild of the tools on fplcopilot.com, running entirely on this machine
against the official Fantasy Premier League public API.

## Run

    ./run.sh            # http://127.0.0.1:8787
    PORT=9000 ./run.sh  # different port

## What's inside

    backend/fpl_api.py   official FPL endpoints + disk cache
    backend/xpts.py      the expected-points rule engine
    backend/solver.py    multi-gameweek MIP transfer optimiser (PuLP/CBC)
    backend/analysis.py  chips, rate-my-team, compare, weekly picks, mini-leagues
    backend/main.py      FastAPI routes + static hosting
    frontend/            single-page app (no build step)

## Data sources

Every number traces back to these public, unauthenticated endpoints:

| Endpoint | Used for |
| --- | --- |
| `/api/bootstrap-static/` | players, teams, gameweeks, per-90 stats, prices, ownership |
| `/api/fixtures/` | full season fixture list with difficulty ratings |
| `/api/entry/{id}/` | manager profile, squad value, overall rank |
| `/api/entry/{id}/history/` | gameweek history and chips already played |
| `/api/entry/{id}/event/{gw}/picks/` | the 15 players in a squad, purchase prices, bank |
| `/api/element-summary/{id}/` | per-fixture player history |
| `/api/leagues-classic/{id}/standings/` | mini-league tables |

Responses are cached under `.cache/` with short TTLs so repeated requests
don't hammer the API. If the API is unreachable the last good copy is served.

## The expected-points model

1. **Team strength.** Season xG and xG conceded per game, shrunk toward the
   league average of 1.45 goals (a six-game prior), give each club an attack
   and a defence multiplier.
2. **Fixture.** Poisson means for both sides, with a 1.10 / 0.92 home-away split.
3. **Minutes.** Availability (status and chance-of-playing) times start rate,
   producing P(play), P(60+) and expected minutes. Overridable per player.
4. **Returns.** A player's xG and xA per 90 are shrunk toward a prior fitted
   from his price, then taken as a share of his team's attack and scaled onto
   the fixture's expected goals.
5. **Scoring.** FPL's own table — 6/6/5/4 per goal by position, 3 per assist,
   Poisson clean sheets, −1 per two conceded, one point per three saves,
   2 points for clearing the defensive-contribution threshold (10 for
   defenders, 12 for midfielders and forwards), bonus estimated from BPS per 90,
   cards, and appearance points.

## The solver

A mixed-integer program over the whole horizon at once: squad, starting eleven,
captain and transfers are all decision variables. Constraints are the real FPL
rules — 15 players, 2/5/5/3, three per club, legal formations, actual bank and
selling prices (profit halved), free transfers banking up to five, −4 per extra
transfer. Bench points count at 12%, and each further gameweek is discounted 13%.

The candidate pool is trimmed to the ~160 best-projecting players plus everyone
you already own, which keeps CBC to a few seconds.
