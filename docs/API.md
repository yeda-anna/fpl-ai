# API reference

All routes are served by `backend/main.py`. JSON in, JSON out. Interactive
docs: `/docs` (Swagger) and `/redoc` while the server runs.

**Common parameters**

- `horizon` — gameweeks ahead, 1–10 (route defaults differ; see below).
- `made` — transfers made in the FPL app for the coming gameweek, which FPL keeps
  private until the deadline, as `"<out_id>-<in_id>,…"`. Accepted wherever a team is
  loaded (`/api/entry`, `/api/rate`, `/api/solve`, `/api/chips`, `/api/copilot`); a pair
  that no longer fits the squad (or swaps positions) is ignored.
- `overrides` — the manager's minute edits as `"<player_id>:<minutes>,…"`,
  e.g. `12:70,328:0`. Minutes clamp to 0–90; malformed pairs are ignored.

**The demo team**: team ID `0` never exists on FPL, so every team route answers
for *Gut Feeling FC*, a made-up manager (`backend/demo.py`): a legal squad
picked on vibes and an invented season. No FPL calls are made for it; `entry.demo`
is `true` in `/api/entry/0`.

**Errors**: unknown team or league → `404` with a readable `detail`. FPL
unreachable with nothing cached → `503`.

## Read routes

| Method | Path | Parameters | Returns |
| --- | --- | --- | --- |
| GET | `/api/meta` | — | current/next gameweek, teams, positions, rules summary, deadlines |
| GET | `/api/players` | `horizon`=5, `position` (1–4), `team`, `max_price`, `min_minutes`=0, `search`, `available_only`=false, `sort`=`xpts_total`, `limit`=60, `offset`=0, `overrides` | paged projection rows with `total` |
| GET | `/api/player/{id}` | `horizon`=6, `minutes` | one player's per-fixture breakdown and minutes model |
| GET | `/api/entry/{team_id}` | `horizon`=5, `overrides`, `made`, `fresh`=false | manager, rank, bank, free transfers, `pending_transfers` (`manual` when entered by hand), squad with xPts, best XI, captain picks, `history` (FPL's per-gameweek points and rank) and `season` (the rank chart: `weeks` with each week's `climb` since the one before, positive = up the table, plus `best`, `worst`, `latest`; unranked weeks are left out). `fresh=1` expires this manager's cached FPL data first (throttled to once per 20 s per team); the app sends it on the first read after a page load |
| GET | `/api/rate/{team_id}` | `horizon`=5, `overrides`, `made` | grade out of 100, sub-scores, strengths, weaknesses |
| GET | `/api/picks` | `horizon`=5 | captains, differentials, value picks and dream team for next gameweek |
| GET | `/api/compare` | `a`, `b`, `horizon`=6 | two players side by side, week by week |
| GET | `/api/entry/{team_id}/leagues` | — | **every mini-league the manager is in** (read from their public FPL profile): for each private league their place and movement, points, the leader, the gap to the leader and to the neighbours either side, and the league's average and best week; FPL's own leagues (Overall, country, club …) and head-to-head leagues with place and percentile; and a summary (leading, top three, climbing, best place). Reads up to 15 private leagues in full (one or two standings pages each, four at a time), the rest are listed. Any Team ID works; the demo team (0) is in none; unknown team → 404 |
| GET | `/api/league/{league_id}` | `horizon`=5, `rivals`=12 (2–25), `entry` | rival ownership, effective ownership, Monte Carlo win odds. With `entry`, that manager is always in the table, even outside the top `rivals` |
| GET | `/api/scout` | `horizon`=5 | price-change odds, set-piece takers, DEFCON leaders |
| GET | `/api/lineups` | `horizon`=1 | predicted XIs per club |

## Action routes

### `POST /api/solve`

```json
{
  "team_id": 1,
  "horizon": 5,
  "max_hits": 2,
  "wildcard_gw": null,
  "free_hit_gw": null,
  "free_transfers": null,
  "bank": null,
  "pool_size": 160,
  "paths": 3,
  "overrides": null,
  "min_chance": 75
}
```

`free_transfers` and `bank` default to the manager's real values. `min_chance`
(0–100) is the chance of playing a player needs to be bought or captained in the
coming gameweek; the response echoes it with `passed_over`, the best players it
left out. The response
has up to `paths` plans, each with per-gameweek transfers, XI, bench, captain,
vice, hits and xPts, plus the do-nothing baseline and a `feasible` flag.

### `POST /api/chips`

`{"team_id": 1, "horizon": 8, "overrides": null}` — every chip scored in every
gameweek within FPL's chip windows, then the best combined plan.

### `POST /api/copilot`

`{"question": "Who should I captain?", "team_id": 1, "horizon": 5,
"overrides": null}` — detects the intent (captain, hit, transfer, rate, chip,
differential, bench, price, overview) and answers from the model's numbers.
Rules-based; no language model involved.

## Platform routes

| Path | Purpose |
| --- | --- |
| `/version` | Current frontend build id, `no-store`; open apps poll it to reload after a deploy |
| `/healthz` | Liveness. Instant, never builds the model: `{"ok": true, "model_ready": bool}` |
| `/api/health` | Readiness. Builds the model if needed and reports gameweeks |
| `/` | the single-page app (`no-store`, CSS/JS links content-hashed); other files under `/static/` |

## Examples

```bash
curl -s localhost:8787/api/meta | python3 -m json.tool | head
curl -s "localhost:8787/api/players?position=3&max_price=7&limit=5"
curl -s -X POST localhost:8787/api/solve -H 'content-type: application/json' \
     -d '{"team_id":1,"horizon":4,"paths":2}'
curl -s -o /dev/null -w '%{http_code}\n' localhost:8787/api/entry/999999999   # 404
```
