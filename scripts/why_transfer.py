#!/usr/bin/env python3
"""Why does the plan make one transfer and not another? Compare swaps on a real team.

    ./.venv/bin/python scripts/why_transfer.py --team 1421260 \\
        --swap "Rudoni>Doku" --swap "Calafiori>Gabriel" --horizon 5
    ./.venv/bin/python scripts/why_transfer.py --fake --team 0 --swap "<out>><in>"   # the made-up league

For each swap it prints the rules that could block it (same position, money, three a
club, fit to play, in the solver's candidate pool), each player's expected points,
minutes and fixtures week by week, the raw gain (the sum of xPts, as a one-for-one
comparison card shows it) and the *plan* gain: what the swap adds to the score the
solver maximises (best eleven each week, captain, 12% of the bench, later weeks
discounted). Then it runs the solver once and prints the first week's transfers.

Players are named by FPL web name (case-insensitive) or by ID. Reads FPL through the
app's own cache (`.cache/`), so the same rules and projections as the live app apply.
Python 3.9-compatible.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ.setdefault("LOG_LEVEL", "WARNING")

import analysis      # noqa: E402
import main          # noqa: E402
import solver        # noqa: E402

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def use_fake() -> None:
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import fakes  # noqa: E402
    import fpl_api  # noqa: E402
    import tempfile
    fpl_api.CACHE_ONLY = True
    fpl_api.CACHE_DIR = tempfile.mkdtemp()
    e = fakes.engine(with_elo=True)
    main._engine.update(obj=e, built=time.time() + 10 ** 9)
    main._rows_cache.clear()
    solver.configure(e.rules)


def find(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    key = key.strip()
    if key.isdigit():
        hit = [r for r in rows if r["id"] == int(key)]
    else:
        hit = [r for r in rows if r["web_name"].lower() == key.lower()]
        if not hit:
            hit = [r for r in rows if key.lower() in r["web_name"].lower()]
    if len(hit) != 1:
        names = ", ".join("%s (%s, id %d)" % (r["web_name"], r["team_short"], r["id"]) for r in hit[:8])
        sys.exit("'%s' matches %d players%s" % (key, len(hit), (": " + names) if names else ""))
    return hit[0]


def plan_value(squad: List[Dict[str, Any]], weeks: int) -> float:
    """The solver's objective for a fixed squad: best XI + captain + vice/bench shares, decayed."""
    total = 0.0
    for t in range(weeks):
        s = analysis.squad_split(squad, t)
        pts = lambda r: r["per_gw"][t]["xpts"] if r["per_gw"] else 0.0  # noqa: E731
        xi = sorted(s["xi"], key=pts, reverse=True)
        vice = pts(xi[1]) if len(xi) > 1 else 0.0
        total += solver.DECAY ** t * (s["xi_xpts"] + s["captain_xpts"] + solver.VICE_WEIGHT * vice
                                      + solver.BENCH_WEIGHT * s["bench_xpts"])
    return total


def player_lines(r: Dict[str, Any], e) -> List[str]:
    p = e.players[r["id"]]
    out = ["  %-14s %s %s £%.1fm  status %s  chance %s%%  form %s  %s" % (
        r["web_name"], POS[r["position"]], r["team_short"], r["price"], r.get("status"),
        r.get("chance_next"), r.get("form"), ("news: " + r["news"]) if r.get("news") else "")]
    for t, g in enumerate(r["per_gw"]):
        mm = e.minutes_model(p, None, t)
        legs = ", ".join("%s(%s) fdr%s %.1f" % (f["opponent_short"], "H" if f["home"] else "A", f.get("fdr"), f["xpts"])
                         for f in g["fixtures"]) or "blank"
        out.append("     GW%-3d %5.2f xPts  %4.0f′ start %3.0f%%  %s" % (g["gw"], g["xpts"], mm["xmins"], 100 * mm["p_start"], legs))
    rates = e.player_rates(p)
    out.append("     total %.1f over %d GWs · xG90 %.2f xA90 %.2f · season %d min, %s starts" % (
        r["xpts_total"], len(r["per_gw"]), rates.get("xg90", 0), rates.get("xa90", 0), p.get("minutes", 0), p.get("starts")))
    return out


def main_() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--team", type=int, required=True)
    ap.add_argument("--swap", action="append", default=[], help='"OUT>IN" by web name or ID; repeatable')
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--fake", action="store_true", help="the made-up league in tests/fakes.py, no network")
    ap.add_argument("--no-solve", action="store_true", help="skip running the solver")
    args = ap.parse_args()
    if args.fake:
        use_fake()

    ctx = main.load_team(args.team, args.horizon)
    e, rows, squad = ctx["engine"], ctx["rows"], ctx["squad_rows"]
    owned = {r["id"] for r in squad}
    clubs: Dict[str, int] = {}
    for r in squad:
        clubs[r["team_short"]] = clubs.get(r["team_short"], 0) + 1
    print("Team %d · GW%d–%d · bank £%.1fm · %d free transfer(s)" % (
        args.team, e.next_gw, e.next_gw + args.horizon - 1, ctx["bank"], ctx["free_transfers"]))
    if ctx["pending_transfers"]:
        print("Transfers already made for GW%d: %s" % (e.next_gw, ", ".join(
            "%s → %s" % (main._name(e, t.get("element_out")), main._name(e, t.get("element_in"))) for t in ctx["pending_transfers"])))
    print("Clubs: " + ", ".join("%s %d%s" % (c, n, " (full)" if n >= solver.MAX_PER_CLUB else "") for c, n in sorted(clubs.items(), key=lambda x: -x[1])))
    split = analysis.squad_split(squad, 0)
    print("GW%d best XI (%s): %s" % (e.next_gw, split["formation"], ", ".join(r["web_name"] for r in split["xi"])))
    print("Bench: %s" % ", ".join(r["web_name"] for r in split["bench"]))
    base = plan_value(squad, args.horizon)
    pool = {r["id"] for r in solver.build_pool(rows, list(owned))}
    sale_of = {p["id"]: p.get("purchase_price") for p in ctx["current_squad"]}

    for raw in args.swap:
        if ">" not in raw:
            sys.exit('--swap takes "OUT>IN"')
        a, b = raw.split(">", 1)
        out, inn = find(rows, a), find(rows, b)
        print("\n=== %s → %s ===" % (out["web_name"], inn["web_name"]))
        checks: List[Tuple[str, bool, str]] = []
        checks.append(("you own %s" % out["web_name"], out["id"] in owned, ""))
        checks.append(("you don't already own %s" % inn["web_name"], inn["id"] not in owned, ""))
        checks.append(("same position", out["position"] == inn["position"], "%s vs %s" % (POS[out["position"]], POS[inn["position"]])))
        sells = solver.selling_price(out["now_cost"], sale_of.get(out["id"]))
        money = sells + int(round(ctx["bank"] * 10))
        checks.append(("money", inn["now_cost"] <= money, "sells £%.1fm + bank £%.1fm = £%.1fm vs £%.1fm%s" % (
            sells / 10.0, ctx["bank"], money / 10.0, inn["price"],
            "" if sale_of.get(out["id"]) is not None else " (bought-at price not public: sold at today's price)")))
        n_club = sum(1 for r in squad if r["team"] == inn["team"] and r["id"] != out["id"])
        checks.append(("three a club", n_club < solver.MAX_PER_CLUB, "%d from %s after selling" % (n_club, inn["team_short"])))
        checks.append(("fit to play (≥%d%%)" % solver.MIN_CHANCE, (inn.get("chance_next") if inn.get("chance_next") is not None else 100) >= solver.MIN_CHANCE,
                       "chance %s%%" % inn.get("chance_next")))
        checks.append(("in the solver's candidate pool", inn["id"] in pool, ""))
        for name, ok, why in checks:
            print("  [%s] %s%s" % ("ok" if ok else "NO", name, ("  — " + why) if why else ""))
        for r in (out, inn):
            print("\n".join(player_lines(r, e)))
        raw_gain = inn["xpts_total"] - out["xpts_total"]
        after = [inn if r["id"] == out["id"] else r for r in squad]
        gain = plan_value(after, args.horizon) - base
        hit = 0 if ctx["free_transfers"] > 0 else solver.HIT_COST
        in_xi = sum(1 for t in range(args.horizon) if out["id"] in {x["id"] for x in analysis.squad_split(squad, t)["xi"]})
        print("  raw gain (sum of xPts): %+.1f · plan gain (what the solver scores): %+.1f%s · %s starts %d of %d weeks in your best XI" % (
            raw_gain, gain, (" − %d hit" % hit) if hit else "", out["web_name"], in_xi, args.horizon))

    if args.no_solve:
        return
    plan = solver.solve(rows, ctx["current_squad"], ctx["bank"], ctx["free_transfers"], args.horizon,
                        max_hits=1, pool_size=160, time_limit=40)
    if not plan["feasible"]:
        print("\nSolver: no feasible plan (%s)" % plan["status"])
        return
    print("\nSolver plan (%s), first weeks:" % plan["status"])
    for g in plan["gameweeks"][:3]:
        moves = ", ".join("%s → %s" % (o["web_name"], i["web_name"]) for o, i in zip(g["transfers_out"], g["transfers_in"])) or "no transfer"
        print("  GW%d: %s · %d FT · hits %d · captain %s · %.1f xPts" % (g["gw"], moves, g["free_transfers"], g["hits"], g["captain"]["web_name"], g["xpts"]))
    if plan.get("passed_over"):
        print("  passed over on fitness: " + ", ".join("%s (%s%%)" % (p["web_name"], p["chance_next"]) for p in plan["passed_over"]))


if __name__ == "__main__":
    main_()
