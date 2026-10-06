# Data sources

## Fantasy Premier League API

Base: `https://fantasy.premierleague.com/api`. Public, no key. All calls go
through `fpl_api.get()`, which caches to `.cache/` and serves the last good
copy when the API fails.

| Endpoint | Function | TTL | Used for |
| --- | --- | --- | --- |
| `bootstrap-static/` | `bootstrap()` | 15 min | players, clubs, gameweeks, prices, flags, **game rules** (`game_config`, `game_settings`, `element_types`, `chips`), price-change progress, set-piece orders, `scout_risks` |
| `fixtures/` | `fixtures()` | 15 min | fixture list, difficulty, kick-off, results |
| `entry/{id}/` | `entry()` | 5 min | manager name, rank, team value, bank |
| `entry/{id}/history/` | `entry_history()` | 10 min | past gameweeks, chips used (free transfers are replayed from this) |
| `entry/{id}/event/{gw}/picks/` | `entry_picks()` | 5 min | the manager's squad, captain, purchase prices |
| `entry/{id}/transfers/` | `entry_transfers()` | — | transfer history (purchase prices) |
| `event/{gw}/live/` | `live()` / `live_final()` | 2 min / 6 h once finished | per-gameweek minutes and stats for recent form |
| `element-summary/{id}/` | `element_summary()` | 30 min | one player's fixtures and history |
| `leagues-classic/{id}/standings/` | `league_standings()` | 10 min | mini-league rivals |

Fields worth knowing in `bootstrap-static.elements`:
`ep_next` (FPL's own projection, used for calibration), `chance_of_playing_next_round`,
`status`, `news`, `news_added`, `expected_goals`, `expected_assists`,
`expected_goals_conceded`, `defensive_contribution`, `bps`, `saves`,
`price_change_percent`, `price_change_projections`, `transfers_in_event`,
`penalties_order`, `corners_and_indirect_freekicks_order`,
`direct_freekicks_order`.

## FPL-Core-Insights

`https://github.com/olbauday/FPL-Core-Insights` — per-gameweek match files
(`<season>/By Gameweek/GW<n>/matches.csv`) that carry ClubElo ratings for both
sides. `priors.fetch_elo()` walks this season's gameweeks newest-first, then
the last eight of the previous season, keeping the newest valid rating per
club. Values are range-checked because rows are occasionally malformed.
Promoted clubs with no rating start 40 points below the weakest known club.
Cached in `.cache/elo_prior.json`.

## What we don't use

ClubElo's own API (unreachable from some hosts — the match files carry the same
numbers), paid scrapers, and any other site's projections. Nothing scraped
from other FPL tools is shipped.

## Etiquette

- Keep TTLs; don't hammer the FPL API. A full engine build is ~10 requests.
- Never commit `.cache/` — it's git-ignored and full of live data.
- Unknown team or league IDs return 404 from FPL; pass that through as a 404.
