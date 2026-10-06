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

The player's share of his club's xG and xA per 90, shrunk toward a price-based
prior by position (`PLAYER_SHRINK_90S = 2.5`), scaled to the fixture's expected
goals and his expected minutes.

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
status, news, form, total_points, minutes, per_gw[], xpts_total, xpts_next,
fpl_ep_next`. Each `per_gw` entry has `gw, fixtures[] (with xmins, xpts …),
xpts, blank, double`.

## Checking it

```bash
./.venv/bin/python scripts/calibrate.py --horizon 5 --players "Haaland:MCI,Saka:ARS"
```

Healthy: mean level within ±0.3 of FPL's `ep_next`, correlation 0.5–0.75
(`ep_next` is form-based, so perfect agreement would be suspicious). See the
`calibrate-xpts` skill for the full procedure.
