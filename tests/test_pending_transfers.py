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


if __name__ == "__main__":
    unittest.main()
