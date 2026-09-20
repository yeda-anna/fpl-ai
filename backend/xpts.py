"""Expected-points (xPts) rule engine.

This is the part fplcopilot.com calls "the data behind everything": a per-player,
per-fixture projection built from the public FPL stats. Nothing here is a black box -
every number below traces back to a documented FPL scoring rule.

Model outline
-------------
1. Team ratings   attack / defence strength from season xG and xGC, shrunk toward the
                  league average because only a handful of games have been played.
2. Fixture goals  Poisson means for each side of a fixture, adjusted for home advantage.
3. Minutes        availability x start rate -> P(play), P(60+), expected minutes.
4. Returns        the player's share of his team's xG / xA scaled onto the fixture.
5. Defence        Poisson clean-sheet probability and the -1 per 2 conceded penalty.
6. Extras         saves, the 2025/26 defensive-contribution bonus, BPS-implied bonus, cards.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# --- FPL scoring rules (2025/26) -------------------------------------------
GOAL_PTS = {1: 6, 2: 6, 3: 5, 4: 4}
CS_PTS = {1: 4, 2: 4, 3: 1, 4: 0}
ASSIST_PTS = 3
SAVE_PER_POINT = 3.0
DC_THRESHOLD = {1: None, 2: 10, 3: 12, 4: 12}   # DEF: CBIT>=10, MID/FWD: CBIRT>=12
DC_PTS = 2

# --- model constants -------------------------------------------------------
LEAGUE_GOALS_PER_TEAM = 1.45      # long-run Premier League average
HOME_ADV = 1.10                   # multiplier on the home side's expected goals
AWAY_ADV = 0.92
SHRINK_GAMES = 6.0                # prior weight, in games, for team ratings
PLAYER_SHRINK_90S = 2.5           # prior weight, in 90s, for player rates
SUB_MINUTES = 22.0                # minutes credited to a likely substitute
STARTER_MINUTES = 84.0            # minutes credited to a nailed starter
P60_GIVEN_START = 0.90


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def poisson_at_least(k: int, lam: float) -> float:
    """P(X >= k) for X ~ Poisson(lam)."""
    if k <= 0:
        return 1.0
    below = sum(poisson_pmf(i, lam) for i in range(k))
    return max(0.0, min(1.0, 1.0 - below))


def expected_concede_penalty(lam: float, cap: int = 12) -> float:
    """E[floor(goals_conceded / 2)] - the -1 per 2 conceded rule for GK and DEF."""
    total = 0.0
    for k in range(cap + 1):
        total += poisson_pmf(k, lam) * (k // 2)
    return total


def bonus_from_bps(bps_per_90: float) -> float:
    """Expected bonus points per 90, calibrated against this season's actual bonus.

    Bonus is winner-take-most: below roughly 14 BPS/90 a player almost never places
    in the top three, and above 26 he is regularly in them.
    """
    if bps_per_90 <= 6:
        return 0.0
    x = (bps_per_90 - 19.0) / 5.2
    return round(1.85 / (1.0 + math.exp(-x)) - 0.10, 4) if bps_per_90 > 6 else 0.0


class Engine(object):
    """Holds derived ratings for one snapshot of the FPL data."""

    def __init__(self, bootstrap: Dict[str, Any], fixtures: List[Dict[str, Any]]):
        self.bootstrap = bootstrap
        self.fixtures = fixtures
        self.teams = {t["id"]: t for t in bootstrap["teams"]}
        self.players = {p["id"]: p for p in bootstrap["elements"]}
        self.events = bootstrap["events"]
        self.current_gw = self._current_gw()
        self.next_gw = self._next_gw()
        self._played = self._games_played()
        self._team_rates = self._team_ratings()
        self._fixtures_by_gw = self._index_fixtures()
        self._priors = self._fit_priors()

    # -- calendar ----------------------------------------------------------
    def _current_gw(self) -> int:
        for e in self.events:
            if e.get("is_current"):
                return e["id"]
        finished = [e["id"] for e in self.events if e.get("finished")]
        return max(finished) if finished else 1

    def _next_gw(self) -> int:
        for e in self.events:
            if e.get("is_next"):
                return e["id"]
        return min(38, self.current_gw + 1)

    def _games_played(self) -> Dict[int, int]:
        played = {}
        for f in self.fixtures:
            if f.get("finished") or f.get("finished_provisional"):
                for side in ("team_h", "team_a"):
                    played[f[side]] = played.get(f[side], 0) + 1
        for tid in self.teams:
            played.setdefault(tid, 0)
        return played

    def _index_fixtures(self) -> Dict[int, List[Dict[str, Any]]]:
        by_gw = {}
        for f in self.fixtures:
            gw = f.get("event")
            if gw is None:
                continue
            by_gw.setdefault(gw, []).append(f)
        return by_gw

    # -- team strength -----------------------------------------------------
    def _team_ratings(self) -> Dict[int, Dict[str, float]]:
        """Attack, creativity and defence multipliers relative to the league average."""
        xg, xa, xgc = {}, {}, {}
        for p in self.bootstrap["elements"]:
            t = p["team"]
            xg[t] = xg.get(t, 0.0) + _f(p.get("expected_goals"))
            xa[t] = xa.get(t, 0.0) + _f(p.get("expected_assists"))
            # every on-pitch player is charged the team's conceded xG, so 11 players
            # over-count it by a factor of 11.
            xgc[t] = xgc.get(t, 0.0) + _f(p.get("expected_goals_conceded"))

        ratings = {}
        for tid in self.teams:
            games = max(1, self._played.get(tid, 0))
            n = float(self._played.get(tid, 0))
            w = n / (n + SHRINK_GAMES)          # how much to trust the observed rate

            xg_pg = xg.get(tid, 0.0) / games
            xa_pg = xa.get(tid, 0.0) / games
            xgc_pg = (xgc.get(tid, 0.0) / games) / 11.0

            att = w * (xg_pg / LEAGUE_GOALS_PER_TEAM) + (1 - w) * 1.0
            dfn = w * (xgc_pg / LEAGUE_GOALS_PER_TEAM) + (1 - w) * 1.0
            ratings[tid] = {
                "attack": max(0.45, min(2.2, att)),
                "defence": max(0.45, min(2.2, dfn)),   # >1 means leaky
                "xg_per_game": max(0.25, xg_pg if n else LEAGUE_GOALS_PER_TEAM),
                "xa_per_game": max(0.18, xa_pg if n else LEAGUE_GOALS_PER_TEAM * 0.7),
                "xgc_per_game": max(0.25, xgc_pg if n else LEAGUE_GOALS_PER_TEAM),
                "games": self._played.get(tid, 0),
            }
        return ratings

    def team_rating(self, team_id: int) -> Dict[str, float]:
        return self._team_rates[team_id]

    def fixture_goals(self, team_id: int, opponent_id: int, home: bool):
        """Poisson means: (goals this team scores, goals it concedes)."""
        me = self._team_rates[team_id]
        opp = self._team_rates[opponent_id]
        venue_for = HOME_ADV if home else AWAY_ADV
        venue_against = AWAY_ADV if home else HOME_ADV
        lam_for = LEAGUE_GOALS_PER_TEAM * me["attack"] * opp["defence"] * venue_for
        lam_against = LEAGUE_GOALS_PER_TEAM * opp["attack"] * me["defence"] * venue_against
        return max(0.15, lam_for), max(0.15, lam_against)

    # -- minutes -----------------------------------------------------------
    def availability(self, p: Dict[str, Any]) -> float:
        status = p.get("status", "a")
        chance = p.get("chance_of_playing_next_round")
        if status == "a":
            return 1.0 if chance is None else max(0.0, min(1.0, chance / 100.0))
        if status == "d":
            return 0.5 if chance is None else max(0.0, min(1.0, chance / 100.0))
        return 0.0     # i (injured), s (suspended), u (unavailable), n (not in squad)

    def minutes_model(self, p: Dict[str, Any], minutes_override: Optional[float] = None):
        games = max(1, self._played.get(p["team"], 0))
        avail = self.availability(p)
        starts = _f(p.get("starts"))
        minutes = _f(p.get("minutes"))

        start_rate = min(1.0, starts / games)
        avg_minutes = minutes / games
        # a player averaging well under a start's worth of minutes is a rotation risk
        if start_rate <= 0 and avg_minutes <= 0:
            start_rate = 0.0

        p_start = avail * start_rate
        cameo = avail * max(0.0, min(0.85, (avg_minutes - start_rate * STARTER_MINUTES) / SUB_MINUTES))
        p_play = min(1.0, p_start + (1.0 - p_start) * cameo)
        p60 = p_start * P60_GIVEN_START

        xmins = p_start * STARTER_MINUTES + max(0.0, p_play - p_start) * SUB_MINUTES
        if minutes_override is not None:
            xmins = max(0.0, min(90.0, float(minutes_override)))
            p_start = avail * min(1.0, xmins / STARTER_MINUTES)
            p_play = avail * (1.0 if xmins > 0 else 0.0)
            p60 = avail * (1.0 if xmins >= 60 else 0.0) * P60_GIVEN_START if xmins >= 60 else 0.0
        return {
            "availability": round(avail, 3),
            "p_start": round(p_start, 3),
            "p_play": round(p_play, 3),
            "p60": round(p60, 3),
            "xmins": round(xmins, 1),
        }

    # -- player rates ------------------------------------------------------
    @staticmethod
    def _least_squares(xs: List[float], ys: List[float]):
        n = len(xs)
        if n < 6:
            return None
        mx = sum(xs) / n
        my = sum(ys) / n
        var = sum((x - mx) ** 2 for x in xs)
        if var <= 0:
            return None
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
        return slope, my - slope * mx

    def _fit_priors(self) -> Dict[int, Dict[str, Any]]:
        """Fit each rate against price, per position.

        Five games is a tiny sample, so a thin-minutes player needs a prior to be
        shrunk toward. Price is the market's own estimate of a player's rate, which
        makes a far better prior than one flat number for every midfielder.
        """
        priors = {}
        for pos in (1, 2, 3, 4):
            pool = [p for p in self.bootstrap["elements"]
                    if p["element_type"] == pos and _f(p.get("minutes")) >= 180]
            out = {}
            for key, field in (("xg90", "expected_goals_per_90"),
                               ("xa90", "expected_assists_per_90"),
                               ("dc90", "defensive_contribution_per_90"),
                               ("bps90", None)):
                xs, ys = [], []
                for p in pool:
                    price = p["now_cost"] / 10.0
                    if field is None:
                        nineties = _f(p.get("minutes")) / 90.0
                        val = _f(p.get("bps")) / nineties if nineties > 0 else 0.0
                    else:
                        val = _f(p.get(field))
                    xs.append(price)
                    ys.append(val)
                fit = self._least_squares(xs, ys)
                mean = (sum(ys) / len(ys)) if ys else 0.0
                out[key] = {"fit": fit, "mean": mean}
            priors[pos] = out
        return priors

    def _prior_for(self, pos: int, key: str, price: float) -> float:
        info = self._priors.get(pos, {}).get(key)
        if not info:
            return 0.0
        if info["fit"]:
            slope, intercept = info["fit"]
            return max(0.0, slope * price + intercept)
        return max(0.0, info["mean"])

    def player_rates(self, p: Dict[str, Any]) -> Dict[str, float]:
        """Per-90 rates, shrunk toward a price-implied prior when minutes are thin."""
        nineties = _f(p.get("minutes")) / 90.0
        w = nineties / (nineties + PLAYER_SHRINK_90S) if nineties > 0 else 0.0
        pos = p["element_type"]
        price = p["now_cost"] / 10.0
        obs_bps = (_f(p.get("bps")) / nineties) if nineties > 0 else 0.0
        return {
            "xg90": w * _f(p.get("expected_goals_per_90")) + (1 - w) * self._prior_for(pos, "xg90", price),
            "xa90": w * _f(p.get("expected_assists_per_90")) + (1 - w) * self._prior_for(pos, "xa90", price),
            "dc90": w * _f(p.get("defensive_contribution_per_90")) + (1 - w) * self._prior_for(pos, "dc90", price),
            "saves90": _f(p.get("saves_per_90")),
            "bps90": w * obs_bps + (1 - w) * self._prior_for(pos, "bps90", price),
            "yc90": (_f(p.get("yellow_cards")) / nineties) if nineties > 1.5 else 0.12,
            "pens": bool(p.get("penalties_order")),
        }

    # -- the projection ----------------------------------------------------
    def player_fixture_xpts(self, player_id: int, fixture: Dict[str, Any],
                            minutes_override: Optional[float] = None) -> Dict[str, Any]:
        p = self.players[player_id]
        pos = p["element_type"]
        team = p["team"]
        home = fixture["team_h"] == team
        opponent = fixture["team_a"] if home else fixture["team_h"]

        lam_for, lam_against = self.fixture_goals(team, opponent, home)
        mins = self.minutes_model(p, minutes_override)
        rates = self.player_rates(p)
        share = mins["xmins"] / 90.0

        tr = self._team_rates[team]
        # the player's slice of his team's output, re-scaled onto this fixture
        goal_share = rates["xg90"] / max(0.30, tr["xg_per_game"])
        assist_share = rates["xa90"] / max(0.20, tr["xa_per_game"])
        xg = goal_share * lam_for * share
        xa = assist_share * (lam_for * 0.72) * share    # ~72% of goals are assisted

        pts_goals = xg * GOAL_PTS[pos]
        pts_assists = xa * ASSIST_PTS

        p_cs = math.exp(-lam_against) * mins["p60"]
        pts_cs = p_cs * CS_PTS[pos]

        pts_conceded = 0.0
        if pos in (1, 2):
            pts_conceded = -expected_concede_penalty(lam_against) * mins["p60"]

        pts_saves = 0.0
        if pos == 1:
            pts_saves = (rates["saves90"] * share) / SAVE_PER_POINT

        pts_dc = 0.0
        threshold = DC_THRESHOLD[pos]
        if threshold and rates["dc90"] > 0:
            lam_dc = rates["dc90"] * share
            pts_dc = poisson_at_least(threshold, lam_dc) * DC_PTS

        pts_appearance = mins["p_play"] * 1.0 + mins["p60"] * 1.0
        pts_bonus = bonus_from_bps(rates["bps90"]) * share
        pts_cards = -rates["yc90"] * share

        total = (pts_appearance + pts_goals + pts_assists + pts_cs + pts_conceded
                 + pts_saves + pts_dc + pts_bonus + pts_cards)

        return {
            "gw": fixture.get("event"),
            "opponent": opponent,
            "opponent_short": self.teams[opponent]["short_name"],
            "home": home,
            "fdr": fixture["team_h_difficulty"] if home else fixture["team_a_difficulty"],
            "xg": round(xg, 3),
            "xa": round(xa, 3),
            "lam_for": round(lam_for, 3),
            "lam_against": round(lam_against, 3),
            "clean_sheet_prob": round(math.exp(-lam_against), 3),
            "xmins": mins["xmins"],
            "p_start": mins["p_start"],
            "breakdown": {
                "appearance": round(pts_appearance, 3),
                "goals": round(pts_goals, 3),
                "assists": round(pts_assists, 3),
                "clean_sheet": round(pts_cs, 3),
                "conceded": round(pts_conceded, 3),
                "saves": round(pts_saves, 3),
                "defensive_contribution": round(pts_dc, 3),
                "bonus": round(pts_bonus, 3),
                "cards": round(pts_cards, 3),
            },
            "xpts": round(max(0.0, total), 3),
        }

    def fixtures_for_team(self, team_id: int, gw: int) -> List[Dict[str, Any]]:
        out = []
        for f in self._fixtures_by_gw.get(gw, []):
            if f["team_h"] == team_id or f["team_a"] == team_id:
                out.append(f)
        return out

    def player_horizon(self, player_id: int, start_gw: int, horizon: int,
                       minutes_override: Optional[float] = None) -> Dict[str, Any]:
        """xPts for one player across the next `horizon` gameweeks."""
        p = self.players[player_id]
        per_gw = []
        for gw in range(start_gw, min(38, start_gw + horizon - 1) + 1):
            fixtures = self.fixtures_for_team(p["team"], gw)
            legs = [self.player_fixture_xpts(player_id, f, minutes_override) for f in fixtures]
            per_gw.append({
                "gw": gw,
                "fixtures": legs,
                "xpts": round(sum(leg["xpts"] for leg in legs), 3),
                "blank": len(legs) == 0,
                "double": len(legs) > 1,
            })
        return {
            "id": player_id,
            "web_name": p["web_name"],
            "team": p["team"],
            "team_short": self.teams[p["team"]]["short_name"],
            "position": p["element_type"],
            "now_cost": p["now_cost"],
            "price": round(p["now_cost"] / 10.0, 1),
            "selected_by_percent": _f(p.get("selected_by_percent")),
            "status": p.get("status"),
            "news": p.get("news") or "",
            "form": _f(p.get("form")),
            "total_points": p.get("total_points", 0),
            "minutes": p.get("minutes", 0),
            "per_gw": per_gw,
            "xpts_total": round(sum(g["xpts"] for g in per_gw), 3),
            "xpts_next": per_gw[0]["xpts"] if per_gw else 0.0,
            "fpl_ep_next": _f(p.get("ep_next")),
        }

    def all_players_horizon(self, start_gw: int, horizon: int,
                            overrides: Optional[Dict[int, float]] = None) -> List[Dict[str, Any]]:
        overrides = overrides or {}
        rows = []
        for pid in self.players:
            if self.players[pid].get("removed"):
                continue
            rows.append(self.player_horizon(pid, start_gw, horizon, overrides.get(pid)))
        rows.sort(key=lambda r: -r["xpts_total"])
        return rows
