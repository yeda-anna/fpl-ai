"""A made-up 20-club Premier League, shaped like FPL's own payloads, for the unit tests.

Nothing here touches the network. `bootstrap()` and `fixtures()` look like FPL's
`bootstrap-static` and `fixtures` (only the fields the backend reads), so the real
`xpts.Engine`, solver, analysis and scout code run on them unchanged. Every value is
derived from the player's id, so the league is the same on every run.

    import fakes
    e = fakes.engine()                       # an xpts.Engine on the made-up league
    rows = e.all_players_horizon(e.next_gw, 3)
"""
from __future__ import annotations

import copy
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import xpts  # noqa: E402

N_CLUBS = 20
CURRENT_GW = 8                       # GW1-8 finished, GW9 is next
SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}     # a full FPL squad's worth of players at every club
BASE_COST = {1: 40, 2: 40, 3: 45, 4: 45}

SCORING = {
    "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
    "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
    "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
    "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
    "assists": 3, "saves": 1, "yellow_cards": -1, "bonus": 1, "long_play": 2, "short_play": 1,
}
CHIPS = [{"name": n, "start_event": s, "stop_event": e}
         for (s, e) in ((1, 19), (20, 38)) for n in ("wildcard", "freehit", "bboost", "3xc")]

# A few players with a flag, so availability rules have something to bite on.
DOUBTFUL = {33: 50, 97: 25}          # id -> chance of playing next round
INJURED = {48, 160}
UNAVAILABLE = {222}


def short(club: int) -> str:
    return "C%02d" % club


def _round_robin(n: int) -> List[List[tuple]]:
    """Circle method: n-1 rounds where every club plays once, then the same with venues swapped."""
    clubs = list(range(1, n + 1))
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = clubs[i], clubs[n - 1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        clubs = [clubs[0]] + [clubs[-1]] + clubs[1:-1]
    return rounds + [[(b, a) for (a, b) in rnd] for rnd in rounds]


def fixtures() -> List[Dict[str, Any]]:
    out, fid = [], 1
    for gw, rnd in enumerate(_round_robin(N_CLUBS), start=1):
        for h, a in rnd:
            done = gw <= CURRENT_GW
            out.append({"id": fid, "event": gw, "team_h": h, "team_a": a,
                        "finished": done, "finished_provisional": done,
                        "team_h_score": (h + gw) % 4 if done else None,
                        "team_a_score": (a + gw) % 3 if done else None,
                        "team_h_difficulty": 2 + (a % 4), "team_a_difficulty": 2 + (h % 4),
                        "kickoff_time": "2026-%02d-%02dT14:00:00Z" % (8 + gw // 5, 1 + (gw * 7) % 27)})
            fid += 1
    return out


def _player(pid: int, club: int, pos: int, k: int) -> Dict[str, Any]:
    starter = k < {1: 1, 2: 4, 3: 4, 4: 2}[pos]                 # first-choice players start
    strength = 1.0 + (N_CLUBS - club) / N_CLUBS                 # club 1 is the strongest
    cost = BASE_COST[pos] + ((club * 7 + k * 13) % (30 if pos <= 2 else 80))
    if pos == 1 and k == 1:
        cost = 40                                               # backup keepers cost 4.0m, as in FPL
    games = CURRENT_GW
    minutes = games * (88 if starter else 9)
    starts = games if starter else 0
    xg90 = {1: 0.0, 2: 0.05, 3: 0.22, 4: 0.42}[pos] * strength * (1.15 if k == 0 else 1.0)
    xa90 = {1: 0.01, 2: 0.07, 3: 0.18, 4: 0.12}[pos] * strength
    nineties = minutes / 90.0
    status, chance, news = "a", None, ""
    if pid in DOUBTFUL:
        status, chance, news = "d", DOUBTFUL[pid], "Knock - %d%% chance of playing" % DOUBTFUL[pid]
    elif pid in INJURED:
        status, chance, news = "i", 0, "Hamstring injury - expected back in a month"
    elif pid in UNAVAILABLE:
        status, chance, news = "u", 0, "Left the club"
    pct = ((pid * 37) % 200) - 100                              # price progress, -100..+99
    likelihood = 3 if pct > 80 else -3 if pct < -80 else 0
    return {
        "id": pid, "team": club, "team_code": club, "element_type": pos,
        "web_name": "%s-%s%d" % (short(club), "GDMF"[pos - 1], k + 1),
        "first_name": "First%d" % pid, "second_name": "Second%d" % pid,
        "now_cost": cost, "cost_change_event": 0, "cost_change_start": (pid % 5) - 2,
        "status": status, "chance_of_playing_next_round": chance, "news": news, "news_added": None,
        "minutes": minutes, "starts": starts,
        "expected_goals_per_90": "%.2f" % xg90, "expected_assists_per_90": "%.2f" % xa90,
        "expected_goals": "%.2f" % (xg90 * nineties), "expected_assists": "%.2f" % (xa90 * nineties),
        "expected_goals_conceded": "%.2f" % (games * 1.3 / strength),
        "goals_scored": int(round(xg90 * nineties)), "assists": int(round(xa90 * nineties)),
        "clean_sheets": games // 4 if pos <= 2 and starter else 0,
        "bonus": 3 if k == 0 else 0, "bps": int(18 * nineties + (pid % 7) * nineties),
        "saves_per_90": 3.1 if pos == 1 else 0, "yellow_cards": pid % 3,
        "defensive_contribution": int((9 if pos == 2 else 6 if pos == 3 else 0) * nineties),
        "defensive_contribution_per_90": 9.5 if pos == 2 else 6.0 if pos == 3 else 1.0,
        "tackles": pid % 11, "clearances_blocks_interceptions": pid % 17, "recoveries": pid % 23,
        "selected_by_percent": "%.1f" % ((pid * 7.3) % 60), "form": "%.1f" % ((pid % 9) * 0.8),
        "total_points": int(4 * nineties) if starter else 2, "points_per_game": "3.5",
        "ep_next": "%.1f" % (2.0 + (pid % 6) * 0.5), "ict_index": "40.0",
        "penalties_order": 1 if (pos == 4 and k == 0) else None,
        "direct_freekicks_order": 1 if (pos == 3 and k == 0) else None,
        "corners_and_indirect_freekicks_order": 1 if (pos == 3 and k == 1) else None,
        "price_change_percent": pct,
        "price_change_projections": [{"offset": d, "projected_percent": min(100, max(-100, pct + d * 10)),
                                      "likelihood": likelihood} for d in (0, 1, 2)],
        "price_change_hourly_rate": 0.5,
        "transfers_in_event": (pid * 311) % 50000, "transfers_out_event": (pid * 173) % 50000,
        "removed": False, "scout_risks": [],
    }


def elements() -> List[Dict[str, Any]]:
    out, pid = [], 1
    for club in range(1, N_CLUBS + 1):
        for pos, n in SHAPE.items():
            for k in range(n):
                out.append(_player(pid, club, pos, k))
                pid += 1
    return out


def events(current: int = CURRENT_GW) -> List[Dict[str, Any]]:
    return [{"id": g, "name": "Gameweek %d" % g, "deadline_time": "2026-%02d-%02dT10:00:00Z" % (8 + g // 5, 1 + (g * 7) % 27),
             "finished": g <= current, "is_current": g == current, "is_next": g == current + 1,
             "average_entry_score": 48 + g % 9 if g <= current else 0,
             "highest_score": 110 + g if g <= current else None,
             "chip_plays": [], "transfers_made": 1000 * g}
            for g in range(1, 39)]


def bootstrap() -> Dict[str, Any]:
    return {
        "teams": [{"id": c, "name": "Club %02d" % c, "short_name": short(c), "code": c,
                   "strength": 3} for c in range(1, N_CLUBS + 1)],
        "events": events(),
        "elements": elements(),
        "element_types": [{"id": 1, "singular_name_short": "GKP", "squad_select": 2, "squad_min_play": 1, "squad_max_play": 1},
                          {"id": 2, "singular_name_short": "DEF", "squad_select": 5, "squad_min_play": 3, "squad_max_play": 5},
                          {"id": 3, "singular_name_short": "MID", "squad_select": 5, "squad_min_play": 2, "squad_max_play": 5},
                          {"id": 4, "singular_name_short": "FWD", "squad_select": 3, "squad_min_play": 1, "squad_max_play": 3}],
        "chips": copy.deepcopy(CHIPS),
        "game_settings": {"squad_squadsize": 15, "squad_squadplay": 11, "squad_team_limit": 3,
                          "squad_total_spend": 1000, "max_extra_free_transfers": 4,
                          "transfers_sell_on_fee": 0.5, "sys_vice_captain_enabled": True},
        "game_config": {"scoring": copy.deepcopy(SCORING), "settings": {}, "status": {}},
        "total_players": 11000000,
    }


def elo() -> Dict[int, Dict[str, Any]]:
    """An Elo prior shaped like `priors.elo_strength`'s output: club 1 strongest."""
    return {c: {"elo": 1900.0 - 15.0 * c} for c in range(1, N_CLUBS + 1)}


def engine(with_elo: bool = False) -> "xpts.Engine":
    """A real Engine on the made-up league (no recent live data; Elo prior only if asked)."""
    return xpts.Engine(bootstrap(), fixtures(), elo=elo() if with_elo else None)


def by_id(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {r["id"]: r for r in rows}


def legal_squad(rows: List[Dict[str, Any]], budget: int = 1000) -> List[Dict[str, Any]]:
    """A legal fifteen from the cheapest players at different clubs: the 'any old squad' a test starts from."""
    need, clubs, out = dict(SHAPE), {}, []
    for r in sorted(rows, key=lambda r: (r["now_cost"], r["id"])):
        q = r["position"]
        if need[q] <= 0 or clubs.get(r["team"], 0) >= 3 or r["status"] != "a":
            continue
        out.append(r)
        need[q] -= 1
        clubs[r["team"]] = clubs.get(r["team"], 0) + 1
    assert sum(r["now_cost"] for r in out) <= budget and len(out) == 15
    return out
