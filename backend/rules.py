"""Game rules read from bootstrap-static, not hardcoded.

FPL publishes its own scoring table (game_config.scoring), squad limits
(game_settings), formation limits (element_types) and chip windows (chips).
Reading them means a rule change - like 2026/27's 10-point goalkeeper goal or the
two-sets-of-chips format - flows through the model, solver and chip planner
without anyone editing code. Every value has a fallback for older payloads.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

POS_KEY = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Fallbacks: the 2025/26 rules, used only if a field is missing.
_DEFAULT_SCORING = {
    "goals_scored": {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4},
    "clean_sheets": {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
    "goals_conceded": {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
    "defensive_contribution": {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
    "assists": 3, "saves": 1, "penalties_saved": 5, "penalties_missed": -2,
    "yellow_cards": -1, "red_cards": -3, "own_goals": -2, "bonus": 1,
    "long_play": 2, "short_play": 1,
}
# Thresholds FPL doesn't publish in the payload; these are the documented rules.
SAVES_PER_POINT = 3
CONCEDED_PER_PENALTY = 2
DC_THRESHOLD = {1: None, 2: 10, 3: 12, 4: 12}


def roll_free_transfers(ft: int, made: int, chip_week: bool, max_ft: int) -> int:
    """Free transfers for the next gameweek, given this week's count and what was done.

    Normal week: spend `made` of the `ft` you had, keep what's left, gain one.
    Wildcard / Free Hit week: the week's own free transfer is used up by the chip
    and nothing already banked is lost, so next week you have the same number you
    started this one with - no extra one is added.
    """
    if chip_week:
        return max(1, min(max_ft, ft))
    return min(max_ft, max(0, ft - made) + 1)


class Rules(object):
    def __init__(self, bootstrap: Dict[str, Any]):
        gc = bootstrap.get("game_config") or {}
        gs = bootstrap.get("game_settings") or {}
        sc = dict(_DEFAULT_SCORING)
        sc.update({k: v for k, v in (gc.get("scoring") or {}).items() if v is not None})
        self.scoring = sc

        # squad and transfer limits
        self.squad_size = int(gs.get("squad_squadsize") or 15)
        self.xi_size = int(gs.get("squad_squadplay") or 11)
        self.club_limit = int(gs.get("squad_team_limit") or 3)
        self.budget = int(gs.get("squad_total_spend") or 1000)          # tenths of £m
        self.max_free_transfers = 1 + int(gs.get("max_extra_free_transfers") or 4)
        self.sell_on_fee = float(gs.get("transfers_sell_on_fee") or 0.5)
        self.vice_enabled = bool(gs.get("sys_vice_captain_enabled", True))

        # formation limits per position
        self.quota, self.xi_min, self.xi_max = {}, {}, {}
        for t in bootstrap.get("element_types", []):
            self.quota[t["id"]] = int(t.get("squad_select") or 0)
            self.xi_min[t["id"]] = int(t.get("squad_min_play") or 0)
            self.xi_max[t["id"]] = int(t.get("squad_max_play") or 0)
        if not self.quota:
            self.quota = {1: 2, 2: 5, 3: 5, 4: 3}
            self.xi_min = {1: 1, 2: 3, 3: 2, 4: 1}
            self.xi_max = {1: 1, 2: 5, 3: 5, 4: 3}

        # chip windows: each chip can appear more than once, each with its own window
        self.chips = [{"name": c["name"], "start": c.get("start_event") or 1,
                       "stop": c.get("stop_event") or 38}
                      for c in bootstrap.get("chips", [])]

        settings = gc.get("settings") or {}
        self.price_change_deadlines = settings.get("price_change_deadlines") or []
        self.price_change_last_updated = (gc.get("status") or {}).get("price_change_last_updated")

    # -- scoring helpers ----------------------------------------------------
    def _by_pos(self, key: str, pos: int) -> float:
        v = self.scoring.get(key, 0)
        if isinstance(v, dict):
            return float(v.get(POS_KEY[pos], 0) or 0)
        return float(v or 0)

    def goal(self, pos):            return self._by_pos("goals_scored", pos)
    def clean_sheet(self, pos):     return self._by_pos("clean_sheets", pos)
    def conceded(self, pos):        return self._by_pos("goals_conceded", pos)
    def dc_points(self, pos):       return self._by_pos("defensive_contribution", pos)
    def assist(self):               return float(self.scoring.get("assists", 3))
    def save_point(self):           return float(self.scoring.get("saves", 1))
    def yellow(self):               return float(self.scoring.get("yellow_cards", -1))
    def long_play(self):            return float(self.scoring.get("long_play", 2))
    def short_play(self):           return float(self.scoring.get("short_play", 1))
    def bonus_unit(self):           return float(self.scoring.get("bonus", 1))

    # -- chip availability ----------------------------------------------------
    def chip_available(self, name: str, gw: int, history: List[Dict[str, Any]]) -> bool:
        """Can this chip be played in this gameweek, given what's already been used?

        A chip is available in a gameweek if some window for it covers that week and
        the manager hasn't already played that chip inside the same window.
        """
        for win in self.chips:
            if win["name"] != name or not (win["start"] <= gw <= win["stop"]):
                continue
            used = any(h.get("name") == name and win["start"] <= (h.get("event") or 0) <= win["stop"]
                       for h in history or [])
            if not used:
                return True
        return False

    def chip_windows_left(self, name: str, from_gw: int, history: List[Dict[str, Any]]) -> List[Dict[str, int]]:
        out = []
        for win in self.chips:
            if win["name"] != name or win["stop"] < from_gw:
                continue
            used = any(h.get("name") == name and win["start"] <= (h.get("event") or 0) <= win["stop"]
                       for h in history or [])
            if not used:
                out.append({"start": max(win["start"], from_gw), "stop": win["stop"]})
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scoring": {
                "goal": {POS_KEY[p]: self.goal(p) for p in POS_KEY},
                "clean_sheet": {POS_KEY[p]: self.clean_sheet(p) for p in POS_KEY},
                "conceded_per_2": {POS_KEY[p]: self.conceded(p) for p in POS_KEY},
                "defensive_contribution": {POS_KEY[p]: self.dc_points(p) for p in POS_KEY},
                "assist": self.assist(), "save_per_3": self.save_point(),
                "appearance_under_60": self.short_play(), "appearance_60_plus": self.long_play(),
                "yellow": self.yellow(),
            },
            "squad_size": self.squad_size, "club_limit": self.club_limit,
            "budget": self.budget / 10.0, "max_free_transfers": self.max_free_transfers,
            "sell_on_fee": self.sell_on_fee,
            "formation": {POS_KEY[p]: [self.xi_min[p], self.xi_max[p]] for p in self.quota},
            "quota": {POS_KEY[p]: self.quota[p] for p in self.quota},
            "chips": self.chips,
            "price_change_deadlines": self.price_change_deadlines,
            "price_change_last_updated": self.price_change_last_updated,
        }
