"""A manager's mini-leagues: every league they belong to, and where they stand in each.

FPL lists a manager's leagues on their public profile (`/entry/{id}/`, `leagues`):
classic leagues (private ones you join with a code, plus FPL's own - Overall, a
gameweek league, a country, a club) and head-to-head leagues. Each carries the
manager's rank. For the private classic leagues we also read the standings page
that holds them (50 managers a page), which gives the leader, the gap to the
leader, the neighbours either side, and how the league scored this week.

Pure functions: the standings fetcher is passed in, so this runs (and is tested)
without a network. Nothing here is a model - it is arithmetic on FPL's own tables.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

PAGE_SIZE = 50          # managers on one FPL standings page
MAX_DETAIL = 15         # private leagues read in full (each costs a request or two)


def _key(row: Dict[str, Any]) -> int:
    """Unique, sequential order within a league (`rank` can tie)."""
    return int(row.get("rank_sort") or row.get("rank") or 0)


def page_of(rank: Optional[int]) -> int:
    """The standings page a given rank sits on."""
    return max(1, (int(rank) - 1) // PAGE_SIZE + 1) if rank else 1


def overview(league: Dict[str, Any], scope: str = "classic") -> Dict[str, Any]:
    """One league as the manager's profile lists it."""
    kind = "h2h" if scope == "h2h" else ("system" if league.get("league_type") == "s" else "private")
    rank, last = league.get("entry_rank"), league.get("entry_last_rank")
    return {
        "id": league.get("id"), "name": league.get("name"), "kind": kind,
        "my_rank": rank, "last_rank": last,
        "movement": (last - rank) if rank and last else None,       # positive: climbed since last week
        "size": league.get("rank_count") or league.get("max_entries"),
        "percentile": league.get("entry_percentile_rank"),          # FPL's own leagues only
        "closed": bool(league.get("closed")),
        "has_cup": bool(league.get("has_cup")),
    }


def standing_stats(entry_id: int, pages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The manager's place in a league, from whichever standings pages were read.

    Needs the first page (for the leader); if the manager's own page wasn't read the
    "mine" figures stay None rather than guessing.
    """
    rows: Dict[int, Dict[str, Any]] = {}
    for page in pages:
        for r in (page.get("standings") or {}).get("results") or []:
            if r.get("entry") is not None:
                rows[r["entry"]] = r
    ordered = sorted(rows.values(), key=_key)
    if not ordered:
        return None
    leader = ordered[0]
    out: Dict[str, Any] = {
        "leader": {"entry_name": leader.get("entry_name"), "player_name": leader.get("player_name"),
                   "total": leader.get("total")},
        "managers_seen": len(ordered),
        "more_pages": any((p.get("standings") or {}).get("has_next") for p in pages),
        "my_total": None, "my_gw": None, "gap_to_leader": None, "behind_next": None, "ahead_of_next": None,
        "next_above": None, "next_below": None, "i_lead": False,
    }
    gws = [r["event_total"] for r in ordered if isinstance(r.get("event_total"), (int, float))]
    totals = [r["total"] for r in ordered if isinstance(r.get("total"), (int, float))]
    if gws:
        best = max(ordered, key=lambda r: r.get("event_total") if isinstance(r.get("event_total"), (int, float)) else -1)
        out["gw_best"] = {"entry_name": best.get("entry_name"), "player_name": best.get("player_name"),
                          "event_total": best.get("event_total")}
        out["gw_avg"] = round(sum(gws) / len(gws), 1)
    if totals:
        out["avg_total"] = round(sum(totals) / len(totals), 1)

    mine_at = next((i for i, r in enumerate(ordered) if r.get("entry") == entry_id), None)
    if mine_at is None:
        return out
    mine = ordered[mine_at]
    out["my_total"], out["my_gw"] = mine.get("total"), mine.get("event_total")
    out["i_lead"] = mine_at == 0 and _key(mine) == 1
    if leader.get("total") is not None and mine.get("total") is not None:
        out["gap_to_leader"] = leader["total"] - mine["total"]
    # the neighbours count only if they really are the next rank either side
    # (the manager's page may start or end right at the edge of what was read)
    if mine_at > 0 and _key(ordered[mine_at - 1]) == _key(mine) - 1:
        above = ordered[mine_at - 1]
        out["next_above"] = {"entry_name": above.get("entry_name"), "total": above.get("total")}
        out["behind_next"] = above["total"] - mine["total"] if None not in (above.get("total"), mine.get("total")) else None
    if mine_at + 1 < len(ordered) and _key(ordered[mine_at + 1]) == _key(mine) + 1:
        below = ordered[mine_at + 1]
        out["next_below"] = {"entry_name": below.get("entry_name"), "total": below.get("total")}
        out["ahead_of_next"] = mine["total"] - below["total"] if None not in (below.get("total"), mine.get("total")) else None
    return out


def find_entry_row(entry_id: int, rank: Optional[int], first_page: Dict[str, Any],
                   standings_fn: Callable[[int, int], Dict[str, Any]], league_id: int) -> Optional[Dict[str, Any]]:
    """The manager's own standings row, even when they're not on the first page."""
    for r in (first_page.get("standings") or {}).get("results") or []:
        if r.get("entry") == entry_id:
            return r
    page = page_of(rank)
    if page <= 1:
        return None
    try:
        for r in (standings_fn(league_id, page).get("standings") or {}).get("results") or []:
            if r.get("entry") == entry_id:
                return r
    except Exception:
        return None
    return None


def _detail(entry_id: int, lg: Dict[str, Any], standings_fn: Callable[[int, int], Dict[str, Any]]) -> Dict[str, Any]:
    """Read the pages that matter for one private league and fold the numbers in."""
    out = dict(lg)
    try:
        pages = [standings_fn(lg["id"], 1)]
    except Exception:
        out["unavailable"] = True
        return out
    want = page_of(lg.get("my_rank"))
    if want > 1:
        try:
            pages.append(standings_fn(lg["id"], want))
        except Exception:
            pass                                   # the leader is still known; "mine" stays empty
    stats = standing_stats(entry_id, pages)
    if stats is None:
        out["unavailable"] = True
        return out
    out.update(stats)
    if not out.get("size") and not stats["more_pages"]:
        out["size"] = stats["managers_seen"]
    return out


def my_leagues(entry: Dict[str, Any], entry_id: int, standings_fn: Callable[[int, int], Dict[str, Any]],
               max_detail: int = MAX_DETAIL, workers: int = 4) -> Dict[str, Any]:
    """Every league the manager belongs to, with their place in each private one."""
    lg = entry.get("leagues") or {}
    classic = [overview(x, "classic") for x in lg.get("classic") or []]
    h2h = [overview(x, "h2h") for x in lg.get("h2h") or []]
    private = [x for x in classic if x["kind"] == "private"]
    system = [x for x in classic if x["kind"] == "system"]

    todo = private[:max_detail]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        detailed = list(pool.map(lambda x: _detail(entry_id, x, standings_fn), todo))
    detailed += private[max_detail:]

    ranked = [x for x in detailed if x.get("my_rank")]
    def place(x):                                  # 0 = top of the league, 1 = bottom
        return (x["my_rank"] - 1) / float(x["size"]) if x.get("size") else 1.0
    best = min(ranked, key=lambda x: (place(x), x["my_rank"]), default=None)
    summary = {
        "private": len(private),
        "leading": sum(1 for x in detailed if x.get("i_lead") or x.get("my_rank") == 1),
        "top3": sum(1 for x in ranked if x["my_rank"] <= 3),
        "climbing": sum(1 for x in ranked if (x.get("movement") or 0) > 0),
        "falling": sum(1 for x in ranked if (x.get("movement") or 0) < 0),
        "best": {"id": best["id"], "name": best["name"], "rank": best["my_rank"], "size": best.get("size")} if best else None,
        "unread": max(0, len(private) - max_detail),
    }
    return {
        "entry": entry_id,
        "team": entry.get("name"),
        "manager": ("%s %s" % (entry.get("player_first_name", ""), entry.get("player_last_name", ""))).strip(),
        "leagues": detailed + h2h + system,
        "summary": summary,
    }


def empty(entry_id: int, team: str = "", manager: str = "") -> Dict[str, Any]:
    """A manager with no leagues (the demo team, or a brand-new squad)."""
    return {"entry": entry_id, "team": team, "manager": manager, "leagues": [],
            "summary": {"private": 0, "leading": 0, "top3": 0, "climbing": 0, "falling": 0, "best": None, "unread": 0}}
