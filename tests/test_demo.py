"""The demo team must be a legal squad under the season's rules, every time.

Run:  ./.venv/bin/python tests/test_demo.py
"""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import demo            # noqa: E402

QUOTA = {1: 2, 2: 5, 3: 5, 4: 3}


def league(n_clubs=20, per_pos=None):
    """A made-up player list: every club has keepers, defenders, midfielders and forwards
    at a spread of prices, with a few flagged as injured."""
    per_pos = per_pos or {1: 3, 2: 8, 3: 8, 4: 4}
    base = {1: 40, 2: 40, 3: 45, 4: 45}
    out, pid = [], 1
    for club in range(1, n_clubs + 1):
        for pos, n in per_pos.items():
            for k in range(n):
                cost = base[pos] + (club * 7 + k * 11) % (90 if pos > 2 else 25)
                out.append({"id": pid, "team": club, "element_type": pos, "now_cost": cost,
                            "selected_by_percent": str((pid * 13) % 50), "status": "i" if pid % 37 == 0 else "a"})
                pid += 1
    return out


def events(n):
    return [{"id": i, "average_entry_score": 50 + i % 7, "finished": True} for i in range(1, n + 1)]


class DemoTests(unittest.TestCase):
    def check_legal(self, squad, budget=1000, club_limit=3):
        self.assertEqual(len(squad), sum(QUOTA.values()))
        self.assertEqual(dict(Counter(p["element_type"] for p in squad)), QUOTA)
        self.assertLessEqual(max(Counter(p["team"] for p in squad).values()), club_limit)
        self.assertLessEqual(sum(p["now_cost"] for p in squad), budget)
        self.assertEqual(len({p["id"] for p in squad}), len(squad))

    def test_the_squad_is_legal(self):
        self.check_legal(demo.pick_squad(league(), QUOTA, 3, 1000))

    def test_legal_on_a_tight_budget_and_club_limit(self):
        self.check_legal(demo.pick_squad(league(), QUOTA, 2, 900), budget=900, club_limit=2)

    def test_it_keeps_an_injured_star(self):
        squad = demo.pick_squad(league(), QUOTA, 3, 1000)
        self.assertTrue(any(p["status"] == "i" for p in squad))

    def test_it_picks_on_vibes_the_priciest_names_first(self):
        squad = demo.pick_squad(league(), QUOTA, 3, 1000)
        fwd = max(p["now_cost"] for p in league() if p["element_type"] == 4)
        self.assertIn(fwd, [p["now_cost"] for p in squad])

    def test_only_players_the_model_knows(self):
        allowed = {p["id"] for p in league() if p["id"] % 2}
        squad = demo.pick_squad(league(), QUOTA, 3, 1000, allowed)
        self.check_legal(squad)
        self.assertTrue(all(p["id"] in allowed for p in squad))

    def test_same_squad_every_time(self):
        self.assertEqual(demo.pick_squad(league(), QUOTA, 3, 1000), demo.pick_squad(league(), QUOTA, 3, 1000))

    def test_the_season_ends_in_a_shocker(self):
        h = demo.history(events(7), 7)
        self.assertEqual([r["event"] for r in h["current"]], list(range(1, 8)))
        self.assertEqual(h["current"][-1]["points"], (50 + 7 % 7) - 19)
        self.assertEqual(h["chips"][0]["name"], "wildcard")

    def test_team_is_shaped_like_fpl(self):
        t = demo.team(league(), events(5), 5, QUOTA, 3, 1000)
        self.assertEqual(t["entry"]["id"], demo.DEMO_ID)
        self.assertEqual(len(t["picks"]["picks"]), 15)
        spent = sum(p["purchase_price"] for p in t["picks"]["picks"])
        self.assertEqual(spent + t["picks"]["entry_history"]["bank"], 1000)
        self.assertEqual(t["entry"]["summary_overall_points"], sum(r["points"] for r in t["history"]["current"]))


if __name__ == "__main__":
    unittest.main()
