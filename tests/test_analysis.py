"""Best eleven, Free Hit team, Rate My Team, compare, weekly picks, chips and mini-leagues
on a made-up 20-club league.

Run:  ./.venv/bin/python tests/test_analysis.py
"""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes      # noqa: E402  (puts backend/ on the path)
import analysis   # noqa: E402
import fpl_api    # noqa: E402

E = fakes.engine()
ROWS = E.all_players_horizon(E.next_gw, 3)
INDEX = fakes.by_id(ROWS)


def xp(r, t=0):
    return r["per_gw"][t]["xpts"]


class BestXITests(unittest.TestCase):
    def setUp(self):
        self.squad = fakes.legal_squad(ROWS)

    def test_the_eleven_is_a_legal_formation(self):
        total, xi, formation = analysis.best_xi(self.squad)
        shape = Counter(r["position"] for r in xi)
        self.assertEqual(len(xi), 11)
        self.assertEqual(shape[1], 1)
        self.assertEqual(formation, "%d-%d-%d" % (shape[2], shape[3], shape[4]))
        self.assertAlmostEqual(total, sum(xp(r) for r in xi), places=6)

    def test_no_legal_eleven_beats_it(self):
        total, _xi, _f = analysis.best_xi(self.squad)
        by_pos = {q: sorted((r for r in self.squad if r["position"] == q), key=lambda r: -xp(r)) for q in (1, 2, 3, 4)}
        for d in range(3, 6):
            for m in range(2, 6):
                f = 10 - d - m
                if 1 <= f <= 3:
                    alt = sum(xp(r) for r in by_pos[1][:1] + by_pos[2][:d] + by_pos[3][:m] + by_pos[4][:f])
                    self.assertGreaterEqual(total + 1e-9, alt)

    def test_split_benches_the_other_four_and_captains_the_top_starter(self):
        split = analysis.squad_split(self.squad)
        self.assertEqual(len(split["bench"]), 4)
        self.assertEqual({r["id"] for r in split["xi"]} | {r["id"] for r in split["bench"]},
                         {r["id"] for r in self.squad})
        self.assertEqual(split["captain"]["id"], max(split["xi"], key=xp)["id"])
        self.assertEqual(split["captain_xpts"], round(xp(split["captain"]), 2))

    def test_too_few_players_gives_no_eleven(self):
        self.assertEqual(analysis.best_xi(self.squad[:5]), (0.0, [], "n/a"))


class FreeHitTeamTests(unittest.TestCase):
    def test_the_free_hit_eleven_is_legal_and_skips_the_injured(self):
        fh = analysis._one_week_dream_team(ROWS, 0, 100.0)
        self.assertEqual(len(fh["xi"]), 11)
        clubs = Counter(INDEX[p["id"]]["team"] for p in fh["xi"])
        self.assertLessEqual(max(clubs.values()), 3)
        self.assertTrue(all(p["status"] not in ("i", "u", "n", "s") for p in fh["xi"]))
        self.assertIn(fh["captain"]["id"], {p["id"] for p in fh["xi"]})
        self.assertLessEqual(fh["cost"], 100.0 - 16.0 + 1e-6, "leaves room for a four-man bench")


class ClosenessTests(unittest.TestCase):
    def test_the_scale_runs_from_65_to_95_percent_of_the_optimum(self):
        self.assertEqual(analysis._closeness(0.50), 0.0)
        self.assertEqual(analysis._closeness(0.65), 0.0)
        self.assertEqual(analysis._closeness(0.80), 50.0)
        self.assertEqual(analysis._closeness(0.95), 100.0)
        self.assertEqual(analysis._closeness(1.20), 100.0)


class RateTeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.squad = fakes.legal_squad(ROWS)
        cls.bank = (1000 - sum(r["now_cost"] for r in cls.squad)) / 10.0
        cls.rating = analysis.rate_team(E, ROWS, cls.squad, {"name": "Test FC"}, cls.bank, 3)

    def test_scores_are_bounded_and_the_grade_matches_the_overall(self):
        r = self.rating
        for k, v in r["scores"].items():
            self.assertTrue(0.0 <= v <= 100.0, k)
        self.assertTrue(0.0 <= r["overall"] <= 100.0)
        bands = [(90, "A+"), (82, "A"), (74, "B+"), (65, "B"), (56, "C+"), (45, "C"), (-1, "D")]
        self.assertEqual(r["grade"], next(g for floor, g in bands if r["overall"] >= floor))

    def test_the_cheapest_squad_trails_the_benchmark_and_is_told_so(self):
        r = self.rating
        self.assertLess(r["squad_xpts"], r["benchmark_xpts"])
        self.assertEqual(len(r["benchmark_squad"]), 15)
        self.assertTrue(any("best squad" in n for n in r["notes"]))
        self.assertTrue(r["top_upgrades"], "a bargain-bin squad has upgrades")
        for u in r["top_upgrades"]:
            self.assertEqual(u["out"]["position"], u["in"]["position"])
            self.assertGreater(u["gain"], 1.5)

    def test_flagged_players_are_called_out(self):
        squad = list(self.squad)
        doubt = INDEX[33]                                  # 50% doubtful in the fake league
        slot = next(i for i, r in enumerate(squad) if r["position"] == doubt["position"])
        squad[slot] = doubt
        r = analysis.rate_team(E, ROWS, squad, {}, self.bank, 3)
        self.assertIn(33, [p["id"] for p in r["flagged"]])
        self.assertLess(r["scores"]["fitness"], 100.0)
        self.assertTrue(r["notes"][0].startswith("1 flagged player"))


class CompareTests(unittest.TestCase):
    def test_the_verdict_names_the_higher_projection(self):
        a, b = ROWS[0], ROWS[-1]
        out = analysis.compare(E, ROWS, a["id"], b["id"])
        self.assertGreater(out["margin"], 0.8)
        self.assertTrue(out["verdict"].startswith(a["web_name"]))
        self.assertEqual(len(out["a"]["per_gw"]), 3)

    def test_an_unknown_player_is_an_error_not_a_crash(self):
        self.assertEqual(analysis.compare(E, ROWS, ROWS[0]["id"], 99999), {"error": "player not found"})


class WeeklyPicksTests(unittest.TestCase):
    def test_captains_are_sorted_and_available(self):
        out = analysis.weekly_picks(E, ROWS, E.next_gw)
        caps = out["captains"]
        self.assertEqual(len(caps), 8)
        self.assertEqual([c["xpts"] for c in caps], sorted((c["xpts"] for c in caps), reverse=True))
        self.assertTrue(all(c["status"] == "a" for c in caps))
        self.assertTrue(all(d["selected_by_percent"] < 15.0 for d in out["differentials"]))
        self.assertEqual(set(out["by_position"]), {"GKP", "DEF", "MID", "FWD"})
        self.assertEqual(len(out["dream_team"]["xi"]), 11)


class ChipStrategyTests(unittest.TestCase):
    def test_used_chips_are_not_offered_and_plans_never_double_up(self):
        squad = fakes.legal_squad(ROWS)
        history = [{"name": "wildcard", "event": 2}, {"name": "3xc", "event": 5}]
        out = analysis.chip_strategy(E, ROWS, squad, [], 0.0, 1, 3, history)
        self.assertEqual(out["options"]["WC"], [])          # no current squad given, and already used
        self.assertEqual(out["options"]["TC"], [])          # played in GW5, this window
        self.assertEqual({o["gw"] for o in out["options"]["BB"]}, {9, 10, 11})
        for plan in out["best_plans"]:
            weeks = [p["gw"] for p in plan["picks"]]
            self.assertEqual(len(weeks), len(set(weeks)))
        self.assertEqual(out["windows"]["wildcard"], [{"start": 20, "stop": 38}])
        self.assertEqual(sorted(out["chips_used"]), ["3xc (GW5)", "wildcard (GW2)"])

    def test_a_bench_boost_is_worth_the_bench(self):
        squad = fakes.legal_squad(ROWS)
        out = analysis.chip_strategy(E, ROWS, squad, [], 0.0, 1, 3, [])
        for opt, base in zip(sorted(out["options"]["BB"], key=lambda o: o["gw"]), out["baseline"]):
            self.assertEqual(opt["gain"], round(base["bench_xpts"], 2))


class MiniLeagueTests(unittest.TestCase):
    def standings(self):
        return {"league": {"id": 1, "name": "Office"},
                "standings": {"results": [
                    {"entry": 100 + i, "entry_name": "Team %d" % i, "player_name": "Mgr %d" % i,
                     "rank": i + 1, "total": 500 - 10 * i} for i in range(4)]}}

    def picks_for(self, entry, gw):
        # each rival owns the cheapest legal squad, with one star swapped in by entry number
        squad = [r["id"] for r in fakes.legal_squad(ROWS)]
        squad[0] = [r for r in ROWS if r["position"] == fakes.by_id(ROWS)[squad[0]]["position"]][entry % 4]["id"]
        return {"picks": [{"element": pid} for pid in squad]}

    def test_win_odds_add_up_and_the_leader_is_favourite(self):
        with mock.patch.object(fpl_api, "entry_picks", side_effect=self.picks_for):
            out = analysis.mini_league(E, ROWS, self.standings(), E.current_gw, 3, sims=800)
        self.assertEqual(out["rivals_analysed"], 4)
        self.assertAlmostEqual(sum(m["win_probability"] for m in out["managers"]), 100.0, delta=0.5)
        self.assertAlmostEqual(sum(m["top3_probability"] for m in out["managers"]), 300.0, delta=1.5)
        self.assertEqual(out["managers"][0]["entry"], 100, "a 30-point lead over 3 weeks should hold")
        self.assertTrue(all(0 <= o["pct"] <= 100 for o in out["ownership"]))

    def test_the_same_league_gives_the_same_odds(self):
        with mock.patch.object(fpl_api, "entry_picks", side_effect=self.picks_for):
            a = analysis.mini_league(E, ROWS, self.standings(), E.current_gw, 3, sims=300)
            b = analysis.mini_league(E, ROWS, self.standings(), E.current_gw, 3, sims=300)
        self.assertEqual([m["win_probability"] for m in a["managers"]],
                         [m["win_probability"] for m in b["managers"]])

    def test_a_rival_whose_picks_fail_is_skipped(self):
        def flaky(entry, gw):
            if entry == 102:
                raise RuntimeError("FPL said no")
            return self.picks_for(entry, gw)
        with mock.patch.object(fpl_api, "entry_picks", side_effect=flaky):
            out = analysis.mini_league(E, ROWS, self.standings(), E.current_gw, 3, sims=200)
        self.assertEqual(out["rivals_analysed"], 3)
        self.assertNotIn(102, [m["entry"] for m in out["managers"]])


if __name__ == "__main__":
    unittest.main()
