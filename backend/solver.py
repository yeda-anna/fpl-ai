"""Multi-gameweek transfer optimiser.

A mixed-integer program (CBC via PuLP) that plans the next N gameweeks at once,
the way fplcopilot.com's Solver does: it decides the squad, the starting eleven,
the captain and the transfers in every gameweek simultaneously, trading points
now against points later and paying -4 hits only when they pay for themselves.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pulp

SQUAD_SIZE = 15
XI_SIZE = 11
POS_QUOTA = {1: 2, 2: 5, 3: 5, 4: 3}          # GK, DEF, MID, FWD in the 15
XI_MIN = {1: 1, 2: 3, 3: 2, 4: 1}
XI_MAX = {1: 1, 2: 5, 3: 5, 4: 3}
MAX_PER_CLUB = 3
HIT_COST = 4.0
MAX_FREE_TRANSFERS = 5                         # 2025/26 rules: bank up to 5
BENCH_WEIGHT = 0.12                            # bench points are worth something
VICE_WEIGHT = 0.04                             # the vice only plays if the captain blanks
DECAY = 0.87                                   # a point next week beats a point in GW+5


SELL_ON_FEE = 0.5


def configure(rules) -> None:
    """Adopt the squad, formation and transfer limits FPL publishes."""
    global SQUAD_SIZE, XI_SIZE, POS_QUOTA, XI_MIN, XI_MAX, MAX_PER_CLUB, MAX_FREE_TRANSFERS, SELL_ON_FEE
    SQUAD_SIZE = rules.squad_size
    XI_SIZE = rules.xi_size
    POS_QUOTA = dict(rules.quota)
    XI_MIN = dict(rules.xi_min)
    XI_MAX = dict(rules.xi_max)
    MAX_PER_CLUB = rules.club_limit
    MAX_FREE_TRANSFERS = rules.max_free_transfers
    SELL_ON_FEE = rules.sell_on_fee


def selling_price(now_cost: int, purchase_price: Optional[int]) -> int:
    """Sell at purchase price plus the rise less FPL's sell-on fee, rounded down."""
    if purchase_price is None:
        return now_cost
    if now_cost <= purchase_price:
        return now_cost
    return purchase_price + int((now_cost - purchase_price) * (1.0 - SELL_ON_FEE))


def build_pool(rows: List[Dict[str, Any]], current_ids: List[int], pool_size: int = 160):
    """Trim the 600+ players to a tractable candidate set.

    CBC would grind on the full league, so keep the highest-projecting players in
    each position plus everyone already owned - an optimum is never outside that set
    in practice.
    """
    by_pos = {1: [], 2: [], 3: [], 4: []}
    for r in rows:
        if r["status"] in ("u", "n"):
            continue
        by_pos[r["position"]].append(r)
    keep = {}
    caps = {1: max(12, pool_size // 8), 2: pool_size // 3,
            3: pool_size // 3, 4: pool_size // 5}
    for pos, lst in by_pos.items():
        lst.sort(key=lambda r: -r["xpts_total"])
        for r in lst[:caps[pos]]:
            keep[r["id"]] = r
    index = {r["id"]: r for r in rows}
    for pid in current_ids:
        if pid in index:
            keep[pid] = index[pid]
    return list(keep.values())


def solve(rows: List[Dict[str, Any]],
          current_squad: List[Dict[str, Any]],
          bank: float,
          free_transfers: int,
          horizon: int,
          max_hits: int = 2,
          wildcard_gw: Optional[int] = None,
          free_hit_gw: Optional[int] = None,
          pool_size: int = 160,
          time_limit: int = 25,
          forbid: Optional[List[List[Any]]] = None,
          gap: float = 0.005) -> Dict[str, Any]:
    """Return an optimal transfer plan.

    current_squad: [{"id": int, "purchase_price": int}, ...] - may be empty, in which
    case this becomes a "build me a squad from scratch" (wildcard) problem.
    """
    owned = {p["id"]: p for p in current_squad}
    pool = build_pool(rows, list(owned.keys()), pool_size)
    index = {r["id"]: r for r in pool}
    ids = list(index.keys())

    gws = [rows[0]["per_gw"][t]["gw"] for t in range(horizon)] if rows else []
    T = list(range(horizon))

    xp = {}
    for pid in ids:
        per_gw = {g["gw"]: g["xpts"] for g in index[pid]["per_gw"]}
        for t in T:
            xp[(pid, t)] = per_gw.get(gws[t], 0.0)

    buy = {pid: index[pid]["now_cost"] for pid in ids}
    sell = {pid: selling_price(index[pid]["now_cost"],
                               owned[pid].get("purchase_price") if pid in owned else None)
            for pid in ids}
    pos = {pid: index[pid]["position"] for pid in ids}
    club = {pid: index[pid]["team"] for pid in ids}
    clubs = sorted(set(club.values()))

    prob = pulp.LpProblem("fpl_multi_gw", pulp.LpMaximize)

    squad = pulp.LpVariable.dicts("squad", (ids, T), cat="Binary")
    lineup = pulp.LpVariable.dicts("xi", (ids, T), cat="Binary")
    capt = pulp.LpVariable.dicts("cap", (ids, T), cat="Binary")
    vice = pulp.LpVariable.dicts("vice", (ids, T), cat="Binary")
    tin = pulp.LpVariable.dicts("in", (ids, T), cat="Binary")
    tout = pulp.LpVariable.dicts("out", (ids, T), cat="Binary")
    hits = pulp.LpVariable.dicts("hits", T, lowBound=0, upBound=max_hits, cat="Integer")
    ft = pulp.LpVariable.dicts("ft", T, lowBound=1, upBound=MAX_FREE_TRANSFERS, cat="Integer")
    bank_v = pulp.LpVariable.dicts("bank", T, lowBound=0, cat="Continuous")

    start_bank = int(round(bank * 10))
    have_squad = len(owned) == SQUAD_SIZE

    for t in T:
        gw = gws[t]
        free_squad = (wildcard_gw == gw) or (free_hit_gw == gw) or (not have_squad and t == 0)

        prob += pulp.lpSum(squad[p][t] for p in ids) == SQUAD_SIZE
        for q, n in POS_QUOTA.items():
            prob += pulp.lpSum(squad[p][t] for p in ids if pos[p] == q) == n
        for c in clubs:
            prob += pulp.lpSum(squad[p][t] for p in ids if club[p] == c) <= MAX_PER_CLUB

        prob += pulp.lpSum(lineup[p][t] for p in ids) == XI_SIZE
        for q in (1, 2, 3, 4):
            members = [lineup[p][t] for p in ids if pos[p] == q]
            prob += pulp.lpSum(members) >= XI_MIN[q]
            prob += pulp.lpSum(members) <= XI_MAX[q]
        for p in ids:
            prob += lineup[p][t] <= squad[p][t]
            prob += capt[p][t] <= lineup[p][t]
            prob += vice[p][t] <= lineup[p][t]
            prob += capt[p][t] + vice[p][t] <= 1      # captain and vice are different players
        prob += pulp.lpSum(capt[p][t] for p in ids) == 1
        prob += pulp.lpSum(vice[p][t] for p in ids) == 1

        # squad continuity
        for p in ids:
            prev = (squad[p][t - 1] if t > 0
                    else (1 if p in owned else 0))
            prob += squad[p][t] == prev + tin[p][t] - tout[p][t]
            prob += tin[p][t] + tout[p][t] <= 1

        made = pulp.lpSum(tin[p][t] for p in ids)

        if free_squad:
            prob += hits[t] == 0                      # chip week: transfers are free
        else:
            prob += hits[t] >= made - ft[t]

        # free transfer roll-over: ft_next = min(5, ft_now - made + 1)
        if t == 0:
            prob += ft[t] == min(MAX_FREE_TRANSFERS, max(1, free_transfers))
        else:
            prev_made = pulp.lpSum(tin[p][t - 1] for p in ids)
            built_from_scratch = (not have_squad and t - 1 == 0)
            if (wildcard_gw == gws[t - 1]) or (free_hit_gw == gws[t - 1]) or built_from_scratch:
                # chips - and picking a squad from nothing - don't spend free transfers
                prob += ft[t] <= ft[t - 1] + 1
            else:
                prob += ft[t] <= ft[t - 1] - prev_made + 1

        # budget
        spend = pulp.lpSum(buy[p] * tin[p][t] for p in ids)
        raise_ = pulp.lpSum(sell[p] * tout[p][t] for p in ids)
        prev_bank = bank_v[t - 1] if t > 0 else start_bank
        prob += bank_v[t] == prev_bank + raise_ - spend

    objective = []
    for t in T:
        d = DECAY ** t
        objective.append(d * pulp.lpSum(xp[(p, t)] * lineup[p][t] for p in ids))
        objective.append(d * pulp.lpSum(xp[(p, t)] * capt[p][t] for p in ids))
        objective.append(d * VICE_WEIGHT * pulp.lpSum(xp[(p, t)] * vice[p][t] for p in ids))
        objective.append(d * BENCH_WEIGHT * pulp.lpSum(
            xp[(p, t)] * (squad[p][t] - lineup[p][t]) for p in ids))
        objective.append(-d * HIT_COST * hits[t])
    prob += pulp.lpSum(objective)

    # No-good cuts: each forbidden plan is ruled out so the solver must find a
    # genuinely different route rather than returning the same answer again.
    for banned in (forbid or []):
        terms = [tin[p][t] for p, t in banned if p in index and t in T]
        if terms:
            prob += pulp.lpSum(terms) <= len(terms) - 1

    # Stop once the plan is provably within GAP of the best possible. Projections
    # carry far more uncertainty than 0.5%, so proving the last sliver is wasted time.
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit, gapRel=gap))

    def val(v):
        return int(round(v.value() or 0))

    plan = []
    for t in T:
        ins = [index[p] for p in ids if val(tin[p][t]) == 1]
        outs = [index[p] for p in ids if val(tout[p][t]) == 1]
        xi = [index[p] for p in ids if val(lineup[p][t]) == 1]
        sq = [index[p] for p in ids if val(squad[p][t]) == 1]
        cap_id = next((p for p in ids if val(capt[p][t]) == 1), None)
        vice_id = next((p for p in ids if val(vice[p][t]) == 1), None)
        bench = [r for r in sq if r["id"] not in {x["id"] for x in xi}]
        xi.sort(key=lambda r: (r["position"], -xp[(r["id"], t)]))
        # FPL benches the reserve keeper separately, then three outfielders in order
        bench.sort(key=lambda r: (r["position"] != 1, -xp[(r["id"], t)]))

        def light(r, t=t):
            week = next((g for g in r["per_gw"] if g["gw"] == gws[t]), None)
            legs = week["fixtures"] if week else []
            opp = ", ".join("%s (%s)" % (f["opponent_short"], "H" if f["home"] else "A")
                            for f in legs) or "Blank"
            return {"id": r["id"], "web_name": r["web_name"], "team_short": r["team_short"],
                    "team": r["team"], "position": r["position"], "price": r["price"],
                    "selected_by_percent": r.get("selected_by_percent", 0.0),
                    "opp": opp, "xpts": round(xp[(r["id"], t)], 2)}

        xi_pts = sum(xp[(r["id"], t)] for r in xi)
        cap_pts = xp[(cap_id, t)] if cap_id else 0.0
        n_hits = val(hits[t])
        plan.append({
            "gw": gws[t],
            "transfers_in": [light(r) for r in ins],
            "transfers_out": [light(r) for r in outs],
            "hits": n_hits,
            "hit_cost": n_hits * HIT_COST,
            "free_transfers": val(ft[t]),
            "bank": round(val(bank_v[t]) / 10.0, 1),
            "captain": light(index[cap_id]) if cap_id else None,
            "vice_captain": light(index[vice_id]) if vice_id else None,
            "starting_xi": [light(r) for r in xi],
            "bench": [light(r) for r in bench],
            "chip": ("Wildcard" if wildcard_gw == gws[t]
                     else "Free Hit" if free_hit_gw == gws[t] else None),
            "xpts": round(xi_pts + cap_pts - n_hits * HIT_COST, 2),
            "xpts_before_hits": round(xi_pts + cap_pts, 2),
        })

    # sol_status > 0 means CBC holds a genuine integer-feasible plan (optimal, or the
    # best found before the time limit). Anything else and the variables are junk.
    feasible = getattr(prob, "sol_status", 1) > 0 and pulp.LpStatus[status] != "Infeasible"
    signature = [(p, t) for t in T for p in ids if val(tin[p][t]) == 1]

    return {
        "signature": signature,
        "feasible": feasible,
        "status": pulp.LpStatus[status],
        "horizon": horizon,
        "total_xpts": round(sum(g["xpts"] for g in plan), 2),
        "total_hits": sum(g["hits"] for g in plan),
        "pool_size": len(ids),
        "gameweeks": plan,
    }
