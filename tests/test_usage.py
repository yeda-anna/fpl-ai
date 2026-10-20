"""Anonymous usage counts: visits, new vs returning, demo vs real, pages and features.

Run:  ./.venv/bin/python tests/test_usage.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import usage   # noqa: E402


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"STATS_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_visits_split_new_and_returning_and_by_team_mode(self):
        usage.record_visit(False, "team")
        usage.record_visit(True, "team")
        usage.record_visit(True, "demo")
        usage.record_visit(False, "nonsense")                     # an unknown mode counts as "none"
        t = usage.summary()["today"]
        self.assertEqual((t["visits"], t["new"], t["returning"]), (4, 2, 2))
        self.assertEqual(t["modes"], {"team": 2, "demo": 1, "none": 1})

    def test_only_the_apps_own_pages_are_counted(self):
        self.assertTrue(usage.record_view("matches/predictions"))
        usage.record_view("matches/predictions")
        self.assertFalse(usage.record_view("../../etc/passwd"))
        self.assertFalse(usage.record_view("home/1421260"))         # never a free-form string, so never an ID
        self.assertEqual(usage.summary()["today"]["views"], [{"name": "matches/predictions", "count": 2}])

    def test_features_by_route_template_only_when_they_answer(self):
        usage.record_route("POST", "/api/solve", 200)
        usage.record_route("GET", "/api/entry/{team_id}/swaps/{player_id}", 200)
        usage.record_route("GET", "/api/entry/{team_id}/swaps/{player_id}", 200)
        usage.record_route("GET", "/api/rate/{team_id}", 404)        # a failed call isn't use
        usage.record_route("GET", "/api/meta", 200)                  # not a feature
        usage.record_route("GET", None, 200)
        f = {x["name"]: x["count"] for x in usage.summary()["today"]["features"]}
        self.assertEqual(f, {"Swap ideas": 2, "Transfer plan": 1})

    def test_the_file_holds_counts_and_nothing_else(self):
        usage.record_visit(True, "team")
        usage.record_view("home/squad")
        usage.record_route("GET", "/api/entry/{team_id}", 200)
        raw = open(os.path.join(self.tmp.name, "usage.json")).read()
        day = list(json.loads(raw)["days"].values())[0]
        self.assertEqual(set(day), {"visits", "new", "returning", "modes", "views", "features"})
        self.assertNotIn("team_id", raw.replace("{team_id}", ""))

    def test_the_summary_covers_the_period_a_row_a_day(self):
        usage.record_visit(False, "none")
        s = usage.summary(14)
        self.assertEqual(len(s["days"]), 14)
        self.assertEqual(s["days"][-1]["visits"], 1)
        self.assertEqual(s["week"]["visits"], 1)
        self.assertTrue(s["persistent"])
        self.assertTrue(s["since"])

    def test_old_days_are_dropped(self):
        data = {"since": "2020-01-01", "days": {"2020-01-%02d" % i: {"visits": 1} for i in range(1, 32)}}
        with mock.patch.object(usage, "KEEP_DAYS", 10):
            usage._save(data)
        self.assertEqual(len(usage._load()["days"]), 10)

    def test_a_broken_file_starts_again(self):
        with open(os.path.join(self.tmp.name, "usage.json"), "w") as f:
            f.write("{not json")
        usage.record_visit(False, "team")
        self.assertEqual(usage.summary()["today"]["visits"], 1)

    def test_without_stats_dir_the_counts_are_not_persistent(self):
        with mock.patch.dict(os.environ, {"STATS_DIR": ""}):
            self.assertFalse(usage.persistent())


if __name__ == "__main__":
    unittest.main()
