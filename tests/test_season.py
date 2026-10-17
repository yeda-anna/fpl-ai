"""The season rank chart's data: FPL's gameweek history, shaped for Home → My squad.

`analysis.season_history` turns /entry/{id}/history/ "current" into the weeks the chart
draws, each with its rank and the climb since the week before (positive = up the table),
plus the best and worst rank so far. `/api/entry/{id}` carries it as `season`.

Run:  ./.venv/bin/python tests/test_season.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes      # noqa: E402  (puts backend/ on the path)
import analysis   # noqa: E402
import fpl_api    # noqa: E402


def ev(gw, rank, points=50, hits=0, transfers=1, bench=4, total=None):
    """One gameweek as FPL's history endpoint returns it."""
    return {"event": gw, "points": points, "total_points": total if total is not None else points * gw,
            "rank": 1000, "overall_rank": rank, "event_transfers": transfers,
            "event_transfers_cost": hits, "points_on_bench": bench, "bank": 5, "value": 1000}


class SeasonHistoryTests(unittest.TestCase):
    def test_a_smaller_rank_is_a_climb(self):
        s = analysis.season_history([ev(1, 2000000), ev(2, 1500000), ev(3, 1800000)])
        self.assertEqual([w["climb"] for w in s["weeks"]], [None, 500000, -300000])

    def test_weeks_come_out_in_order_whatever_order_fpl_sends(self):
        s = analysis.season_history([ev(3, 300), ev(1, 100), ev(2, 200)])
        self.assertEqual([w["gw"] for w in s["weeks"]], [1, 2, 3])
        self.assertEqual(s["weeks"][1]["climb"], -100)

    def test_unranked_weeks_are_dropped_and_the_climb_skips_them(self):
        s = analysis.season_history([ev(1, 900000), ev(2, None), ev(3, 0), ev(4, 600000)])
        self.assertEqual([w["gw"] for w in s["weeks"]], [1, 4])
        self.assertEqual(s["weeks"][1]["climb"], 300000)

    def test_best_and_worst_and_latest(self):
        s = analysis.season_history([ev(1, 800000), ev(2, 250000), ev(3, 1200000), ev(4, 400000)])
        self.assertEqual(s["best"], {"gw": 2, "rank": 250000})
        self.assertEqual(s["worst"], {"gw": 3, "rank": 1200000})
        self.assertEqual(s["latest"]["gw"], 4)
        self.assertEqual(s["latest"]["climb"], 800000)

    def test_a_tied_best_rank_is_the_first_time_it_was_reached(self):
        s = analysis.season_history([ev(1, 5000), ev(2, 3000), ev(3, 3000)])
        self.assertEqual(s["best"]["gw"], 2)

    def test_each_week_keeps_points_hits_and_bench(self):
        w = analysis.season_history([ev(1, 10, points=72, hits=4, transfers=2, bench=11, total=72)])["weeks"][0]
        self.assertEqual(w, {"gw": 1, "points": 72, "total": 72, "rank": 10, "climb": None,
                             "transfers": 2, "hits": 4, "bench": 11})

    def test_no_history_means_no_chart(self):
        for empty in ([], None, [ev(1, None)]):
            self.assertEqual(analysis.season_history(empty),
                             {"weeks": [], "best": None, "worst": None, "latest": None})

    def test_a_single_week_is_its_own_best(self):
        s = analysis.season_history([ev(1, 3456789)])
        self.assertEqual(len(s["weeks"]), 1)
        self.assertEqual(s["best"], s["worst"])
        self.assertIsNone(s["latest"]["climb"])


class EntryRouteTests(unittest.TestCase):
    """`/api/entry/{id}` carries the season, on the demo team (no FPL account, no network)."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import main
        cls._cache = tempfile.TemporaryDirectory()
        fpl_api.CACHE_ONLY, fpl_api.CACHE_DIR = True, cls._cache.name
        e = fakes.engine(with_elo=True)
        main._engine.update(obj=e, built=time.time() + 10 ** 9)
        main._rows_cache.clear()
        main.solver_mod.configure(e.rules)
        cls.t = TestClient(main.app).get("/api/entry/0").json()

    @classmethod
    def tearDownClass(cls):
        cls._cache.cleanup()

    def test_the_season_matches_the_history(self):
        season, hist = self.t["season"], self.t["history"]
        self.assertEqual([w["gw"] for w in season["weeks"]], [h["gw"] for h in hist])
        self.assertEqual([w["rank"] for w in season["weeks"]], [h["rank"] for h in hist])
        self.assertEqual(season["latest"]["rank"], self.t["entry"]["overall_rank"])

    def test_the_climbs_add_up_to_the_whole_season(self):
        w = self.t["season"]["weeks"]
        self.assertEqual(sum(x["climb"] for x in w[1:]), w[0]["rank"] - w[-1]["rank"])

    def test_the_demo_runs_to_the_current_gameweek_with_its_shocker_last(self):
        w = self.t["season"]["weeks"]
        self.assertEqual(w[-1]["gw"], fakes.CURRENT_GW)
        self.assertLess(w[-1]["climb"], 0, "the demo's last week is a shocker, so it drops")


if __name__ == "__main__":
    unittest.main()
