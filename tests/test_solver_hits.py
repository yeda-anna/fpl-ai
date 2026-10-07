"""Solver hits: paid transfers must be possible in any gameweek, not just the last.

The free-transfer roll-over used to force `made <= ft` in every week but the last
of the horizon, so `max_hits` only ever mattered at the end. These tests build a
synthetic league (no FPL API, no server) and check the plan against FPL's own rule,
`ft_next = min(5, max(0, ft - made) + 1)`.

Run:  ./.venv/bin/python tests/test_solver_hits.py
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import rules    # noqa: E402
import solver   # noqa: E402

MAX_FT = 5
FIRST_GW = 10
COST = 50                                   # everyone costs £5.0m, so the budget never binds
OWNED_POSITIONS = [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]
PER_CLUB = {1: 2, 2: 5, 3: 5, 4: 3}


def make_league(horizon: int = 3, star_xpts: float = 25.0, star_from: int = 0
                ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """20 clubs. The manager owns 15 players on clubs 0-4 who all project 0 xPts; the
    first player of each position at the other 15 clubs is a "star" projecting
    `star_xpts` from gameweek index `star_from` (0 before that, like the owned
    players); everyone else projects 1."""
    owned_ids = {}
    for i, position in enumerate(OWNED_POSITIONS):
        owned_ids[(i % 5, position, 0)] = True

    rows = []
    for club in range(20):
        for position, count in PER_CLUB.items():
            for k in range(count):
                key = (club, position, k)
                if key in owned_ids:
                    base = 0.0
                elif k == 0:
                    base = star_xpts
                else:
                    base = 1.0
                per_gw = []
                for t in range(horizon):
                    xp = 0.0 if (k == 0 and t < star_from) else base
                    per_gw.append({"gw": FIRST_GW + t, "xpts": xp,
                                   "fixtures": [{"opponent_short": "OPP", "home": True}]})
                rows.append({
                    "id": club * 100 + position * 10 + k, "web_name": "P%d" % (club * 100 + position * 10 + k),
                    "team": club, "team_short": "C%02d" % club, "position": position,
                    "now_cost": COST, "price": COST / 10.0, "status": "a",
                    "selected_by_percent": 1.0, "per_gw": per_gw,
                    "xpts_total": sum(g["xpts"] for g in per_gw),
                })
    squad = [{"id": club * 100 + position * 10 + k, "purchase_price": COST}
             for (club, position, k) in owned_ids]
    return rows, squad


def run(max_hits: int, free_transfers: int = 1, horizon: int = 3, star_from: int = 0, **kw):
    rows, squad = make_league(horizon, star_from=star_from)
    return solver.solve(rows, squad, 2.0, free_transfers, horizon, max_hits=max_hits,
                        pool_size=60, time_limit=20, **kw)


def made(week: Dict[str, Any]) -> int:
    return len(week["transfers_in"])


class HitsTests(unittest.TestCase):
    def test_hits_are_taken_in_the_first_week(self):
        # Every owned player projects 0 and plenty of non-owned players project 25.
        # Swapping a 0 for a 25 beats the 4-point charge by a mile, so the whole
        # allowance goes in GW1 (1 free + 6 hits), not in the last gameweek.
        plan = run(max_hits=6)
        self.assertTrue(plan["feasible"])
        first = plan["gameweeks"][0]
        self.assertEqual(made(first), 7)
        self.assertEqual(first["hits"], 6)
        self.assertEqual(first["hit_cost"], 24.0)

    def test_a_hit_week_leaves_one_free_transfer_not_an_infeasible_plan(self):
        # After a 7-transfer week the next one starts again from a single free transfer.
        plan = run(max_hits=6)
        first, second = plan["gameweeks"][0], plan["gameweeks"][1]
        self.assertEqual(second["free_transfers"], 1)
        # and GW2 can still pay for more: the four starters left at 0 xPts are swapped too
        self.assertGreater(made(second), 1)
        self.assertEqual(second["hits"], made(second) - 1)

    def test_no_hit_budget_means_no_hits_anywhere(self):
        plan = run(max_hits=0)
        self.assertTrue(plan["feasible"])
        self.assertEqual(plan["total_hits"], 0)
        # one free transfer a week: 1, then 1 (nothing banked), then 1
        self.assertEqual([made(g) for g in plan["gameweeks"]], [1, 1, 1])

    def test_hit_budgets_give_different_plans(self):
        # scout.py compares plans with 0, 1 and 2 hits allowed; they must now differ.
        by_hits = {h: run(max_hits=h) for h in (0, 1, 2)}
        totals = [by_hits[h]["total_xpts"] for h in (0, 1, 2)]
        self.assertLess(totals[0], totals[1])
        self.assertLess(totals[1], totals[2])
        self.assertEqual(made(by_hits[1]["gameweeks"][0]), 2)
        self.assertEqual(made(by_hits[2]["gameweeks"][0]), 3)

    def test_a_banked_transfer_is_still_used_before_a_hit_is_paid(self):
        # Two free transfers going in: the second one is free, only the third costs.
        plan = run(max_hits=1, free_transfers=2)
        first = plan["gameweeks"][0]
        self.assertEqual(made(first), 3)
        self.assertEqual(first["hits"], 1)

    def test_hits_wait_for_the_week_their_gain_starts(self):
        # The stars only project from GW2 (index 1). A hit costs 4 now or 4 x DECAY a
        # week later, so with nothing to gain in GW1 the charge belongs in GW2 - which
        # the old constraint could not do, GW2 not being the last week. The cap is wide
        # enough never to bind, and the gap is zero because the difference between the
        # two weeks (4 x 0.13 per hit) is smaller than the solver's usual 0.5%.
        plan = run(max_hits=14, star_from=1, gap=0.0)
        self.assertTrue(plan["feasible"])
        first, second = plan["gameweeks"][0], plan["gameweeks"][1]
        self.assertEqual(first["hits"], 0)
        self.assertGreater(second["hits"], 0)


class FplRuleTests(unittest.TestCase):
    """Whatever the solver plans, replaying FPL's rule over its transfers must agree."""

    def assert_follows_fpl(self, plan, start_ft, max_hits, chip_gws=()):
        ft = min(MAX_FT, max(1, start_ft))
        for g in plan["gameweeks"]:
            n = made(g)
            self.assertEqual(g["free_transfers"], ft, "free transfers shown for GW%d" % g["gw"])
            chip_week = g["gw"] in chip_gws
            if chip_week:
                self.assertEqual(g["hits"], 0)
            else:
                self.assertEqual(g["hits"], max(0, n - ft), "hits taken in GW%d" % g["gw"])
                self.assertLessEqual(g["hits"], max_hits)
            self.assertAlmostEqual(g["xpts"], g["xpts_before_hits"] - 4 * g["hits"], places=2)
            ft = rules.roll_free_transfers(ft, n, chip_week, MAX_FT)

    def test_plans_match_the_rule_for_every_budget(self):
        for start_ft in (1, 2, 3):
            for max_hits in (0, 1, 2, 6):
                with self.subTest(free_transfers=start_ft, max_hits=max_hits):
                    plan = run(max_hits=max_hits, free_transfers=start_ft)
                    self.assertTrue(plan["feasible"])
                    self.assert_follows_fpl(plan, start_ft, max_hits)

    def test_staggered_gains_match_the_rule(self):
        for max_hits in (1, 3):
            with self.subTest(max_hits=max_hits):
                plan = run(max_hits=max_hits, star_from=1, horizon=4)
                self.assertTrue(plan["feasible"])
                self.assert_follows_fpl(plan, 1, max_hits)

    def test_a_wildcard_week_is_free_and_keeps_the_bank(self):
        wc = FIRST_GW + 1
        plan = run(max_hits=2, wildcard_gw=wc)
        self.assertTrue(plan["feasible"])
        self.assert_follows_fpl(plan, 1, 2, chip_gws=(wc,))
        gws = plan["gameweeks"]
        self.assertEqual(gws[1]["chip"], "Wildcard")
        self.assertEqual(gws[1]["hits"], 0)
        self.assertEqual(gws[2]["free_transfers"], gws[1]["free_transfers"])

    def test_building_from_scratch_spends_no_free_transfers(self):
        rows, _ = make_league(3)
        plan = solver.solve(rows, [], 100.0, 1, 3, max_hits=0, pool_size=60, time_limit=20)
        self.assertTrue(plan["feasible"])
        first = plan["gameweeks"][0]
        self.assertEqual(made(first), solver.SQUAD_SIZE)
        self.assertEqual(plan["total_hits"], 0)
        self.assertEqual(plan["gameweeks"][1]["free_transfers"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
