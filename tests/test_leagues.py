"""A manager's mini-leagues, on payloads shaped like FPL's own (`/entry/{id}/` and the standings pages).

Run:  ./.venv/bin/python tests/test_leagues.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import leagues   # noqa: E402

ME = 1421260


def row(entry, rank, total, gw, name=None):
    return {"entry": entry, "entry_name": name or "Team %d" % entry, "player_name": "Mgr %d" % entry,
            "rank": rank, "rank_sort": rank, "last_rank": rank, "total": total, "event_total": gw}


def page(rows, has_next=False):
    return {"standings": {"has_next": has_next, "page": 1, "results": rows}}


def league(lid, name, rank, last=None, kind="x", size=None, **kw):
    d = {"id": lid, "name": name, "league_type": kind, "entry_rank": rank, "entry_last_rank": last or rank,
         "rank_count": size, "closed": False, "has_cup": False}
    d.update(kw)
    return d


def entry(classic, h2h=None):
    return {"id": ME, "name": "Plain FC", "player_first_name": "Anna", "player_last_name": "Y",
            "leagues": {"classic": classic, "h2h": h2h or [], "cup": {}, "cup_matches": []}}


class FakeFPL:
    """Standings pages by (league, page); records what was asked for."""
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def __call__(self, league_id, page_no=1):
        self.asked.append((league_id, page_no))
        if (league_id, page_no) not in self.pages:
            raise RuntimeError("unreachable")
        return self.pages[(league_id, page_no)]


def pack(league_id, ranks, me_rank, me_total):
    """A page of 50 managers whose ranks are given, with me among them."""
    rows = []
    for r in ranks:
        rows.append(row(ME if r == me_rank else 9000 + r, r, me_total + (me_rank - r) * 3, 40 + r % 17))
    return rows


class PagingTests(unittest.TestCase):
    def test_page_of(self):
        self.assertEqual([leagues.page_of(r) for r in (None, 1, 50, 51, 100, 101, 2500)], [1, 1, 1, 2, 2, 3, 50])


class OverviewTests(unittest.TestCase):
    def test_kinds_and_movement(self):
        o = leagues.overview(league(1, "Office", 3, 5, size=12))
        self.assertEqual((o["kind"], o["movement"], o["size"]), ("private", 2, 12))
        self.assertEqual(leagues.overview(league(314, "Overall", 900000, 950000, kind="s", size=11500000,
                                                 entry_percentile_rank=8))["kind"], "system")
        self.assertEqual(leagues.overview(league(5, "H2H", 2), "h2h")["kind"], "h2h")
        self.assertIsNone(leagues.overview(league(1, "x", None))["movement"])


class StandingStatsTests(unittest.TestCase):
    def test_leader_gap_and_neighbours(self):
        rows = [row(1, 1, 500, 60, "Leaders"), row(2, 2, 480, 55), row(ME, 3, 470, 70), row(4, 4, 455, 31), row(5, 5, 400, 20)]
        s = leagues.standing_stats(ME, [page(rows, has_next=False)])
        self.assertEqual(s["leader"]["entry_name"], "Leaders")
        self.assertEqual((s["my_total"], s["my_gw"], s["gap_to_leader"]), (470, 70, 30))
        self.assertEqual((s["behind_next"], s["ahead_of_next"]), (10, 15))
        self.assertFalse(s["i_lead"])
        self.assertEqual(s["gw_best"]["event_total"], 70)               # my own week was the league's best
        self.assertEqual(s["gw_avg"], round((60 + 55 + 70 + 31 + 20) / 5.0, 1))
        self.assertFalse(s["more_pages"])

    def test_leading_has_no_one_above(self):
        s = leagues.standing_stats(ME, [page([row(ME, 1, 500, 60), row(2, 2, 480, 55)])])
        self.assertTrue(s["i_lead"])
        self.assertEqual((s["gap_to_leader"], s["behind_next"], s["ahead_of_next"]), (0, None, 20))

    def test_a_neighbour_on_an_unread_page_is_not_guessed(self):
        # I'm first on page 2 (rank 51); rank 50 is on page 1 but page 1 was read, so it counts;
        # with page 3 read instead, the manager above me (rank 100) is not the next rank up
        page1 = page([row(1, 1, 900, 50), row(50, 50, 500, 40)], has_next=True)
        page2 = page([row(ME, 51, 495, 44), row(52, 52, 490, 30)])
        s = leagues.standing_stats(ME, [page1, page2])
        self.assertEqual(s["behind_next"], 5)
        far = page([row(ME, 101, 300, 44), row(102, 102, 299, 30)])
        s = leagues.standing_stats(ME, [page1, far])
        self.assertIsNone(s["behind_next"])                            # rank 50 isn't rank 100
        self.assertEqual(s["ahead_of_next"], 1)
        self.assertEqual(s["gap_to_leader"], 600)
        self.assertTrue(s["more_pages"])

    def test_not_in_the_pages_read(self):
        s = leagues.standing_stats(ME, [page([row(1, 1, 900, 50), row(2, 2, 880, 40)], has_next=True)])
        self.assertEqual(s["leader"]["total"], 900)
        self.assertIsNone(s["my_total"]); self.assertIsNone(s["gap_to_leader"]); self.assertFalse(s["i_lead"])

    def test_empty_league(self):
        self.assertIsNone(leagues.standing_stats(ME, [page([])]))


class MyLeaguesTests(unittest.TestCase):
    def setUp(self):
        self.classic = [
            league(314, "Overall", 1200000, 1250000, kind="s", size=11500000, entry_percentile_rank=10),
            league(268323, "Friends", 3, 4, size=12),
            league(777, "Big Office", 120, 130, size=240),          # my rank 120 -> standings page 3
            league(888, "Work", 1, 1, size=9),
            league(999, "Broken", 5, 5, size=10),
        ]
        pages = {
            (268323, 1): page([row(1, 1, 500, 60, "Leaders"), row(2, 2, 480, 55), row(ME, 3, 470, 70), row(4, 4, 455, 31)]),
            (777, 1): page([row(9001, 1, 700, 50)] + [row(9100 + i, i + 2, 690 - i, 40) for i in range(49)], has_next=True),
            (777, 3): page(pack(777, range(101, 151), 120, 410), has_next=True),
            (888, 1): page([row(ME, 1, 610, 65), row(2, 2, 600, 40)]),
        }
        self.fpl = FakeFPL(pages)
        self.out = leagues.my_leagues(entry(self.classic, [league(55, "Head to head", 2, kind="x")]), ME, self.fpl)
        self.by = {x["id"]: x for x in self.out["leagues"]}

    def test_private_leagues_first_then_h2h_then_fpls_own(self):
        kinds = [x["kind"] for x in self.out["leagues"]]
        self.assertEqual(kinds, ["private"] * 4 + ["h2h", "system"])
        self.assertEqual(self.out["team"], "Plain FC")

    def test_each_private_league_is_read(self):
        f = self.by[268323]
        self.assertEqual((f["my_rank"], f["movement"], f["gap_to_leader"], f["behind_next"]), (3, 1, 30, 10))
        self.assertEqual(f["leader"]["entry_name"], "Leaders")

    def test_a_manager_on_page_three_is_found_on_page_three(self):
        big = self.by[777]
        self.assertIn((777, 3), self.fpl.asked)
        self.assertNotIn((777, 2), self.fpl.asked)                      # only the pages that matter
        self.assertEqual((big["my_rank"], big["my_total"], big["gap_to_leader"]), (120, 410, 290))
        self.assertEqual(big["size"], 240)

    def test_leading_and_summary(self):
        self.assertTrue(self.by[888]["i_lead"])
        s = self.out["summary"]
        self.assertEqual((s["private"], s["leading"], s["top3"]), (4, 1, 2))   # Friends 3rd, Work 1st; Broken 5th, Big Office 120th
        self.assertEqual((s["climbing"], s["falling"]), (2, 0))                 # Friends 4th to 3rd, Big Office 130th to 120th
        self.assertEqual(s["best"]["name"], "Work")

    def test_a_league_that_fails_to_load_keeps_what_the_profile_says(self):
        broken = self.by[999]
        self.assertTrue(broken["unavailable"])
        self.assertEqual(broken["my_rank"], 5)
        self.assertEqual(self.by[314]["percentile"], 10)

    def test_only_the_first_few_private_leagues_are_read_in_full(self):
        many = [league(2000 + i, "L%d" % i, 2, size=8) for i in range(20)]
        pages = {(2000 + i, 1): page([row(1, 1, 50, 5), row(ME, 2, 40, 4)]) for i in range(20)}
        fake = FakeFPL(pages)
        out = leagues.my_leagues(entry(many), ME, fake, max_detail=15)
        self.assertEqual(len(fake.asked), 15)
        self.assertEqual(out["summary"]["unread"], 5)
        self.assertEqual(len(out["leagues"]), 20)

    def test_no_leagues_at_all(self):
        out = leagues.my_leagues({"id": ME, "name": "New"}, ME, FakeFPL({}))
        self.assertEqual(out["leagues"], [])
        self.assertEqual(out["summary"]["private"], 0)
        self.assertEqual(leagues.empty(0, "Demo")["leagues"], [])

    def test_find_entry_row_reads_the_managers_page_only_when_needed(self):
        fake = FakeFPL({(777, 3): page(pack(777, range(101, 151), 120, 410))})
        first = page([row(9001, 1, 700, 50)], has_next=True)
        r = leagues.find_entry_row(ME, 120, first, fake, 777)
        self.assertEqual(r["total"], 410)
        self.assertEqual(fake.asked, [(777, 3)])
        on_first = leagues.find_entry_row(ME, 1, page([row(ME, 1, 5, 5)]), fake, 777)
        self.assertEqual(on_first["rank"], 1)
        self.assertEqual(len(fake.asked), 1)


if __name__ == "__main__":
    unittest.main()
