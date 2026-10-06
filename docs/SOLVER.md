# The solver

`backend/solver.py` plans the next N gameweeks at once as a mixed-integer
program, solved with CBC through PuLP.

## Variables (per player p, gameweek t)

| Variable | Meaning |
| --- | --- |
| `squad[p][t]` | in the 15 |
| `lineup[p][t]` | in the starting XI |
| `capt[p][t]`, `vice[p][t]` | captain, vice-captain |
| `tin[p][t]`, `tout[p][t]` | transferred in / out before gameweek t |
| `ft[t]` | free transfers available |
| `hits[t]` | paid transfers (−4 each) |
| `bank_v[t]` | money in the bank |

## Constraints

- Squad size, positional quotas, club limit, XI size and formation min/max —
  all from `rules.Rules` via `configure()`.
- Lineup ⊆ squad; one captain, one vice, different players, both starting.
- Squad flow: `squad[t] = squad[t-1] + in − out`, no in-and-out of one player
  in the same week.
- Budget: bank rolls forward; selling uses `selling_price()` (purchase price
  plus the rise less the sell-on fee, rounded down).
- Free transfers: start from the manager's count, bank one per unused week up
  to the season cap; a Wildcard or Free Hit week makes transfers free.
- `max_hits` caps paid transfers per week.
- **Building from scratch** (no current squad): the first squad is free and
  must not spend banked transfers.

## Objective

Σₜ DECAY^t × ( XI xPts + captain xPts + 0.04 × vice xPts + 0.12 × bench xPts − 4 × hits )

`DECAY = 0.87` makes a point next week worth more than a point in five weeks,
because projections get less certain.

## Pool

`build_pool()` keeps the top `pool_size` (default 160) projected players spread
across positions, plus everyone already owned. The optimum lies inside that set
in practice; it keeps CBC fast.

## Alternatives

After the best plan, the solver re-solves with a **no-good cut** on the
transfers of each plan found (Σ tin ≤ |plan| − 1), so every alternative is a
different route, not the same one with a reshuffled bench. Up to `paths` (3).

## Stopping rule

`gapRel = 0.005` (0.5% of optimal) for the main plan and `0.01` for
alternatives, `timeLimit = 25` s. Projections carry far more uncertainty than
that.

## Feasibility

Always check `prob.sol_status > 0` (`feasible` in the result) before trusting a
plan. An infeasible result usually means the budget or club limit can't be
met — report it, don't render garbage.
