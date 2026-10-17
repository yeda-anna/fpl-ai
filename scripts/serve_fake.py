#!/usr/bin/env python3
"""Serve the app on the made-up league in tests/fakes.py, with the network switched off.

For screenshots and UI checks where the real FPL API can't be reached (a cloud
sandbox, a train, CI): every view works on the demo team (ID 0, "Gut Feeling FC"),
names and numbers are test data (players are called C03-D4 and so on). Nothing is
read from or written to `.cache/`.

    ./.venv/bin/python scripts/serve_fake.py                    # http://127.0.0.1:8790
    ./.venv/bin/python scripts/serve_fake.py --port 8791 --repo ../fpl-ai-main
                                                                # another checkout (e.g. a worktree of main)

`--repo` serves a different checkout's backend and frontend, so "before" (main) and
"after" (a PR branch) can run side by side; that checkout needs tests/fakes.py.
Python 3.9-compatible, like the backend.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from typing import Any


def build(repo: str) -> Any:
    """The FastAPI app from `repo`, with its engine built from the fake league and FPL cut off."""
    for sub in ("backend", "tests"):
        path = os.path.join(repo, sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    if not os.path.isfile(os.path.join(repo, "tests", "fakes.py")):
        raise SystemExit("%s has no tests/fakes.py (it arrived in #17); copy it in from main." % repo)
    import fakes     # noqa: E402
    import fpl_api   # noqa: E402
    fpl_api.CACHE_ONLY = True                    # never touch the network
    fpl_api.CACHE_DIR = tempfile.mkdtemp()       # and never read or write the real cache
    import main      # noqa: E402
    e = fakes.engine(with_elo=True)              # with an Elo prior: /api/meta needs one today
    main._engine.update(obj=e, built=time.time() + 10 ** 9)    # never rebuilt
    main._rows_cache.clear()
    main.solver_mod.configure(e.rules)
    return main.app


def main_() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="checkout to serve (default: this one)")
    args = ap.parse_args()
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    app = build(os.path.abspath(args.repo))
    import uvicorn
    print("Fake league on http://%s:%d/ (demo team, test data)" % (args.host, args.port), flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main_()
