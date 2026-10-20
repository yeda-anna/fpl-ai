"""The multi-gameweek solver returns legal, well-accounted plans on a made-up 20-club league.

Every plan it returns must be a squad FPL would accept in every gameweek (15 players,
2-5-5-3, at most three per club, money in the bank), with a legal eleven, a captain and
a different vice inside it, and hits charged at four points each.

Run:  ./.venv/bin/python tests/test_solver.py
"""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes    # noqa: E402  (puts backend/ on the path)
import solver   # noqa: E402

E = fakes.engine()
ROWS = E.all_players_horizon(E.next_gw, 3)
INDEX = fakes.by_id(ROWS)
FAST = dict(pool_size=80, time_limit=15)


def owned(squad_rows):
    return [{"id": r["id"], "purchase_price": r["now_cost"]} for r in squad_rows]


class LegalPlanMixin(object):
    def assert_legal(self, plan, from_scratch=False):
        self.assertTrue(plan["feasible"], plan["status"])
        for gw in plan["gameweeks"]:
            squad = gw["starting_xi"] + gw["bench"]
            ids = [p["id"] for p in squad]
            self.assertEqual(len(ids), 15, "GW%d squad size" % gw["gw"])
            self.assertEqual(len(set(ids)), 15, "GW%d has a duplicate" % gw["gw"])
            self.assertEqual(Counter(p["position"] for p in squad), Counter({1: 2, 2: 5, 3: 5, 4: 3}))
            self.assertLessEqual(max(Counter(INDEX[i]["team"] for i in ids).values()), 3)
            xi = Counter(p["position"] for p in gw["starting_xi"])
            self.assertEqual(sum(xi.values()), 11)
            self.assertEqual(xi[1], 1)
            self.assertTrue(3 <= xi[2] <= 5 and 2 <= xi[3] <= 5 and 1 <= xi[4] <= 3)
            xi_ids = {p["id"] for p in gw["starting_xi"]}
            self.assertIn(gw["captain"]["id"], xi_ids)
            self.assertIn(gw["vice_captain"]["id"], xi_ids)
            self.assertNotEqual(gw["captain"]["id"], gw["vice_captain"]["id"])
            self.assertGreaterEqual(gw["bank"], 0.0)
            if not (from_scratch and gw is plan["gameweeks"][0]):
                self.assertEqual(len(gw["transfers_in"]), len(gw["transfers_out"]))
            self.assertAlmostEqual(gw["xpts"], gw["xpts_before_hits"] - 4 * gw["hits"], places=1)
            self.assertEqual(gw["bench"][0]["position"], 1, "the reserve keeper is benched first")
        self.assertAlmostEqual(plan["total_xpts"], sum(g["xpts"] for g in plan["gameweeks"]), places=1)
        self.assertEqual(plan["total_hits"], sum(g["hits"] for g in plan["gameweeks"]))


class SellingPriceTests(unittest.TestCase):
    def test_a_rise_is_split_with_fpl_and_rounded_down(self):
        self.assertEqual(solver.selling_price(63, 60), 61)    # +0.3m rise -> keep 0.1m
        self.assertEqual(solver.selling_price(64, 60), 62)

    def test_a_fall_is_taken_in_full(self):
        self.assertEqual(solver.selling_price(55, 60), 55)

    def test_no_purchase_price_sells_at_the_current_price(self):
        self.assertEqual(solver.selling_price(71, None), 71)


class PoolTests(unittest.TestCase):
    def test_owned_players_stay_in_the_pool_however_poor(self):
        worst = ROWS[-1]
        pool = solver.build_pool(ROWS, [worst["id"]], pool_size=60)
        self.assertIn(worst["id"], {r["id"] for r in pool})

    def test_players_who_have_left_are_never_candidates(self):
        pool = solver.build_pool(ROWS, [], pool_size=300)
        self.assertNotIn(222, {r["id"] for r in pool})          # status "u" in the fake league

    def test_every_position_is_represented(self):
        pool = solver.build_pool(ROWS, [], pool_size=60)
        self.assertEqual(set(r["position"] for r in pool), {1, 2, 3, 4})


class PlanTests(LegalPlanMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.squad = fakes.legal_squad(ROWS)
        cls.bank = (1000 - sum(r["now_cost"] for r in cls.squad)) / 10.0

    def test_a_plan_from_a_real_squad_is_legal_every_week(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=1, **FAST)
        self.assert_legal(plan)
        self.assertEqual(plan["horizon"], 3)
        self.assertEqual([g["gw"] for g in plan["gameweeks"]], [9, 10, 11])

    def test_no_hits_allowed_means_at_most_the_free_transfers(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=0, **FAST)
        self.assert_legal(plan)
        self.assertEqual(plan["total_hits"], 0)
        self.assertLessEqual(len(plan["gameweeks"][0]["transfers_in"]), 1)

    def test_free_transfers_shown_follow_fpls_roll_over(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 2, 3, max_hits=0, **FAST)
        gws = plan["gameweeks"]
        self.assertEqual(gws[0]["free_transfers"], 2)
        for prev, nxt in zip(gws, gws[1:]):
            expected = min(5, max(0, prev["free_transfers"] - len(prev["transfers_in"])) + 1)
            self.assertEqual(nxt["free_transfers"], expected)

    def test_the_squad_carries_over_between_weeks(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=1, **FAST)
        before = {r["id"] for r in self.squad}
        for gw in plan["gameweeks"]:
            after = {p["id"] for p in gw["starting_xi"] + gw["bench"]}
            self.assertEqual(after, (before - {p["id"] for p in gw["transfers_out"]})
                             | {p["id"] for p in gw["transfers_in"]})
            self.assertTrue({p["id"] for p in gw["transfers_out"]} <= before)
            before = after

    def test_a_forbidden_plan_forces_a_different_route(self):
        first = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=0, **FAST)
        self.assertTrue(first["signature"], "a cheap squad should always want a transfer")
        second = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=0,
                              forbid=[first["signature"]], **FAST)
        self.assert_legal(second)
        self.assertNotEqual(sorted(first["signature"]), sorted(second["signature"]))

    def test_a_wildcard_week_rebuilds_without_hits(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=0, wildcard_gw=9, **FAST)
        self.assert_legal(plan)
        gw9 = plan["gameweeks"][0]
        self.assertEqual(gw9["chip"], "Wildcard")
        self.assertEqual(gw9["hits"], 0)
        self.assertGreater(len(gw9["transfers_in"]), 1)

    def test_a_free_hit_squad_lasts_one_week_only(self):
        # Free Hit in the middle: the week after, the manager is back to the squad they had before it
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 3, max_hits=0, free_hit_gw=10, **FAST)
        self.assert_legal(plan)
        before, hit, after = plan["gameweeks"]
        ids = lambda g: {p["id"] for p in g["starting_xi"] + g["bench"]}
        self.assertEqual(hit["chip"], "Free Hit")
        self.assertEqual(hit["hits"], 0)
        self.assertGreater(len(hit["transfers_in"]), 1)
        self.assertEqual(ids(after), (ids(before) - {p["id"] for p in after["transfers_out"]})
                         | {p["id"] for p in after["transfers_in"]})
        self.assertLessEqual(len(after["transfers_in"]), 5)             # free transfers only, no rebuild
        self.assertGreater(len(ids(hit) - ids(before)), len(ids(after) - ids(before)))

    def test_a_free_hit_in_the_first_week_reverts_to_the_squad_you_hold(self):
        plan = solver.solve(ROWS, owned(self.squad), self.bank, 1, 2, max_hits=0, free_hit_gw=9, **FAST)
        self.assert_legal(plan)
        mine = {r["id"] for r in self.squad}
        nxt = plan["gameweeks"][1]
        self.assertEqual({p["id"] for p in nxt["starting_xi"] + nxt["bench"]},
                         (mine - {p["id"] for p in nxt["transfers_out"]}) | {p["id"] for p in nxt["transfers_in"]})
        self.assertTrue({p["id"] for p in nxt["transfers_out"]} <= mine)


class FromScratchTests(LegalPlanMixin, unittest.TestCase):
    def test_an_empty_squad_builds_a_legal_fifteen_within_budget(self):
        plan = solver.solve(ROWS, [], 100.0, 1, 3, max_hits=0, **FAST)
        self.assert_legal(plan, from_scratch=True)
        self.assertEqual(len(plan["gameweeks"][0]["transfers_in"]), 15)
        gw = plan["gameweeks"][0]
        spent = sum(INDEX[p["id"]]["now_cost"] for p in gw["starting_xi"] + gw["bench"])
        self.assertLessEqual(spent, 1000)
        self.assertEqual(gw["hits"], 0)

    def test_building_from_nothing_does_not_spend_free_transfers(self):
        plan = solver.solve(ROWS, [], 100.0, 1, 2, max_hits=0, **FAST)
        self.assertEqual(plan["gameweeks"][1]["free_transfers"], 2)


if __name__ == "__main__":
    unittest.main()
