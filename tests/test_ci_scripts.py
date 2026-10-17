"""The CI gate's own scripts: the start-command check and the smoke test.

scripts/check_start_command.py is tested on its parsing and on real files in a
temp folder; scripts/smoke.sh is run against a tiny local HTTP server that
plays a healthy app and then each kind of broken one. No network beyond
127.0.0.1; the smoke tests skip if bash or curl isn't installed.

Run:  ./.venv/bin/python tests/test_ci_scripts.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_start_command as csc   # noqa: E402

SMOKE = os.path.join(ROOT, "scripts", "smoke.sh")
CMD = "uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"


class StartCommandParsingTests(unittest.TestCase):
    def test_procfile_web_line(self):
        self.assertEqual(csc.procfile_web("web: %s\n" % CMD), CMD)
        self.assertEqual(csc.procfile_web("worker: x\nweb:   uvicorn  a:b \n"), "uvicorn a:b")

    def test_procfile_without_web(self):
        self.assertIsNone(csc.procfile_web("worker: python job.py\n"))
        self.assertIsNone(csc.procfile_web(""))
        self.assertIsNone(csc.procfile_web("web:\n"))

    def test_railway_start(self):
        self.assertEqual(csc.railway_start({"deploy": {"startCommand": CMD}}), CMD)
        self.assertIsNone(csc.railway_start({}))
        self.assertIsNone(csc.railway_start({"deploy": {}}))
        self.assertIsNone(csc.railway_start({"deploy": {"startCommand": 5}}))


class StartCommandFilesTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, procfile=None, railway=None):
        if procfile is not None:
            with open(os.path.join(self.dir, "Procfile"), "w") as fh:
                fh.write(procfile)
        if railway is not None:
            with open(os.path.join(self.dir, "railway.json"), "w") as fh:
                fh.write(railway if isinstance(railway, str) else json.dumps(railway))

    def test_repo_files_match(self):
        self.assertIsNone(csc.check(ROOT))

    def test_matching_files(self):
        self.write("web: %s\n" % CMD, {"deploy": {"startCommand": CMD}})
        self.assertIsNone(csc.check(self.dir))

    def test_whitespace_differences_are_ignored(self):
        self.write("web:  %s \n" % CMD.replace(" ", "  "), {"deploy": {"startCommand": CMD}})
        self.assertIsNone(csc.check(self.dir))

    def test_mismatch_is_reported(self):
        self.write("web: uvicorn main:ap --app-dir backend\n", {"deploy": {"startCommand": CMD}})
        self.assertIn("differ", csc.check(self.dir))

    def test_missing_pieces_are_reported(self):
        self.assertIn("Procfile", csc.check(self.dir))
        self.write("web: %s\n" % CMD, "{not json")
        self.assertIn("railway.json", csc.check(self.dir))
        self.write(railway={"build": {}})
        self.assertIn("startCommand", csc.check(self.dir))
        self.write("worker: x\n", {"deploy": {"startCommand": CMD}})
        self.assertIn("web:", csc.check(self.dir))


# --- smoke.sh ------------------------------------------------------------------

BUILD = "abc123def456"
PAGE = ('<!doctype html><html><head><meta name="app-build" content="%s">\n'
        '<link rel="stylesheet" href="/static/styles.css?v=0123456789ab"></head>'
        '<body><script src="/static/app.js?v=ba9876543210"></script></body></html>' % BUILD)


def healthy() -> Dict[str, Tuple[int, str]]:
    return {
        "/healthz": (200, '{"ok":true,"model_ready":false}'),
        "/": (200, PAGE),
        "/version": (200, '{"build":"%s"}' % BUILD),
        "/static/styles.css?v=0123456789ab": (200, "body{}"),
        "/api/entry/999999999": (404, '{"detail":"No FPL team with ID 999999999."}'),
    }


class FakeApp:
    """A local HTTP server answering from a {path: (status, body)} table."""

    def __init__(self, routes: Dict[str, Tuple[int, str]], booting: int = 0):
        table = routes
        left = [booting]            # /healthz answers 503 this many times first

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/healthz" and left[0] > 0:
                    left[0] -= 1
                    status, body = 503, "starting"
                else:
                    status, body = table.get(self.path, (404, '{"detail":"Not Found"}'))
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@unittest.skipUnless(shutil.which("bash") and shutil.which("curl"), "needs bash and curl")
class SmokeScriptTests(unittest.TestCase):
    def run_smoke(self, routes, *args, url=None, booting=0, timeout="0"):
        app = FakeApp(routes, booting)
        self.addCleanup(app.close)
        # SMOKE_TIMEOUT=0: a single /healthz try, so failure cases don't wait
        env = dict(os.environ, SMOKE_TIMEOUT=timeout, SMOKE_INTERVAL="0.2")
        return subprocess.run(["bash", SMOKE, url or app.url] + list(args), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=60)

    def assertFailsWith(self, proc, text):
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(text, proc.stderr)

    def test_healthy_app_passes(self):
        proc = self.run_smoke(healthy())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("all checks passed", proc.stdout)
        self.assertNotIn("999999999", proc.stdout)      # the live check is opt-in

    def test_waits_for_a_booting_server(self):
        proc = self.run_smoke(healthy(), booting=2, timeout="30")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("/healthz → 200", proc.stdout)

    def test_trailing_slash_in_base_url(self):
        app = FakeApp(healthy())
        self.addCleanup(app.close)
        proc = subprocess.run(["bash", SMOKE, app.url + "/"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_live_unknown_team_404_passes(self):
        proc = self.run_smoke(healthy(), "--live")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("/api/entry/999999999 → 404", proc.stdout)

    def test_live_unknown_team_500_fails(self):
        routes = healthy()
        routes["/api/entry/999999999"] = (500, "Internal Server Error")
        self.assertFailsWith(self.run_smoke(routes, "--live"), "expected 404")

    def test_unhealthy_fails_after_timeout(self):
        routes = healthy()
        routes["/healthz"] = (503, '{"ok":false}')
        self.assertFailsWith(self.run_smoke(routes), "/healthz did not answer")

    def test_health_not_ok_fails(self):
        routes = healthy()
        routes["/healthz"] = (200, '{"ok":false}')
        self.assertFailsWith(self.run_smoke(routes), "/healthz did not answer")

    def test_nothing_listening_fails(self):
        app = FakeApp({})
        url = app.url
        app.close()                                        # the port is now closed
        self.assertFailsWith(self.run_smoke({}, url=url), "/healthz did not answer")

    def test_page_error_fails(self):
        routes = healthy()
        routes["/"] = (500, "boom")
        self.assertFailsWith(self.run_smoke(routes), "/ → 500")

    def test_page_without_build_id_fails(self):
        routes = healthy()
        routes["/"] = (200, PAGE.replace('<meta name="app-build" content="%s">' % BUILD, ""))
        self.assertFailsWith(self.run_smoke(routes), "app-build")

    def test_version_mismatch_fails(self):
        routes = healthy()
        routes["/version"] = (200, '{"build":"000000000000"}')
        self.assertFailsWith(self.run_smoke(routes), "!= page build")

    def test_missing_asset_fails(self):
        routes = healthy()
        del routes["/static/styles.css?v=0123456789ab"]
        self.assertFailsWith(self.run_smoke(routes), "/static/styles.css?v=0123456789ab → 404")

    def test_page_without_hashed_assets_fails(self):
        routes = healthy()
        routes["/"] = (200, PAGE.replace("?v=0123456789ab", "").replace("?v=ba9876543210", ""))
        self.assertFailsWith(self.run_smoke(routes), "content-hashed")

    def test_bad_arguments(self):
        proc = subprocess.run(["bash", SMOKE], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=10)
        self.assertEqual(proc.returncode, 2)
        proc = subprocess.run(["bash", SMOKE, "http://127.0.0.1:1", "--nope"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=10)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
