"""Price changes, set pieces, DEFCON, predicted line-ups and the rules-based Copilot,
on a made-up 20-club league.

Run:  ./.venv/bin/python tests/test_scout.py
"""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes   # noqa: E402  (puts backend/ on the path)
import scout   # noqa: E402

E = fakes.engine()
ROWS = E.all_players_horizon(E.next_gw, 3)
INDEX = fakes.by_id(ROWS)


class IntentTests(unittest.TestCase):
    def test_questions_map_to_the_right_tool(self):
        cases = {
            "Who should I captain this week?": "captain",
            "Is a -4 worth taking?": "hit",
            "Who should I sell?": "transfer",
            "Rate my team": "rate",
            "When should I play my wildcard?": "chip",
            "Any differentials to climb rank?": "differential",
            "Who do I start, what's my starting XI?": "bench",
            "Who will rise in price tonight?": "price",
            "Hello": "overview",
            "": "overview",
        }
        for q, intent in cases.items():
            self.assertEqual(scout.detect_intent(q), intent, q)

    def test_matching_ignores_case(self):
        self.assertEqual(scout.detect_intent("WHO SHOULD I CAPTAIN"), "captain")


class PriceChangeTests(unittest.TestCase):
    def test_risers_and_fallers_follow_fpls_own_projection(self):
        out = scout.price_changes(E, ROWS)
        self.assertTrue(out["risers"] and out["fallers"])
        for r in out["risers"]:
            self.assertTrue(r["likelihood"] >= 2 or r["projected"] >= 80)
        for f in out["fallers"]:
            self.assertTrue(f["likelihood"] <= -2 or f["projected"] <= -80)
        risers = {r["player"]["id"] for r in out["risers"]}
        self.assertFalse(risers & {f["player"]["id"] for f in out["fallers"]})
        self.assertLessEqual(len(out["risers"]), 18)
        nets = [abs(m["net"]) for m in out["most_transferred"]]
        self.assertEqual(nets, sorted(nets, reverse=True))
        for m in out["most_transferred"]:
            self.assertEqual(m["net"], m["in"] - m["out"])


class SetPieceTests(unittest.TestCase):
    def test_every_club_lists_its_takers_in_order(self):
        out = scout.set_pieces(E, ROWS)
        self.assertEqual(len(out["teams"]), 20)
        self.assertEqual([t["team"] for t in out["teams"]], sorted(t["team"] for t in out["teams"]))
        for t in out["teams"]:
            self.assertEqual(len(t["penalties"]), 1)
            self.assertEqual(t["penalties"][0]["position"], 4)
            self.assertEqual(len(t["corners"]), 1)


class DefconTests(unittest.TestCase):
    def test_keepers_are_left_out_and_thresholds_follow_position(self):
        out = scout.defcon(E, ROWS)["players"]
        self.assertTrue(out)
        self.assertTrue(all(p["player"]["position"] != 1 for p in out))
        for p in out:
            self.assertEqual(p["threshold"], 10 if p["player"]["position"] == 2 else 12)
            self.assertTrue(0.0 <= p["hit_probability"] <= 100.0)
        probs = [p["hit_probability"] for p in out]
        self.assertEqual(probs, sorted(probs, reverse=True))


class LineupTests(unittest.TestCase):
    def test_every_club_names_a_legal_eleven_of_its_own_players(self):
        out = scout.predicted_lineups(E, ROWS)
        self.assertEqual(len(out["teams"]), 20)
        for t in out["teams"]:
            xi = t["xi"]
            self.assertEqual(len(xi), 11, t["team"])
            self.assertEqual(Counter(p["player"]["position"] for p in xi), Counter({1: 1, 2: 4, 3: 4, 4: 2}))
            self.assertTrue(all(p["player"]["team_short"] == t["team"] for p in xi))

    def test_first_choice_players_start(self):
        club1 = next(t for t in scout.predicted_lineups(E, ROWS)["teams"] if t["team"] == "C01")
        names = {p["player"]["web_name"] for p in club1["xi"]}
        self.assertIn("C01-G1", names)
        self.assertNotIn("C01-G2", names)


class CopilotTests(unittest.TestCase):
    def test_the_captain_answer_comes_from_your_own_squad(self):
        squad = fakes.legal_squad(ROWS)
        out = scout.copilot(E, ROWS, "Who should I captain?", {"squad_rows": squad}, 3)
        self.assertEqual(out["intent"], "captain")
        self.assertTrue(out["has_team"])
        best = max((r for r in squad if r["status"] == "a"), key=lambda r: r["per_gw"][0]["xpts"])
        self.assertIn(best["web_name"], out["answer"])
        self.assertEqual(out["table"]["rows"][0][0], best["web_name"])

    def test_without_a_team_the_captain_comes_from_everyone(self):
        out = scout.copilot(E, ROWS, "captain?", None, 3)
        self.assertFalse(out["has_team"])
        top = max((r for r in ROWS if r["status"] == "a"), key=lambda r: r["per_gw"][0]["xpts"])
        self.assertIn(top["web_name"], out["answer"])

    def test_the_bench_answer_starts_the_best_eleven(self):
        squad = fakes.legal_squad(ROWS)
        out = scout.copilot(E, ROWS, "Who do I start?", {"squad_rows": squad}, 3)
        self.assertEqual(out["intent"], "bench")
        self.assertTrue(out["answer"].startswith("Start this eleven in "))

    def test_a_vague_question_gets_the_overview_and_a_hint(self):
        out = scout.copilot(E, ROWS, "thoughts?", None, 3)
        self.assertEqual(out["intent"], "overview")
        self.assertIn(ROWS[0]["web_name"], out["answer"])
        self.assertTrue(out["points"])


if __name__ == "__main__":
    unittest.main()
