"""Transfers made since the last deadline must show in the squad straight away.

Run:  ./.venv/bin/python tests/test_pending_transfers.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import main            # noqa: E402

SQUAD = [{"id": i, "purchase_price": 50} for i in range(1, 16)]


def t(out_id, in_id, event, out_cost=50, in_cost=60, time="2026-10-09T10:00:00Z"):
    return {"element_out": out_id, "element_in": in_id, "event": event,
            "element_out_cost": out_cost, "element_in_cost": in_cost, "time": time}


class PendingTests(unittest.TestCase):
    def test_transfer_for_next_gw_replaces_the_player_in_his_slot(self):
        squad, bank, applied = main.apply_pending_transfers(SQUAD, 1.5, [t(4, 99, 9)], 8)
        self.assertEqual([p["id"] for p in squad][3], 99)
        self.assertNotIn(4, [p["id"] for p in squad])
        self.assertEqual(squad[3]["purchase_price"], 60)
        self.assertEqual(bank, 0.5)               # sold for 5.0, bought for 6.0
        self.assertEqual(len(applied), 1)

    def test_transfers_already_in_the_picks_are_ignored(self):
        squad, bank, applied = main.apply_pending_transfers(SQUAD, 1.5, [t(4, 99, 8), t(5, 98, 7)], 8)
        self.assertEqual(squad, SQUAD)
        self.assertEqual((bank, applied), (1.5, []))

    def test_chained_transfers_apply_in_order(self):
        tr = [t(99, 77, 9, time="2026-10-09T11:00:00Z"), t(4, 99, 9, time="2026-10-09T10:00:00Z")]
        squad, _, applied = main.apply_pending_transfers(SQUAD, 1.0, tr, 8)
        self.assertEqual(squad[3]["id"], 77)
        self.assertEqual(len(applied), 2)

    def test_the_input_squad_is_not_changed(self):
        before = [dict(p) for p in SQUAD]
        main.apply_pending_transfers(SQUAD, 1.0, [t(4, 99, 9)], 8)
        self.assertEqual(SQUAD, before)


class FakeEngine:
    players = {4: {"element_type": 4, "now_cost": 78}, 99: {"element_type": 4, "now_cost": 60},
               98: {"element_type": 3, "now_cost": 55}}


class MadeTests(unittest.TestCase):
    """Transfers the manager enters by hand: FPL hides them until the deadline."""

    def test_parse_made(self):
        self.assertEqual(main.parse_made("417-306, 12-99,bad,1-x,"), [(417, 306), (12, 99)])
        self.assertEqual(main.parse_made(None), [])

    def test_a_made_transfer_swaps_the_player_and_moves_the_bank(self):
        squad = [dict(p) for p in SQUAD]
        squad[3]["purchase_price"] = 74                 # bought at 7.4, now 7.8: sells for 7.6
        made = main.made_transfers(FakeEngine(), squad, [(4, 99)], 8)
        self.assertEqual(made[0]["event"], 9)
        self.assertEqual(made[0]["element_out_cost"], 76)
        new, bank, applied = main.apply_pending_transfers(squad, 0.5, made, 8)
        self.assertEqual(new[3]["id"], 99)
        self.assertEqual(bank, 2.1)                     # 0.5 + 7.6 - 6.0
        self.assertTrue(applied[0]["manual"])

    def test_a_swap_across_positions_or_unknown_player_is_ignored(self):
        self.assertEqual(main.made_transfers(FakeEngine(), SQUAD, [(4, 98), (4, 12345)], 8), [])

    def test_once_the_picks_carry_it_the_made_transfer_drops_out(self):
        after = [dict(p) for p in SQUAD]
        after[3] = {"id": 99, "purchase_price": 60}     # the deadline passed: 4 is gone, 99 is in
        made = main.made_transfers(FakeEngine(), after, [(4, 99)], 9)
        new, bank, applied = main.apply_pending_transfers(after, 1.0, made, 9)
        self.assertEqual((new, bank, applied), (after, 1.0, []))


if __name__ == "__main__":
    unittest.main()
