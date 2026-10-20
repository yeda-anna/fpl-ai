# The expected-points model

`backend/xpts.py` projects points for every player in every fixture of the
horizon. Every step maps to an FPL scoring rule; nothing is a black box.

## 1. Rules

`rules.Rules(bootstrap)` reads `game_config.scoring`, `game_settings`,
`element_types` and `chips`. Points per goal, clean sheet, assist, saves,
defensive contribution (DEFCON), cards and the concede penalty all come from
there. The constants `GOAL_PTS`, `CS_PTS` … at the top of `xpts.py` are legacy
and **unused** — do not reintroduce them.

## 2. Club strength

For each club, attack and defence multipliers relative to
`LEAGUE_GOALS_PER_TEAM = 1.45`:

- **Prior** from ClubElo ratings (via FPL-Core-Insights match files):
  `exp(±k · z)` where `z` is the Elo gap from the league mean. The slope `k` is
  fitted from this season's results, clamped to `ELO_K_RANGE = (0.0006, 0.002)`,
  default `0.0011`.
- **Evidence** from this season's xG and xG conceded.
- Blend: the prior counts as `SHRINK_GAMES = 6` games, so it fades as the season
  goes on.
- **Recent form** (`_recent_team_form`): each club's xG for and against per game
  over the last six gameweeks of live data (a club's xG is the sum of its
  players'; its xG against is what its opponents made), each game back counting
  `TEAM_FORM_DECAY = 0.8` as much. The season rate counts as `TEAM_FORM_K = 6`
  games against that run, and the result moves attack and defence by at most
  `TEAM_FORM_RANGE = (0.80, 1.25)`. So a side that has stopped creating is a
  weaker attack, and one that has started leaking is a better fixture for
  attackers. The multipliers are `form_attack` / `form_defence` in `/api/meta`'s
  `team_ratings`, and each fixture carries the opponent's (`opp_form_attack`,
  `opp_form_defence`); the player sheet says "opponent leaky lately" and so on.

## 3. Fixture goals

Poisson means for both sides: own attack × opponent defence × league average,
times `HOME_ADV = 1.10` at home or `AWAY_ADV = 0.92` away.

## 4. Minutes

`minutes_model()` gives P(play), P(start), P(60+) and expected minutes.

- **Recent form**: per-gameweek minutes from `/event/{gw}/live/`, each week back
  counting `RECENT_DECAY = 0.72` as much; recent form never outweighs the season
  by more than `RECENT_WEIGHT_CAP = 0.70`.
- **Starter minutes** learned per player (default `STARTER_MINUTES = 87`); a
  likely substitute gets `SUB_MINUTES = 22`.
- **Availability** from `status` and `chance_of_playing_next_round`; doubtful
  flags recover over the horizon.
- **Injury returners** (flag cleared within `RETURN_NEWS_DAYS = 28`) ramp in at
  `RETURN_RAMP = (60, 75)` minutes.
- **Regression to role**: further-out weeks close the gap to a player's usual
  minutes at `REVERT_RATE = 0.5` per week.
- **Loans**: `scout_risks` blocks weeks where a loanee can't face his parent
  club — zero minutes.
- **User overrides**: any minutes the manager sets in the UI replace the model's
  (0–90).

## 5. Attacking returns

The player's share of his club's xG and xA per 90, scaled to the fixture's
expected goals and his expected minutes. His per-90 rate (`attacking_rates`)
blends three things, in order of trust:

1. **Season** xG/xA per 90, shrunk toward a price-based prior by position
   (`PLAYER_SHRINK_90S = 2.5`).
2. **Recent form**: his xG/xA per 90 over the last six gameweeks (recent weeks
   weighted more, as for minutes). It counts half once he has
   `FORM_RATE_K = 4` recent 90s and never more than `FORM_RATE_CAP = 35%`.
3. **What he actually did**: season goals and assists per 90. It counts half at
   `FINISH_K = 30` season 90s and never more than `FINISH_CAP = 25%`, because
   finishing above xG mostly regresses.

**Chance to score**: `p_goal = 1 − e^(−xG)` per fixture (and `p_return` with
assists); per gameweek, the chance of at least one goal across its fixtures.
Shown in Players → Projections ("Show: Chance to score", "Sort: Chance to score,
next GW") and on the player sheet.

## 6. Defence and extras

- Clean sheet: Poisson P(0 conceded) × P(60+).
- Concede penalty: expected −1 per two goals (`expected_concede_penalty`).
- Saves: one point per three saves.
- DEFCON: P(reaching the CBIT/CBIRT threshold — DEF 10, MID/FWD 12).
- Bonus: implied from BPS per 90 (`bonus_from_bps`).
- Cards: expected deductions from season rates.

## 7. Output rows

`player_horizon()` returns, per player:
`id, web_name, team, team_short, position, now_cost, price, selected_by_percent,
status, news, chance_next, form, total_points, minutes, per_gw[], xpts_total,
xpts_next, p_goal_next, fpl_ep_next`. `chance_next` is FPL's chance of playing
next round (0–100, from `availability`). Each `per_gw` entry has `gw, fixtures[]
(with xmins, xpts, p_goal, p_return, opp_form_* …), xpts, p_goal, blank, double`.

## Match predictions

`matches.py` turns the same fixture goal expectations (`Engine.fixture_goals`: Elo
strength, this season's xG, recent form, home advantage) into a prediction for every
match. The two means give a table of scoreline chances (Poisson, with Dixon-Coles'
correction `RHO = -0.08` so 0-0 and 1-1 are not under-called), and the home win,
draw and away win chances are sums over it. The predicted result is the likeliest of
the three; the predicted score is the likeliest scoreline **inside that result** —
otherwise the headline would often read 1-1 for a match one side wins 60% of the time.
Clean sheets, both-to-score and 3+ goals come from the same table. Matches already
played use the current ratings, which include them, so the "model" score beside a
real result is in-sample, not a track record.

## Checking it

```bash
./.venv/bin/python scripts/calibrate.py --horizon 5 --players "Haaland:MCI,Saka:ARS"
```

Healthy: mean level within ±0.3 of FPL's `ep_next`, correlation 0.5–0.75
(`ep_next` is form-based, so perfect agreement would be suspicious). See the
`calibrate-xpts` skill for the full procedure.
