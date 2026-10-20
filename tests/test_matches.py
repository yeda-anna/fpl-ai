"""Match predictions: the scoreline model, the pick, and a gameweek of fixtures.

Run:  ./.venv/bin/python tests/test_matches.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import matches   # noqa: E402


class GridTests(unittest.TestCase):
    def test_the_scoreline_table_sums_to_one(self):
        for lh, la in [(1.4, 1.1), (0.3, 0.3), (3.0, 0.4), (2.2, 2.2)]:
            self.assertAlmostEqual(sum(map(sum, matches.scoreline_grid(lh, la))), 1.0, places=9)

    def test_dixon_coles_lifts_low_scoring_draws(self):
        indep = matches.scoreline_grid(1.3, 1.1, rho=0.0)
        dc = matches.scoreline_grid(1.3, 1.1)
        self.assertGreater(dc[0][0], indep[0][0])
        self.assertGreater(dc[1][1], indep[1][1])
        self.assertGreater(sum(dc[i][i] for i in range(9)), sum(indep[i][i] for i in range(9)))

    def test_outcome_chances_sum_to_one_and_follow_strength(self):
        p = matches.predict(2.1, 0.8)
        self.assertAlmostEqual(p["p_home"] + p["p_draw"] + p["p_away"], 1.0, places=3)
        self.assertGreater(p["p_home"], p["p_draw"])
        self.assertGreater(p["p_draw"], p["p_away"])
        mirror = matches.predict(0.8, 2.1)
        self.assertAlmostEqual(p["p_home"], mirror["p_away"], places=4)       # the same match the other way round
        self.assertAlmostEqual(p["p_cs_home"], mirror["p_cs_away"], places=4)


class PickTests(unittest.TestCase):
    def outcome(self, score):
        return "home" if score[0] > score[1] else "away" if score[0] < score[1] else "draw"

    def test_the_predicted_score_always_agrees_with_the_pick(self):
        for lh in (0.4, 0.9, 1.3, 1.8, 2.6):
            for la in (0.4, 0.9, 1.3, 1.8, 2.6):
                p = matches.predict(lh, la)
                self.assertEqual(self.outcome(p["score"]), p["pick"], (lh, la, p["score"], p["pick"]))

    def test_a_clear_favourite_is_picked_to_win_by_a_goal_or_more(self):
        p = matches.predict(2.5, 0.6)
        self.assertEqual(p["pick"], "home")
        self.assertGreater(p["score"][0], p["score"][1])
        self.assertEqual(matches.predict(0.6, 2.5)["pick"], "away")

    def test_two_evenly_matched_low_scoring_sides_are_a_draw(self):
        p = matches.predict(0.9, 0.9)
        self.assertEqual(p["pick"], "draw")
        self.assertEqual(p["score"][0], p["score"][1])

    def test_top_scores_are_ordered_and_include_the_favourite_score_or_better(self):
        p = matches.predict(1.7, 1.0)
        probs = [t["p"] for t in p["top_scores"]]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertEqual(len(probs), 6)
        self.assertLessEqual(p["score_prob"], probs[0] + 1e-9)

    def test_clean_sheets_goals_and_both_to_score(self):
        low, high = matches.predict(0.7, 0.7), matches.predict(2.0, 2.0)
        self.assertGreater(low["p_cs_home"], high["p_cs_home"])
        self.assertGreater(high["p_over25"], low["p_over25"])
        self.assertGreater(high["p_btts"], low["p_btts"])


class FakeEngine:
    """Three fixtures in gameweek 8 (one finished) and Club 1 the strongest side."""
    teams = {i: {"name": "Club %d" % i, "short_name": "C%d" % i} for i in range(1, 7)}
    STRENGTH = {1: 1.8, 2: 1.2, 3: 1.0, 4: 0.9, 5: 0.8, 6: 0.7}
    FIX = [
        {"id": 3, "event": 8, "team_h": 5, "team_a": 6, "kickoff_time": "2026-10-19T14:00:00Z", "finished": False, "team_h_score": None, "team_a_score": None, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"id": 1, "event": 8, "team_h": 1, "team_a": 2, "kickoff_time": "2026-10-18T14:00:00Z", "finished": True, "team_h_score": 2, "team_a_score": 1, "team_h_difficulty": 4, "team_a_difficulty": 2},
        {"id": 2, "event": 8, "team_h": 3, "team_a": 4, "kickoff_time": "2026-10-18T16:30:00Z", "finished": False, "team_h_score": None, "team_a_score": None, "team_h_difficulty": 3, "team_a_difficulty": 3},
    ]

    def fixtures_in(self, gw):
        return [f for f in self.FIX if f["event"] == gw]

    def fixture_goals(self, team, opp, home):
        s = self.STRENGTH
        return 1.4 * s[team] / s[opp] * (1.1 if home else 0.92), 1.4 * s[opp] / s[team] * (0.92 if home else 1.1)


class GameweekTests(unittest.TestCase):
    def setUp(self):
        self.gw = matches.gameweek(FakeEngine(), 8)
        self.ms = self.gw["matches"]

    def test_every_fixture_is_predicted_in_kick_off_order(self):
        self.assertEqual([m["id"] for m in self.ms], [1, 2, 3])
        self.assertEqual(self.gw["gw"], 8)

    def test_each_match_carries_teams_odds_and_a_score(self):
        m = self.ms[0]
        self.assertEqual((m["home"]["short"], m["away"]["name"]), ("C1", "Club 2"))
        self.assertAlmostEqual(m["p_home"] + m["p_draw"] + m["p_away"], 1.0, places=3)
        self.assertEqual(m["pick"], "home")                                    # the strongest side at home
        self.assertEqual(len(m["score"]), 2)

    def test_finished_matches_carry_the_real_score_and_unplayed_ones_do_not(self):
        self.assertEqual(self.ms[0]["actual"], [2, 1]); self.assertTrue(self.ms[0]["finished"])
        self.assertIsNone(self.ms[1]["actual"]); self.assertFalse(self.ms[1]["finished"])

    def test_the_summary_describes_the_round(self):
        s = self.gw["summary"]
        self.assertEqual(s["matches"], 3)
        self.assertEqual(s["home_wins"] + s["draws"] + s["away_wins"], 3)
        self.assertEqual(s["biggest_favourite"]["short"], "C1")
        self.assertTrue(s["biggest_favourite"]["home"])
        self.assertGreater(s["goals_per_match"], 1.5)

    def test_an_empty_gameweek(self):
        out = matches.gameweek(FakeEngine(), 30)
        self.assertEqual(out["matches"], [])
        self.assertEqual(out["summary"], {"matches": 0})


if __name__ == "__main__":
    unittest.main()
