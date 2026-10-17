"""Every API route answers in the shape the frontend reads, with the network switched off.

The engine is built from the made-up league in `fakes.py` and handed to `main` directly,
FPL is cut off (`FPL_CACHE_ONLY`, an empty cache folder), and every team route runs on the
demo team (ID 0), which needs no FPL account. An unknown team must be a 404 with a readable
detail, never a 500.

Run:  ./.venv/bin/python tests/test_api.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fakes     # noqa: E402  (puts backend/ on the path)
import fpl_api   # noqa: E402

from fastapi.testclient import TestClient   # noqa: E402

import main      # noqa: E402

_CACHE = tempfile.TemporaryDirectory()
E = fakes.engine(with_elo=True)


def setUpModule():
    fpl_api.CACHE_ONLY = True                 # never touch the network
    fpl_api.CACHE_DIR = _CACHE.name           # and never read a developer's real cache
    main._engine.update(obj=E, built=time.time() + 10 ** 9)   # never rebuilt during the run
    main._rows_cache.clear()
    main.solver_mod.configure(E.rules)


def tearDownModule():
    _CACHE.cleanup()


client = TestClient(main.app)


def ok(path, **kw):
    r = client.get(path, **kw)
    assert r.status_code == 200, "%s -> %d %s" % (path, r.status_code, r.text[:300])
    return r.json()


def post(path, body):
    r = client.post(path, json=body)
    assert r.status_code == 200, "%s -> %d %s" % (path, r.status_code, r.text[:300])
    return r.json()


class PlatformTests(unittest.TestCase):
    def test_healthz_answers_without_building(self):
        self.assertEqual(ok("/healthz"), {"ok": True, "model_ready": True})

    def test_health_reports_the_calendar(self):
        h = ok("/api/health")
        self.assertEqual((h["current_gw"], h["next_gw"], h["players"]), (8, 9, 300))

    def test_api_answers_are_never_cached_by_the_browser(self):
        r = client.get("/api/meta")
        self.assertIn("no-store", r.headers["cache-control"])

    def test_the_page_is_served_with_a_build_id(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('name="app-build"', r.text)
        self.assertEqual(client.get("/version").json()["build"] in r.text, True)


class ReadRouteTests(unittest.TestCase):
    def test_meta(self):
        m = ok("/api/meta")
        self.assertEqual(m["next_gw"], 9)
        self.assertEqual(len(m["teams"]), 20)
        self.assertEqual(len(m["events"]), 38)
        self.assertEqual(m["rules"]["scoring"]["goal"]["GKP"], 10.0)

    @unittest.expectedFailure
    def test_meta_still_answers_when_the_elo_prior_is_missing(self):
        # KNOWN BUG: when FPL-Core-Insights can't be reached, engine() carries on with
        # elo={} (by design), but /api/meta then rounds each club's "elo": None and
        # returns a 500. Remove this decorator when that is fixed.
        main._engine.update(obj=fakes.engine(with_elo=False))
        try:
            ok("/api/meta")
        finally:
            main._engine.update(obj=E)

    def test_players_filter_sort_and_page(self):
        out = ok("/api/players", params={"position": 4, "max_price": 8.0, "limit": 5, "horizon": 3})
        self.assertLessEqual(len(out["players"]), 5)
        self.assertTrue(all(p["position"] == 4 and p["price"] <= 8.0 for p in out["players"]))
        totals = [p["xpts_total"] for p in out["players"]]
        self.assertEqual(totals, sorted(totals, reverse=True))
        page2 = ok("/api/players", params={"position": 4, "max_price": 8.0, "limit": 5, "offset": 5, "horizon": 3})
        self.assertEqual(page2["count"], out["count"])
        self.assertFalse({p["id"] for p in out["players"]} & {p["id"] for p in page2["players"]})

    def test_players_search_and_cheapest_first(self):
        out = ok("/api/players", params={"search": "c01-f", "sort": "price_asc"})
        self.assertEqual({p["web_name"] for p in out["players"]}, {"C01-F1", "C01-F2", "C01-F3"})
        prices = [p["price"] for p in out["players"]]
        self.assertEqual(prices, sorted(prices))

    def test_a_minutes_override_changes_the_projection(self):
        pid = ok("/api/players", params={"limit": 1})["players"][0]["id"]
        base = ok("/api/players", params={"search": "", "limit": 300})["players"]
        mine = ok("/api/players", params={"limit": 300, "overrides": "%d:0" % pid})["players"]
        before = next(p for p in base if p["id"] == pid)["xpts_total"]
        after = next(p for p in mine if p["id"] == pid)
        self.assertLess(after["xpts_total"], before)
        self.assertEqual(after["minutes_overridden"], 0.0)

    def test_one_player(self):
        p = ok("/api/player/1", params={"horizon": 2})
        self.assertEqual(p["id"], 1)
        self.assertEqual(len(p["per_gw"]), 2)
        self.assertIn("xmins", p["minutes_model"])
        self.assertIn("goals", p["season"])

    def test_an_unknown_player_is_a_404(self):
        r = client.get("/api/player/99999")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "Unknown player")

    def test_picks_compare_scout_lineups(self):
        self.assertEqual(len(ok("/api/picks", params={"horizon": 3})["captains"]), 8)
        c = ok("/api/compare", params={"a": 1, "b": 2, "horizon": 3})
        self.assertEqual((c["a"]["id"], c["b"]["id"]), (1, 2))
        s = ok("/api/scout", params={"horizon": 3})
        self.assertEqual(set(s), {"gw", "prices", "set_pieces", "defcon"})
        self.assertEqual(len(ok("/api/lineups")["teams"]), 20)


class TeamRouteTests(unittest.TestCase):
    def test_the_demo_team_loads_without_fpl(self):
        t = ok("/api/entry/0", params={"horizon": 3, "fresh": 1})
        self.assertTrue(t["entry"]["demo"])
        self.assertEqual(t["entry"]["name"], "Gut Feeling FC")
        self.assertEqual(len(t["squad"]), 15)
        self.assertEqual(len(t["starting_xi"]), 11)
        self.assertEqual(len(t["bench"]), 4)
        self.assertIn(t["captain"]["id"], {p["id"] for p in t["starting_xi"]})
        self.assertGreaterEqual(t["bank"], 0.0)

    def test_the_demo_history_runs_to_the_current_week(self):
        hist = ok("/api/entry/0")["history"]
        self.assertEqual([h["gw"] for h in hist], list(range(1, 9)))
        for h in hist:
            self.assertEqual(set(h), {"gw", "points", "rank", "transfers", "hits"})
            self.assertGreater(h["rank"], 0)

    def test_a_transfer_entered_by_hand_is_applied(self):
        t = ok("/api/entry/0")
        out = next(p for p in t["squad"] if p["position"] == 3)
        owned = {p["id"] for p in t["squad"]}
        cand = next(p for p in ok("/api/players", params={"position": 3, "sort": "price_asc", "limit": 300})["players"]
                    if p["id"] not in owned and p["status"] == "a")
        after = ok("/api/entry/0", params={"made": "%d-%d" % (out["id"], cand["id"])})
        ids = {p["id"] for p in after["squad"]}
        self.assertIn(cand["id"], ids)
        self.assertNotIn(out["id"], ids)
        self.assertTrue(after["pending_transfers"][0]["manual"])

    def test_an_unknown_team_is_a_readable_404(self):
        for path in ("/api/entry/987654321", "/api/rate/987654321", "/api/entry/987654321/leagues"):
            r = client.get(path)
            self.assertEqual(r.status_code, 404, path)
            self.assertIn("987654321", r.json()["detail"])

    def test_rate_the_demo_team(self):
        r = ok("/api/rate/0", params={"horizon": 3})
        self.assertIn(r["grade"], ("A+", "A", "B+", "B", "C+", "C", "D"))
        self.assertTrue(0 <= r["overall"] <= 100)

    def test_the_demo_team_is_in_no_leagues(self):
        out = ok("/api/entry/0/leagues")
        self.assertTrue(out["demo"])

    def test_solve_for_the_demo_team(self):
        out = post("/api/solve", {"team_id": 0, "horizon": 2, "paths": 2, "pool_size": 70})
        self.assertTrue(out["feasible"])
        self.assertTrue(out["paths"])
        self.assertEqual(out["paths"][0]["label"], "Path 1")
        totals = [p["total_xpts"] for p in out["paths"]]
        self.assertEqual(totals, sorted(totals, reverse=True), "Path 1 is always the best found")
        for plan in out["paths"]:
            self.assertEqual(len(plan["gameweeks"]), 2)

    def test_chips_for_the_demo_team(self):
        out = post("/api/chips", {"team_id": 0, "horizon": 3})
        self.assertEqual(len(out["baseline"]), 3)
        self.assertEqual(out["options"]["WC"], [], "the demo burnt its Wildcard in GW2")

    def test_copilot_with_and_without_a_team(self):
        a = post("/api/copilot", {"question": "Who should I captain?", "team_id": 0, "horizon": 3})
        self.assertTrue(a["has_team"])
        self.assertEqual(a["intent"], "captain")
        b = post("/api/copilot", {"question": "Who should I captain?", "team_id": 987654321, "horizon": 3})
        self.assertFalse(b["has_team"], "an unknown team falls back to the whole league")


class ParserTests(unittest.TestCase):
    def test_overrides_clamp_and_skip_junk(self):
        self.assertEqual(main.parse_overrides("12:70,328:0,5:200,7:-3,bad,9:x"),
                         {12: 70.0, 328: 0.0, 5: 90.0, 7: 0.0})
        self.assertEqual(main.parse_overrides(None), {})


if __name__ == "__main__":
    unittest.main()
