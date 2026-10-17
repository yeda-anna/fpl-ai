"""Fail if Procfile and railway.json start the app differently.

Railway deploys with `railway.json`'s `deploy.startCommand`; the Railpack CLI
that CI builds with (and Heroku-style hosts) read the `Procfile`'s `web:` line.
If the two drift, CI would test a different app from the one production runs.

    python3 scripts/check_start_command.py          # exit 0 if they match, 1 if not
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def procfile_web(text: str) -> Optional[str]:
    """The command on the Procfile's `web:` line, or None if there isn't one."""
    for line in text.splitlines():
        name, sep, cmd = line.partition(":")
        if sep and name.strip() == "web":
            return " ".join(cmd.split()) or None
    return None


def railway_start(config: dict) -> Optional[str]:
    """`deploy.startCommand` from a parsed railway.json, or None."""
    cmd = (config.get("deploy") or {}).get("startCommand")
    if not isinstance(cmd, str):
        return None
    return " ".join(cmd.split()) or None


def check(root: str = ROOT) -> Optional[str]:
    """None if the start commands match, otherwise a readable reason."""
    try:
        with open(os.path.join(root, "Procfile"), encoding="utf-8") as fh:
            proc = procfile_web(fh.read())
    except OSError as exc:
        return "can't read Procfile: %s" % exc
    try:
        with open(os.path.join(root, "railway.json"), encoding="utf-8") as fh:
            rail = railway_start(json.load(fh))
    except (OSError, ValueError) as exc:
        return "can't read railway.json: %s" % exc
    if proc is None:
        return "Procfile has no `web:` command"
    if rail is None:
        return "railway.json has no deploy.startCommand"
    if proc != rail:
        return ("start commands differ:\n  Procfile     web: %s\n  railway.json     %s"
                % (proc, rail))
    return None


def main() -> int:
    problem = check()
    if problem:
        print("FAIL " + problem, file=sys.stderr)
        return 1
    print("ok   Procfile and railway.json start the app the same way")
    return 0


if __name__ == "__main__":
    sys.exit(main())
