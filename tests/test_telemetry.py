"""Structured logs: one JSON line per event, request lines by route template, FPL failures visible.

Run:  ./.venv/bin/python tests/test_telemetry.py
"""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import httpx                                   # noqa: E402
from fastapi import FastAPI, HTTPException     # noqa: E402
from fastapi.testclient import TestClient      # noqa: E402

import fpl_api     # noqa: E402
import telemetry   # noqa: E402

TEAM_ID = 4242317


class Captured(unittest.TestCase):
    """Each test gets a fresh JSON handler writing into a buffer."""

    def setUp(self):
        self.buf = io.StringIO()
        telemetry.setup(self.buf)
        logging.getLogger("papa").setLevel(logging.DEBUG)

    def lines(self):
        out = []
        for raw in self.buf.getvalue().splitlines():
            out.append(json.loads(raw))    # every line must be valid JSON on its own
        return out

    def events(self, name):
        return [l for l in self.lines() if l.get("event") == name]


class TestFormatter(Captured):
    def test_one_line_json_with_fields(self):
        log = telemetry.get_logger("unit")
        telemetry.event(log, "unit.thing", ms=12, feasible=True)
        (line,) = self.lines()
        self.assertEqual(line["message"], "unit.thing")
        self.assertEqual(line["event"], "unit.thing")
        self.assertEqual(line["level"], "info")
        self.assertEqual(line["logger"], "papa.unit")
        self.assertEqual(line["ms"], 12)
        self.assertIs(line["feasible"], True)
        self.assertTrue(line["time"].endswith("Z"))

    def test_levels_use_railway_names(self):
        log = telemetry.get_logger("unit")
        telemetry.event(log, "w", logging.WARNING)
        telemetry.event(log, "e", logging.ERROR)
        telemetry.event(log, "c", logging.CRITICAL)
        self.assertEqual([l["level"] for l in self.lines()], ["warn", "error", "error"])

    def test_traceback_stays_on_one_line(self):
        log = telemetry.get_logger("unit")
        try:
            raise ValueError("boom")
        except ValueError:
            telemetry.event(log, "unit.failed", logging.ERROR, exc_info=True)
        self.assertEqual(len(self.buf.getvalue().strip().splitlines()), 1)
        (line,) = self.lines()
        self.assertEqual(line["error"], "ValueError")
        self.assertIn("boom", line["traceback"])

    def test_below_level_is_dropped(self):
        logging.getLogger("papa").setLevel(logging.INFO)
        telemetry.event(telemetry.get_logger("unit"), "quiet", logging.DEBUG)
        self.assertEqual(self.lines(), [])

    def test_uvicorn_goes_through_the_same_handler(self):
        logging.getLogger("uvicorn.error").info("Started server process\n",
                                                extra={"color_message": "\x1b[36mStarted\x1b[0m"})
        (line,) = self.lines()
        self.assertEqual(line["logger"], "uvicorn.error")
        self.assertEqual(line["message"], "Started server process")
        self.assertNotIn("color_message", line)
        self.assertTrue(logging.getLogger("uvicorn.access").disabled)


def make_app():
    app = FastAPI()
    telemetry.instrument(app)

    @app.get("/api/entry/{team_id}")
    def entry(team_id: int):
        if team_id == 0:
            raise HTTPException(404, "Team not found")
        return {"id": team_id}

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("kaput")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


class TestRequestLog(Captured):
    def setUp(self):
        super().setUp()
        self.client = TestClient(make_app(), raise_server_exceptions=False)

    def test_route_template_not_the_team_id(self):
        self.assertEqual(self.client.get("/api/entry/%d" % TEAM_ID).status_code, 200)
        (line,) = self.events("http.request")
        self.assertEqual(line["route"], "/api/entry/{team_id}")
        self.assertEqual(line["method"], "GET")
        self.assertEqual(line["status"], 200)
        self.assertIsInstance(line["ms"], int)
        self.assertEqual(line["level"], "info")
        self.assertNotIn(str(TEAM_ID), self.buf.getvalue())

    def test_404_is_info_not_error(self):
        self.assertEqual(self.client.get("/api/entry/0").status_code, 404)
        (line,) = self.events("http.request")
        self.assertEqual((line["status"], line["level"]), (404, "info"))

    def test_unmatched_path_has_no_route(self):
        self.assertEqual(self.client.get("/nope/%d" % TEAM_ID).status_code, 404)
        (line,) = self.events("http.request")
        self.assertIsNone(line["route"])
        self.assertNotIn(str(TEAM_ID), self.buf.getvalue())

    def test_unhandled_error_logged_as_500(self):
        self.assertEqual(self.client.get("/api/boom").status_code, 500)
        (line,) = self.events("http.request")
        self.assertEqual((line["status"], line["level"], line["error"]), (500, "error", "RuntimeError"))

    def test_healthz_is_debug(self):
        self.client.get("/healthz")
        (line,) = self.events("http.request")
        self.assertEqual(line["level"], "debug")


class FakeClient:
    """Stands in for httpx.Client: answers with `response` or raises `exc`."""
    response = None
    exc = None

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        if FakeClient.exc is not None:
            raise FakeClient.exc
        return FakeClient.response


class TestFplFetchLog(Captured):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.saved = (fpl_api.CACHE_DIR, fpl_api.CACHE_ONLY, fpl_api.httpx.Client)
        fpl_api.CACHE_DIR, fpl_api.CACHE_ONLY = self.tmp, False
        fpl_api.httpx.Client = FakeClient
        FakeClient.response, FakeClient.exc = None, None

    def tearDown(self):
        fpl_api.CACHE_DIR, fpl_api.CACHE_ONLY, fpl_api.httpx.Client = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def entry(self):
        return fpl_api.get("/entry/%d/" % TEAM_ID, "entry-%d" % TEAM_ID, "entry")

    def test_successful_fetch(self):
        req = httpx.Request("GET", "https://example.test/")
        FakeClient.response = httpx.Response(200, json={"id": TEAM_ID}, request=req)
        self.assertEqual(self.entry(), {"id": TEAM_ID})
        (line,) = self.events("fpl.fetch")
        self.assertEqual((line["endpoint"], line["status"], line["level"]), ("entry", 200, "info"))
        self.assertNotIn(str(TEAM_ID), self.buf.getvalue())

    def test_outage_with_stale_copy_is_a_warning(self):
        fpl_api._write_cache("entry-%d" % TEAM_ID, {"id": TEAM_ID})
        os.utime(fpl_api._cache_path("entry-%d" % TEAM_ID), (0, 0))       # expired
        FakeClient.exc = httpx.ConnectTimeout("timed out")
        self.assertEqual(self.entry(), {"id": TEAM_ID})
        (line,) = self.events("fpl.fetch_failed")
        self.assertEqual(line["level"], "warn")
        self.assertIs(line["served_stale"], True)
        self.assertEqual(line["error"], "ConnectTimeout")
        self.assertNotIn(str(TEAM_ID), self.buf.getvalue())

    def test_outage_without_copy_is_an_error(self):
        FakeClient.exc = httpx.ConnectError("down")
        with self.assertRaises(httpx.ConnectError):
            self.entry()
        (line,) = self.events("fpl.fetch_failed")
        self.assertEqual((line["level"], line["served_stale"]), ("error", False))

    def test_unknown_team_404_is_info(self):
        req = httpx.Request("GET", "https://example.test/")
        FakeClient.response = httpx.Response(404, request=req)
        with self.assertRaises(httpx.HTTPStatusError):
            self.entry()
        (line,) = self.events("fpl.fetch_failed")
        self.assertEqual((line["level"], line["status"]), ("info", 404))


def player(pid, pos, team, xp):
    return {"id": pid, "web_name": "R%d" % pid, "team": team, "team_short": "T%d" % team, "position": pos,
            "now_cost": 50, "price": 5.0, "status": "a", "selected_by_percent": 5.0, "chance_next": 100,
            "xpts_total": xp * 3, "per_gw": [{"gw": g, "xpts": xp, "fixtures": []} for g in (6, 7, 8)]}


class TestSolverLog(Captured):
    def test_a_solve_logs_time_status_and_feasible(self):
        import solver
        rows, owned, pid = [], [], 1
        for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
            for _ in range(n):
                rows.append(player(pid, pos, 1 + pid % 10, 2.0))
                owned.append({"id": pid, "purchase_price": 50})
                pid += 1
        plan = solver.solve(rows, owned, 2.0, 1, 3, max_hits=0)
        self.assertTrue(plan["feasible"])
        (line,) = self.events("solver.solved")
        self.assertIs(line["feasible"], True)
        self.assertEqual(line["status"], plan["status"])
        self.assertEqual((line["horizon"], line["level"]), (3, "info"))
        self.assertIsInstance(line["ms"], int)
        self.assertIs(line["alternative"], False)


if __name__ == "__main__":
    unittest.main()
