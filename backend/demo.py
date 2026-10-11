"""The demo team: a made-up manager for visitors who don't play FPL.

Team ID 0 never exists on FPL, so the app uses it for "Gut Feeling FC", a squad
picked on vibes: the most expensive names the budget allows, filled out with
whatever is left, and one injured star kept "for the badge". It is a legal
squad under this season's rules (squad size, positions, club limit, budget),
so every team view works on it, and its season so far is invented but steady:
a little under the average most weeks, a love of hits, a Wildcard burnt early
and a shocker in the last gameweek (so Home's roast has something to chew on).

The functions here take FPL-shaped data and return FPL-shaped data (the same
fields as /entry/{id}/, /entry/{id}/event/{gw}/picks/ and /entry/{id}/history/),
so `load_team` treats the demo exactly like a real manager. No network calls.
"""
from __future__ import annotations

from typing import Any, Dict, List

DEMO_ID = 0
NAME = "Gut Feeling FC"

# The order the vibes manager fills the squad: the glamour slots first, the keepers last.
SLOT_ORDER = [4, 3, 3, 4, 2, 3, 1, 2, 2, 3, 4, 2, 3, 2, 1]


def _vibes(p: Dict[str, Any]) -> tuple:
    """How a manager who picks on vibes ranks players: price first, then fame."""
    return (p["now_cost"], float(p.get("selected_by_percent") or 0), -p["id"])


def pick_squad(elements: List[Dict[str, Any]], quota: Dict[int, int], club_limit: int,
               budget: int, allowed: Any = None) -> List[Dict[str, Any]]:
    """A legal squad picked on vibes. `allowed`: ids the model can project (others skipped)."""
    pool = [p for p in elements
            if p.get("status") != "u" and (allowed is None or p["id"] in allowed)]
    by_pos: Dict[int, List[Dict[str, Any]]] = {}
    for p in sorted(pool, key=_vibes, reverse=True):
        by_pos.setdefault(p["element_type"], []).append(p)
    cheapest = {pos: sorted(p["now_cost"] for p in ps) for pos, ps in by_pos.items()}

    squad: List[Dict[str, Any]] = []
    need = dict(quota)
    clubs: Dict[int, int] = {}

    def reserve(after: Dict[int, int]) -> int:
        # the least the rest of the squad could cost, so the budget never runs dry
        return sum(sum(cheapest.get(pos, [0])[:n]) for pos, n in after.items())

    def take(p):
        squad.append(p)
        need[p["element_type"]] -= 1
        clubs[p["team"]] = clubs.get(p["team"], 0) + 1

    def fits(p, spent):
        if need.get(p["element_type"], 0) <= 0 or clubs.get(p["team"], 0) >= club_limit:
            return False
        if any(q["id"] == p["id"] for q in squad):
            return False
        after = dict(need)
        after[p["element_type"]] -= 1
        return spent + p["now_cost"] + reserve(after) <= budget

    # the injured star kept "for the badge": the priciest flagged player who fits
    flagged = sorted((p for p in pool if p.get("status") in ("i", "d", "s")), key=_vibes, reverse=True)
    for p in flagged:
        if fits(p, 0):
            take(p)
            break

    slots = list(SLOT_ORDER)
    for pos, n in quota.items():          # any position the rules ask for beyond the usual shape
        slots += [pos] * max(0, n - SLOT_ORDER.count(pos))
    for pos in slots:
        if need.get(pos, 0) <= 0:
            continue
        spent = sum(q["now_cost"] for q in squad)
        for p in by_pos.get(pos, []):
            if fits(p, spent):
                take(p)
                break
    return squad


def _wobble(gw: int) -> int:
    """A fixed, slightly-below-average swing for each gameweek (no randomness: same every load)."""
    return [-9, 3, -6, -12, 5, -4, -8, 1, -11, -3][gw % 10]


def history(events: List[Dict[str, Any]], current_gw: int) -> Dict[str, Any]:
    """An invented season up to `current_gw`, shaped like FPL's /entry/{id}/history/."""
    rows, total, rank = [], 0, 2400000
    for ev in sorted(events, key=lambda e: e["id"]):
        gw = ev["id"]
        if gw > current_gw:
            break
        avg = ev.get("average_entry_score") or 50
        hits = 4 if gw % 3 == 0 and gw > 1 else 0          # a hit every third week, without fail
        pts = max(8, avg + _wobble(gw) - hits)
        if gw == current_gw:
            pts = max(8, avg - 19)                          # and a shocker last week
        total += pts
        rank = int(rank * (1.0 + (avg - pts) / 160.0)) + 37
        rows.append({"event": gw, "points": pts, "total_points": total, "overall_rank": rank,
                     "event_transfers": 2 if hits else 1, "event_transfers_cost": hits,
                     "points_on_bench": 9 + gw % 5})
    chips = [{"name": "wildcard", "event": 2, "time": None}] if current_gw > 2 else []
    return {"current": rows, "chips": chips, "past": []}


def team(elements: List[Dict[str, Any]], events: List[Dict[str, Any]], current_gw: int,
         quota: Dict[int, int], club_limit: int, budget: int, allowed: Any = None) -> Dict[str, Any]:
    """The demo manager as FPL would answer for them: entry, picks and history."""
    squad = pick_squad(elements, quota, club_limit, budget, allowed)
    spent = sum(p["now_cost"] for p in squad)
    hist = history(events, current_gw)
    last = hist["current"][-1] if hist["current"] else {}
    entry = {
        "id": DEMO_ID, "name": NAME,
        "player_first_name": "Demo", "player_last_name": "Manager",
        "summary_overall_rank": last.get("overall_rank"),
        "summary_overall_points": last.get("total_points", 0),
        "summary_event_points": last.get("points"),
        "last_deadline_value": budget,
        "demo": True,
    }
    picks = {
        "picks": [{"element": p["id"], "purchase_price": p["now_cost"], "position": i + 1}
                  for i, p in enumerate(squad)],
        "entry_history": {"bank": budget - spent, "value": spent},
    }
    return {"entry": entry, "picks": picks, "history": hist}
