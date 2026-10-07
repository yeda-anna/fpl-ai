"""Free-transfer replay: the numbers a manager sees must match FPL's own.

Run:  ./.venv/bin/python tests/test_free_transfers.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import main            # noqa: E402
import rules           # noqa: E402

MAX_FT = 5


def hist(transfers, chips=None):
    """transfers: transfers made in GW1, GW2, ...  chips: {gw: 'wildcard'}"""
    return {"current": [{"event": i + 1, "event_transfers": n} for i, n in enumerate(transfers)],
            "chips": [{"name": name, "event": gw} for gw, name in (chips or {}).items()]}


def replay(transfers, chips=None, gw=None):
    return main.replay_free_transfers(hist(transfers, chips), gw or len(transfers), MAX_FT)


class RollTests(unittest.TestCase):
    def test_normal_week_spends_then_gains_one(self):
        self.assertEqual(rules.roll_free_transfers(2, 1, False, MAX_FT), 2)
        self.assertEqual(rules.roll_free_transfers(1, 1, False, MAX_FT), 1)
        self.assertEqual(rules.roll_free_transfers(3, 0, False, MAX_FT), 4)

    def test_hits_do_not_go_negative(self):
        self.assertEqual(rules.roll_free_transfers(1, 4, False, MAX_FT), 1)

    def test_bank_is_capped(self):
        self.assertEqual(rules.roll_free_transfers(5, 0, False, MAX_FT), 5)

    def test_chip_week_keeps_the_bank_and_adds_nothing(self):
        self.assertEqual(rules.roll_free_transfers(1, 11, True, MAX_FT), 1)
        self.assertEqual(rules.roll_free_transfers(3, 15, True, MAX_FT), 3)
        self.assertEqual(rules.roll_free_transfers(5, 0, True, MAX_FT), 5)


class ReplayTests(unittest.TestCase):
    def test_after_gw1_you_have_one(self):
        self.assertEqual(replay([0]), 1)

    def test_one_transfer_every_week_stays_at_one(self):
        self.assertEqual(replay([0, 1, 1, 1, 1, 1, 1]), 1)

    def test_a_skipped_week_banks_one(self):
        self.assertEqual(replay([0, 1, 0, 1, 1]), 2)
        self.assertEqual(replay([0, 0, 0]), 3)

    def test_hits_reset_to_one(self):
        self.assertEqual(replay([0, 1, 3, 1]), 1)

    def test_wildcard_week_adds_no_extra_transfer(self):
        # One transfer a week, then a wildcard in GW7: still just the one FT for GW8.
        # (The old replay gave 2 here - the bug a manager with 1 FT reported.)
        self.assertEqual(replay([0, 1, 1, 1, 1, 1, 15], chips={7: "wildcard"}), 1)

    def test_free_hit_week_adds_no_extra_transfer(self):
        self.assertEqual(replay([0, 1, 1, 1, 1, 1, 14], chips={7: "freehit"}), 1)

    def test_banked_transfers_survive_a_chip(self):
        # 2 FT going into GW5, wildcard in GW5, still 2 for GW6.
        self.assertEqual(replay([0, 1, 1, 0, 15], chips={5: "wildcard"}), 2)
        # 3 FT going into GW5, free hit in GW5, still 3 for GW6.
        self.assertEqual(replay([0, 1, 0, 0, 12], chips={5: "freehit"}), 3)

    def test_other_chips_behave_like_a_normal_week(self):
        self.assertEqual(replay([0, 1, 1, 0], chips={4: "bboost"}), 2)
        self.assertEqual(replay([0, 1, 1, 0], chips={4: "3xc"}), 2)

    def test_cap(self):
        self.assertEqual(replay([0] * 12), MAX_FT)

    def test_history_newer_than_the_calendar_is_ignored(self):
        # FPL's calendar (cached) still says GW6 is current although the history already
        # has a GW7 row; the squad on screen is GW6's, so the count is for GW7.
        self.assertEqual(replay([0, 1, 1, 1, 1, 0, 0], gw=6), 2)

    def test_empty_history_still_gives_one(self):
        self.assertEqual(main.replay_free_transfers({}, 1, MAX_FT), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
