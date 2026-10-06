#!/usr/bin/env python3
"""Sanity-check expected-points projections.

Builds the projection engine exactly as the server does (Elo prior + recent
per-gameweek form) and reports:

  * overall level and correlation against FPL's own ``ep_next``
  * per-gameweek minutes and xPts for named players (``--players``)
  * mean absolute error against a reference CSV you trust (``--reference``)

Run from the repo root:

    ./.venv/bin/python scripts/calibrate.py
    ./.venv/bin/python scripts/calibrate.py --horizon 5 --players "Haaland:MCI,Saka:ARS"
    ./.venv/bin/python scripts/calibrate.py --reference ref.csv   # web_name,team,xpts[,mins]

Works offline with FPL_CACHE_ONLY=1 once the cache is primed.
Python 3.9-compatible, like the backend.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import fpl_api  # noqa: E402
import priors  # noqa: E402
import solver as solver_mod  # noqa: E402
import xpts  # noqa: E402


def build_engine() -> xpts.Engine:
    """Same construction as main.engine(): probe for the calendar, then priors."""
    bs, fx = fpl_api.bootstrap(), fpl_api.fixtures()
    probe = xpts.Engine(bs, fx)
    try:
        elo = priors.elo_strength(bs, priors.fetch_elo(bs, probe.current_gw))
    except Exception as exc:  # pragma: no cover - diagnostic path
        print("  ! Elo prior unavailable (%s); using league average" % exc)
        elo = {}
    try:
        live = priors.fetch_recent_live(probe.current_gw)
    except Exception as exc:  # pragma: no cover
        print("  ! recent form unavailable (%s)" % exc)
        live = {}
    engine = xpts.Engine(bs, fx, elo=elo, live_by_gw=live)
    solver_mod.configure(engine.rules)
    return engine


def corr(a: List[float], b: List[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


def first_minutes(row: Dict) -> float:
    legs = row["per_gw"][0]["fixtures"] if row["per_gw"] else []
    return legs[0]["xmins"] if legs else 0.0


def load_reference(path: str) -> Dict[Tuple[str, str], Tuple[float, Optional[float]]]:
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            key = (rec["web_name"].strip(), rec["team"].strip().upper())
            mins = rec.get("mins")
            out[key] = (float(rec["xpts"]), float(mins) if mins not in (None, "") else None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--horizon", type=int, default=1, help="gameweeks to project (default 1)")
    ap.add_argument("--min-minutes", type=int, default=270, help="regulars only (default 270)")
    ap.add_argument("--players", default="", help='spot checks, e.g. "Haaland:MCI,Saka:ARS"')
    ap.add_argument("--reference", default="", help="CSV with web_name,team,xpts[,mins]")
    args = ap.parse_args()

    engine = build_engine()
    rows = engine.all_players_horizon(engine.next_gw, max(1, args.horizon))
    by_key = {(r["web_name"], r["team_short"]): r for r in rows}

    print("Mug's Game FC — projection check")
    print("  GW%d next · %d players · Elo for %d clubs (k=%.5f) · form GWs %s"
          % (engine.next_gw, len(rows), sum(1 for v in engine.elo.values() if v),
             engine.elo_k, sorted(engine.live_by_gw.keys())))

    regulars = [r for r in rows if r["minutes"] >= args.min_minutes]
    mine = [r["xpts_next"] for r in regulars]
    fpl = [r["fpl_ep_next"] for r in regulars]
    if regulars:
        print("\nAgainst FPL's ep_next (%d players with ≥%d minutes)" % (len(regulars), args.min_minutes))
        print("  mean level   model %.2f · FPL %.2f · gap %+.2f"
              % (sum(mine) / len(mine), sum(fpl) / len(fpl), sum(mine) / len(mine) - sum(fpl) / len(fpl)))
        print("  correlation  %.3f   (0.5–0.75 is normal: ep_next is form-based)" % corr(mine, fpl))

    print("\nTop 10 for GW%d" % engine.next_gw)
    for r in sorted(rows, key=lambda r: -r["xpts_next"])[:10]:
        print("  %-16s %-4s £%4.1fm  %5.2f xPts  %3.0f′" % (r["web_name"], r["team_short"], r["price"],
                                                         r["xpts_next"], first_minutes(r)))

    if args.players:
        print("\nSpot checks (xPts / expected minutes per gameweek)")
        for item in [p.strip() for p in args.players.split(",") if p.strip()]:
            name, _, team = item.partition(":")
            r = by_key.get((name, team.upper()))
            if not r:
                print("  %-16s not found — use web_name:TEAM, e.g. Palmer:CHE" % item)
                continue
            weeks = []
            for g in r["per_gw"]:
                mins = g["fixtures"][0]["xmins"] if g["fixtures"] else 0
                weeks.append("GW%d %.2f/%.0f′" % (g["gw"], g["xpts"], mins) if g["fixtures"] else "GW%d blank" % g["gw"])
            print("  %-16s %s" % (item, " · ".join(weeks)))

    if args.reference:
        ref = load_reference(args.reference)
        dx, dm, missing = [], [], []
        for key, (rx, rm) in ref.items():
            r = by_key.get(key)
            if not r:
                missing.append("%s:%s" % key)
                continue
            dx.append(abs(r["xpts_next"] - rx))
            if rm is not None:
                dm.append(abs(first_minutes(r) - rm))
        print("\nAgainst %s (%d players)" % (os.path.basename(args.reference), len(dx)))
        if dx:
            print("  MAE xPts     %.2f" % (sum(dx) / len(dx)))
        if dm:
            print("  MAE minutes  %.1f" % (sum(dm) / len(dm)))
        if missing:
            print("  not matched  %s" % ", ".join(missing[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
