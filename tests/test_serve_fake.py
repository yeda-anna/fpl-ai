"""scripts/serve_fake.py serves the whole app on the made-up league, with FPL cut off.

It is what the `pr-screenshots` skill (and anyone without FPL access) runs to see a
branch in a browser, so it must keep working as the backend changes.

Run:  ./.venv/bin/python tests/test_serve_fake.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from fastapi.testclient import TestClient   # noqa: E402

_spec = importlib.util.spec_from_file_location("serve_fake", os.path.join(ROOT, "scripts", "serve_fake.py"))
serve_fake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(serve_fake)


class ServeFakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(serve_fake.build(ROOT))

    def test_the_network_is_off_and_the_real_cache_untouched(self):
        import fpl_api
        self.assertTrue(fpl_api.CACHE_ONLY)
        self.assertNotEqual(os.path.abspath(fpl_api.CACHE_DIR), os.path.join(ROOT, ".cache"))

    def test_the_model_is_ready_at_once(self):
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True, "model_ready": True})

    def test_the_page_and_the_views_it_reads_answer(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="landDemo"', page.text)          # the screenshots start from the demo button
        for path in ("/api/meta", "/api/entry/0", "/api/picks", "/api/players?limit=5", "/api/lineups"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_the_demo_team_is_the_made_up_one(self):
        t = self.client.get("/api/entry/0").json()
        self.assertEqual(t["entry"]["name"], "Gut Feeling FC")
        self.assertEqual(len(t["squad"]), 15)

    def test_a_checkout_without_the_fake_league_is_refused_clearly(self):
        with self.assertRaises(SystemExit) as cm:
            serve_fake.build(os.path.join(ROOT, "docs"))
        self.assertIn("tests/fakes.py", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
