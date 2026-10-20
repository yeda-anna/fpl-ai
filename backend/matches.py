"""Match predictions: for every fixture in a gameweek, who is likeliest to win and by how many goals.

The same goal expectations that drive the player projections (xpts.Engine.fixture_goals:
each side's attack against the other's defence, Elo strength, this season's xG, recent
form, home advantage) give each side a Poisson mean. From those two means the chance of
every scoreline follows, with Dixon-Coles' small correction so 0-0 and 1-1 are not
under-called (independent Poisson draws too few low-scoring draws). The three outcome
chances are sums over the scoreline table.

The *predicted score* is the most likely scoreline among the outcomes' favourite: pick the
likeliest of home win / draw / away win, then the likeliest scoreline inside it. That keeps
the headline coherent ("Arsenal to win, 2-1") rather than showing the single likeliest
scoreline, which is often a draw even when one side is clearly the favourite.

Pure functions; no network.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

MAX_GOALS = 8            # scorelines up to 8-8 are tabulated; the rest is rounding error
RHO = -0.08              # Dixon-Coles: > 0 would push draws down, < 0 lifts 0-0 and 1-1


def _pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _tau(i: int, j: int, lam_h: float, lam_a: float, rho: float) -> float:
    if i == 0 and j == 0:
        return 1.0 - lam_h * lam_a * rho
    if i == 0 and j == 1:
        return 1.0 + lam_h * rho
    if i == 1 and j == 0:
        return 1.0 + lam_a * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def scoreline_grid(lam_h: float, lam_a: float, rho: float = RHO, n: int = MAX_GOALS) -> List[List[float]]:
    """grid[i][j] = P(home scores i, away scores j), summing to 1."""
    g = [[_pmf(i, lam_h) * _pmf(j, lam_a) * max(0.0, _tau(i, j, lam_h, lam_a, rho)) for j in range(n + 1)]
         for i in range(n + 1)]
    total = sum(sum(row) for row in g)
    return [[c / total for c in row] for row in g]


def predict(lam_h: float, lam_a: float, rho: float = RHO) -> Dict[str, Any]:
    """The prediction for one match from the two sides' expected goals."""
    g = scoreline_grid(lam_h, lam_a, rho)
    n = len(g)
    p_home = sum(g[i][j] for i in range(n) for j in range(n) if i > j)
    p_draw = sum(g[i][i] for i in range(n))
    p_away = sum(g[i][j] for i in range(n) for j in range(n) if i < j)
    pick = max((("home", p_home), ("draw", p_draw), ("away", p_away)), key=lambda x: x[1])[0]

    def inside(i: int, j: int) -> bool:
        return (i > j) if pick == "home" else (i == j) if pick == "draw" else (i < j)
    best = max(((i, j) for i in range(n) for j in range(n) if inside(i, j)), key=lambda c: g[c[0]][c[1]])
    cells = sorted(((i, j) for i in range(n) for j in range(n)), key=lambda c: -g[c[0]][c[1]])[:6]
    return {
        "xg_home": round(lam_h, 2), "xg_away": round(lam_a, 2),
        "p_home": round(p_home, 4), "p_draw": round(p_draw, 4), "p_away": round(p_away, 4),
        "pick": pick,
        "score": [best[0], best[1]], "score_prob": round(g[best[0]][best[1]], 4),
        "top_scores": [{"home": i, "away": j, "p": round(g[i][j], 4)} for i, j in cells],
        "p_cs_home": round(sum(g[i][0] for i in range(n)), 4),       # the away side fails to score
        "p_cs_away": round(sum(g[0][j] for j in range(n)), 4),
        "p_over25": round(sum(g[i][j] for i in range(n) for j in range(n) if i + j >= 3), 4),
        "p_btts": round(sum(g[i][j] for i in range(1, n) for j in range(1, n)), 4),
    }


def gameweek(engine, gw: int) -> Dict[str, Any]:
    """Every fixture in a gameweek with its prediction, and a summary of the round."""
    out: List[Dict[str, Any]] = []
    for f in engine.fixtures_in(gw):
        h, a = f["team_h"], f["team_a"]
        lam_h, lam_a = engine.fixture_goals(h, a, True)
        m = predict(lam_h, lam_a)
        started = f.get("team_h_score") is not None and f.get("team_a_score") is not None
        m.update({
            "id": f.get("id"), "kickoff": f.get("kickoff_time"),
            "home": {"id": h, "name": engine.teams[h]["name"], "short": engine.teams[h]["short_name"]},
            "away": {"id": a, "name": engine.teams[a]["name"], "short": engine.teams[a]["short_name"]},
            "finished": bool(f.get("finished") or f.get("finished_provisional")),
            "actual": [f["team_h_score"], f["team_a_score"]] if started else None,
            "fdr_home": f.get("team_h_difficulty"), "fdr_away": f.get("team_a_difficulty"),
        })
        out.append(m)
    out.sort(key=lambda m: (m["kickoff"] or "", m["id"] or 0))
    return {"gw": gw, "matches": out, "summary": summarise(out)}


def summarise(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How the round looks: the predicted split, goals expected, the biggest favourite."""
    if not matches:
        return {"matches": 0}
    fav = max(matches, key=lambda m: max(m["p_home"], m["p_away"]))
    side = "home" if fav["p_home"] >= fav["p_away"] else "away"
    draw = max(matches, key=lambda m: m["p_draw"])
    return {
        "matches": len(matches),
        "home_wins": sum(1 for m in matches if m["pick"] == "home"),
        "draws": sum(1 for m in matches if m["pick"] == "draw"),
        "away_wins": sum(1 for m in matches if m["pick"] == "away"),
        "goals_per_match": round(sum(m["xg_home"] + m["xg_away"] for m in matches) / len(matches), 2),
        "biggest_favourite": {"team": fav[side]["name"], "short": fav[side]["short"],
                              "against": fav["away" if side == "home" else "home"]["short"],
                              "p": fav["p_" + side], "home": side == "home"},
        "likeliest_draw": {"home": draw["home"]["short"], "away": draw["away"]["short"], "p": draw["p_draw"]},
    }
