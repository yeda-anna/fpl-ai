"""Game rules are read from FPL's bootstrap-static, with sane fallbacks for older payloads.

Run:  ./.venv/bin/python tests/test_rules.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes   # noqa: E402  (puts backend/ on the path)
import rules   # noqa: E402


class ReadFromBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.R = rules.Rules(fakes.bootstrap())

    def test_scoring_comes_from_game_config(self):
        self.assertEqual(self.R.goal(1), 10.0)       # 2026/27: a goalkeeper's goal is worth 10
        self.assertEqual(self.R.goal(2), 6.0)
        self.assertEqual(self.R.goal(3), 5.0)
        self.assertEqual(self.R.goal(4), 4.0)
        self.assertEqual(self.R.clean_sheet(3), 1.0)
        self.assertEqual(self.R.conceded(2), -1.0)
        self.assertEqual(self.R.assist(), 3.0)
        self.assertEqual(self.R.yellow(), -1.0)

    def test_a_published_scoring_change_flows_through(self):
        bs = fakes.bootstrap()
        bs["game_config"]["scoring"]["goals_scored"]["MID"] = 7
        bs["game_config"]["scoring"]["assists"] = 4
        R = rules.Rules(bs)
        self.assertEqual(R.goal(3), 7.0)
        self.assertEqual(R.assist(), 4.0)

    def test_squad_limits_and_formation(self):
        R = self.R
        self.assertEqual((R.squad_size, R.xi_size, R.club_limit, R.budget), (15, 11, 3, 1000))
        self.assertEqual(R.max_free_transfers, 5)
        self.assertEqual(R.sell_on_fee, 0.5)
        self.assertEqual(R.quota, {1: 2, 2: 5, 3: 5, 4: 3})
        self.assertEqual(R.xi_min, {1: 1, 2: 3, 3: 2, 4: 1})
        self.assertEqual(R.xi_max, {1: 1, 2: 5, 3: 5, 4: 3})

    def test_to_dict_is_what_meta_publishes(self):
        d = self.R.to_dict()
        self.assertEqual(d["scoring"]["goal"]["GKP"], 10.0)
        self.assertEqual(d["budget"], 100.0)
        self.assertEqual(d["formation"]["DEF"], [3, 5])
        self.assertEqual(d["quota"]["FWD"], 3)
        self.assertEqual(len(d["chips"]), 8)


class FallbackTests(unittest.TestCase):
    def test_an_empty_payload_falls_back_to_the_documented_rules(self):
        R = rules.Rules({})
        self.assertEqual((R.squad_size, R.xi_size, R.club_limit, R.budget), (15, 11, 3, 1000))
        self.assertEqual(R.quota, {1: 2, 2: 5, 3: 5, 4: 3})
        self.assertEqual(R.xi_min[2], 3)
        self.assertEqual(R.goal(4), 4.0)
        self.assertEqual(R.chips, [])

    def test_a_null_scoring_value_keeps_the_fallback(self):
        bs = fakes.bootstrap()
        bs["game_config"]["scoring"]["assists"] = None
        self.assertEqual(rules.Rules(bs).assist(), 3.0)


class ChipWindowTests(unittest.TestCase):
    def setUp(self):
        self.R = rules.Rules(fakes.bootstrap())

    def test_every_chip_is_available_in_both_halves_when_unused(self):
        for chip in ("wildcard", "freehit", "bboost", "3xc"):
            self.assertTrue(self.R.chip_available(chip, 5, []))
            self.assertTrue(self.R.chip_available(chip, 30, []))

    def test_a_chip_played_in_the_first_half_is_gone_until_gw20(self):
        used = [{"name": "wildcard", "event": 2}]
        self.assertFalse(self.R.chip_available("wildcard", 9, used))
        self.assertTrue(self.R.chip_available("wildcard", 20, used))
        self.assertTrue(self.R.chip_available("freehit", 9, used))     # other chips are untouched

    def test_windows_left_start_from_the_given_week(self):
        left = self.R.chip_windows_left("bboost", 9, [])
        self.assertEqual(left, [{"start": 9, "stop": 19}, {"start": 20, "stop": 38}])
        used = [{"name": "bboost", "event": 4}]
        self.assertEqual(self.R.chip_windows_left("bboost", 9, used), [{"start": 20, "stop": 38}])

    def test_an_unknown_chip_is_never_available(self):
        self.assertFalse(self.R.chip_available("fourfold_captain", 9, []))


if __name__ == "__main__":
    unittest.main()
