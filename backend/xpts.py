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

from rules import Rules, DC_THRESHOLD as RULE_DC_THRESHOLD, SAVES_PER_POINT

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
STARTER_MINUTES = 87.0            # minutes credited to a nailed starter
P60_GIVEN_START = 0.90
RECENT_DECAY = 0.72               # each gameweek further back counts 28% less
RECENT_WEIGHT_CAP = 0.70          # recent form never fully overrides the season
ELO_K_DEFAULT = 0.0011            # goals multiplier per Elo point, if it can't be fitted
ELO_K_RANGE = (0.0006, 0.0020)
RETURN_RAMP = (60.0, 75.0)        # minutes in a player's first and second games back
RETURN_NEWS_DAYS = 28             # a flag this recent marks a player as coming back
REVERT_RATE = 0.50                # per gameweek ahead, the share of the gap to his usual role that remains


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

    def __init__(self, bootstrap: Dict[str, Any], fixtures: List[Dict[str, Any]],
                 elo: Optional[Dict[int, Dict[str, Any]]] = None,
                 live_by_gw: Optional[Dict[int, Dict[str, Any]]] = None):
        self.bootstrap = bootstrap
        self.rules = Rules(bootstrap)
        self.elo = elo or {}
        self.live_by_gw = live_by_gw or {}
        self.elo_k = ELO_K_DEFAULT
        self.fixtures = fixtures
        self.teams = {t["id"]: t for t in bootstrap["teams"]}
        self.players = {p["id"]: p for p in bootstrap["elements"]}
        self.events = bootstrap["events"]
        self.current_gw = self._current_gw()
        self.next_gw = self._next_gw()
        self._played = self._games_played()
        self._fixtures_by_gw = self._index_fixtures()
        self._team_rates = self._team_ratings()
        self._recent = self._recent_form()
        self._priors = self._fit_priors()
        self._blocked = self._blocked_weeks()

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
        """Attack and defence multipliers relative to the league average.

        Observed xG and xG conceded are shrunk toward a prior. With Elo available the
        prior is the club's own Elo-implied strength; without it, league average.
        """
        xg, xa, xgc = {}, {}, {}
        for p in self.bootstrap["elements"]:
            t = p["team"]
            xg[t] = xg.get(t, 0.0) + _f(p.get("expected_goals"))
            xa[t] = xa.get(t, 0.0) + _f(p.get("expected_assists"))
            # every on-pitch player is charged the team's conceded xG, so 11 players
            # over-count it by a factor of 11.
            xgc[t] = xgc.get(t, 0.0) + _f(p.get("expected_goals_conceded"))

        observed = {}
        for tid in self.teams:
            games = max(1, self._played.get(tid, 0))
            observed[tid] = {
                "xg_pg": xg.get(tid, 0.0) / games,
                "xa_pg": xa.get(tid, 0.0) / games,
                "xgc_pg": (xgc.get(tid, 0.0) / games) / 11.0,
                "n": float(self._played.get(tid, 0)),
            }

        # Elo prior. Fit how many goals an Elo point is worth from this season's
        # own numbers, so the prior is calibrated rather than assumed.
        elos = {tid: self.elo[tid]["elo"] for tid in self.teams if tid in self.elo}
        mean_elo = (sum(elos.values()) / len(elos)) if elos else None
        if elos and len(elos) >= 12:
            xs, ys = [], []
            for tid, e in elos.items():
                o = observed[tid]
                if o["n"] <= 0 or o["xg_pg"] <= 0 or o["xgc_pg"] <= 0:
                    continue
                xs.append(e - mean_elo)
                ys.append(0.5 * (math.log(o["xg_pg"] / LEAGUE_GOALS_PER_TEAM)
                                 - math.log(o["xgc_pg"] / LEAGUE_GOALS_PER_TEAM)))
            den = sum(x * x for x in xs)
            if den > 0:
                k = sum(x * y for x, y in zip(xs, ys)) / den
                self.elo_k = max(ELO_K_RANGE[0], min(ELO_K_RANGE[1], k))

        ratings = {}
        for tid in self.teams:
            o = observed[tid]
            n = o["n"]
            w = n / (n + SHRINK_GAMES)          # how much to trust the observed rate

            if mean_elo is not None and tid in elos:
                z = elos[tid] - mean_elo
                prior_att = math.exp(self.elo_k * z)
                prior_def = math.exp(-self.elo_k * z)
            else:
                prior_att = prior_def = 1.0

            att_obs = o["xg_pg"] / LEAGUE_GOALS_PER_TEAM if n else prior_att
            def_obs = o["xgc_pg"] / LEAGUE_GOALS_PER_TEAM if n else prior_def
            att = w * att_obs + (1 - w) * prior_att
            dfn = w * def_obs + (1 - w) * prior_def
            ratings[tid] = {
                "attack": max(0.45, min(2.2, att)),
                "defence": max(0.45, min(2.2, dfn)),   # >1 means leaky
                "attack_prior": round(prior_att, 3),
                "defence_prior": round(prior_def, 3),
                "elo": round(elos[tid], 1) if tid in elos else None,
                "xg_per_game": max(0.25, o["xg_pg"] if n else LEAGUE_GOALS_PER_TEAM * prior_att),
                "xa_per_game": max(0.18, o["xa_pg"] if n else LEAGUE_GOALS_PER_TEAM * 0.7 * prior_att),
                "xgc_per_game": max(0.25, o["xgc_pg"] if n else LEAGUE_GOALS_PER_TEAM * prior_def),
                "games": self._played.get(tid, 0),
            }
        return ratings

    def _blocked_weeks(self) -> Dict[int, set]:
        """Gameweeks a player cannot play for contractual reasons.

        bootstrap-static's scout_risks lists loanees who may not face their parent
        club in a given gameweek. That's certain, so it's a hard zero rather than a
        probability.
        """
        out: Dict[int, set] = {}
        for p in self.bootstrap["elements"]:
            for risk in p.get("scout_risks") or []:
                if risk.get("property") == "loan_ineligible" and risk.get("gameweek"):
                    out.setdefault(p["id"], set()).add(int(risk["gameweek"]))
        return out

    def blocked(self, player_id: int, gw: Optional[int]) -> bool:
        return gw is not None and gw in self._blocked.get(player_id, ())

    # -- recent form -------------------------------------------------------
    def _recent_form(self) -> Dict[int, Dict[str, float]]:
        """Recency-weighted minutes and starts from the last few finished gameweeks.

        A gameweek in which a player's club had no fixture is skipped rather than
        counted as zero minutes; a double gameweek is split per fixture.
        """
        out: Dict[int, Dict[str, float]] = {}
        if not self.live_by_gw:
            return out
        gws = sorted(self.live_by_gw.keys(), reverse=True)
        fixtures_per_team: Dict[int, Dict[int, int]] = {}
        for gw in gws:
            counts = {}
            for f in self._fixtures_by_gw.get(gw, []):
                for side in ("team_h", "team_a"):
                    counts[f[side]] = counts.get(f[side], 0) + 1
            fixtures_per_team[gw] = counts

        for k, gw in enumerate(gws):
            weight = RECENT_DECAY ** k
            payload = self.live_by_gw[gw] or {}
            for el in payload.get("elements", []):
                pid = el.get("id")
                p = self.players.get(pid)
                if not p:
                    continue
                n_fix = fixtures_per_team.get(gw, {}).get(p["team"], 0)
                if n_fix <= 0:
                    continue
                st = el.get("stats", {})
                mins = _f(st.get("minutes")) / n_fix
                starts = min(1.0, _f(st.get("starts")) / n_fix)
                r = out.setdefault(pid, {"w": 0.0, "minutes": 0.0, "starts": 0.0,
                                         "start_minutes": 0.0, "start_w": 0.0, "games": 0})
                r["w"] += weight
                r["minutes"] += weight * mins
                r["starts"] += weight * starts
                r["games"] += 1
                if starts > 0 and mins > 0:
                    r["start_minutes"] += weight * mins
                    r["start_w"] += weight
        return out

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

    def _returning(self, p: Dict[str, Any], recent_avg: float) -> bool:
        """Fit (or nearly) but with almost no recent minutes, and recently flagged.

        That pattern is an injury absence, not a player who has been dropped, so his
        minutes should come from his normal role rather than from the empty weeks.
        """
        if self.availability(p) <= 0 or recent_avg >= 20:
            return False
        if p.get("status") == "d" or p.get("news"):
            return True
        added = p.get("news_added")
        if added:
            try:
                import datetime as _dt
                ts = _dt.datetime.strptime(added[:19], "%Y-%m-%dT%H:%M:%S")
                return (_dt.datetime.utcnow() - ts).days <= RETURN_NEWS_DAYS
            except Exception:
                return False
        return False

    def minutes_model(self, p: Dict[str, Any], minutes_override: Optional[float] = None,
                      gw_offset: int = 0):
        games = max(1, self._played.get(p["team"], 0))
        avail = self.availability(p)
        # FPL's chance-of-playing figure is for the next round only. A doubtful
        # player's odds recover the further ahead we look; injured and suspended
        # players stay out until the data says otherwise.
        if gw_offset > 0 and p.get("status") == "d" and avail > 0:
            avail = avail + (1.0 - avail) * (1.0 - REVERT_RATE ** gw_offset)
        season_start = min(1.0, _f(p.get("starts")) / games)
        season_avg = _f(p.get("minutes")) / games

        start_rate, avg_minutes, starter_mins = season_start, season_avg, STARTER_MINUTES
        recent = self._recent.get(p["id"])
        trend = None
        if recent and recent["w"] > 0:
            # how far to lean on the last few weeks grows with how many we have
            lean = min(RECENT_WEIGHT_CAP, 0.25 + 0.11 * recent["games"])
            r_start = recent["starts"] / recent["w"]
            r_avg = recent["minutes"] / recent["w"]
            start_rate = lean * r_start + (1 - lean) * season_start
            avg_minutes = lean * r_avg + (1 - lean) * season_avg
            trend = round(r_avg - season_avg, 1)
            if recent["start_w"] > 0:
                # minutes a player actually gets when he starts - this is what moves
                # a winger who's subbed at 70 below a centre-back who plays 90
                own = recent["start_minutes"] / recent["start_w"]
                trust = recent["start_w"] / (recent["start_w"] + 1.5)
                starter_mins = max(55.0, min(90.0, trust * own + (1 - trust) * STARTER_MINUTES))

        returning = False
        recent_avg = (recent["minutes"] / recent["w"]) if (recent and recent["w"] > 0) else season_avg
        if self._returning(p, recent_avg):
            returning = True
            price = p["now_cost"] / 10.0
            start_rate = max(start_rate, min(0.95, self._prior_for(p["element_type"], "start_rate", price)))
            # ease back in: limited minutes for the first two games, then his usual
            if gw_offset < len(RETURN_RAMP):
                starter_mins = min(starter_mins, RETURN_RAMP[gw_offset])
            avg_minutes = start_rate * starter_mins

        # Further ahead, regress toward his established role. Next week's minutes are
        # mostly about recent selection; minutes in five weeks are mostly about who
        # the player is. Only applies upward, to available players priced as regulars.
        if gw_offset > 0 and not returning and avail > 0:
            price = p["now_cost"] / 10.0
            role = min(0.95, self._prior_for(p["element_type"], "start_rate", price))
            pull = 1.0 - REVERT_RATE ** gw_offset
            if role > start_rate:
                start_rate += (role - start_rate) * pull
            if starter_mins < STARTER_MINUTES and role >= 0.6:
                starter_mins += (STARTER_MINUTES - starter_mins) * pull
            avg_minutes = max(avg_minutes, start_rate * starter_mins)

        p_start = avail * max(0.0, min(1.0, start_rate))
        cameo = avail * max(0.0, min(0.85, (avg_minutes - start_rate * starter_mins) / SUB_MINUTES))
        p_play = min(1.0, p_start + (1.0 - p_start) * cameo)
        p60 = p_start * (P60_GIVEN_START if starter_mins >= 70 else
                         max(0.35, P60_GIVEN_START * (starter_mins - 45) / 25.0))

        xmins = p_start * starter_mins + max(0.0, p_play - p_start) * SUB_MINUTES
        overridden = minutes_override is not None
        if overridden:
            xmins = max(0.0, min(90.0, float(minutes_override)))
            p_start = avail * min(1.0, xmins / max(60.0, starter_mins))
            p_play = avail * (1.0 if xmins > 0 else 0.0)
            p60 = (avail * P60_GIVEN_START) if xmins >= 60 else 0.0
        return {
            "availability": round(avail, 3),
            "p_start": round(p_start, 3),
            "p_play": round(p_play, 3),
            "p60": round(p60, 3),
            "xmins": round(xmins, 1),
            "starter_minutes": round(starter_mins, 1),
            "recent_trend": trend,
            "returning": returning,
            "overridden": overridden,
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
            # how often a fit player at this price starts - the prior for anyone
            # whose own recent minutes were wiped out by an injury
            sx, sy = [], []
            for p in pool:
                if p.get("status") != "a" or p.get("news"):
                    continue
                g = max(1, self._played.get(p["team"], 0))
                sx.append(p["now_cost"] / 10.0)
                sy.append(min(1.0, _f(p.get("starts")) / g))
            fit = self._least_squares(sx, sy)
            out["start_rate"] = {"fit": fit, "mean": (sum(sy) / len(sy)) if sy else 0.5}
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
                            minutes_override: Optional[float] = None,
                            gw_offset: int = 0) -> Dict[str, Any]:
        p = self.players[player_id]
        pos = p["element_type"]
        team = p["team"]
        home = fixture["team_h"] == team
        opponent = fixture["team_a"] if home else fixture["team_h"]

        lam_for, lam_against = self.fixture_goals(team, opponent, home)
        R = self.rules
        loan_block = self.blocked(player_id, fixture.get("event"))
        if loan_block:
            minutes_override = 0.0
        mins = self.minutes_model(p, minutes_override, gw_offset)
        rates = self.player_rates(p)
        share = mins["xmins"] / 90.0

        tr = self._team_rates[team]
        # the player's slice of his team's output, re-scaled onto this fixture
        goal_share = rates["xg90"] / max(0.30, tr["xg_per_game"])
        assist_share = rates["xa90"] / max(0.20, tr["xa_per_game"])
        xg = goal_share * lam_for * share
        xa = assist_share * (lam_for * 0.72) * share    # ~72% of goals are assisted

        # every points value below comes from FPL's own game_config.scoring
        pts_goals = xg * R.goal(pos)
        pts_assists = xa * R.assist()

        p_cs = math.exp(-lam_against) * mins["p60"]
        pts_cs = p_cs * R.clean_sheet(pos)

        pts_conceded = 0.0
        if R.conceded(pos):
            pts_conceded = R.conceded(pos) * expected_concede_penalty(lam_against) * mins["p60"]

        pts_saves = 0.0
        if pos == 1:
            pts_saves = (rates["saves90"] * share) / SAVES_PER_POINT * R.save_point()

        pts_dc = 0.0
        threshold = RULE_DC_THRESHOLD[pos]
        if threshold and rates["dc90"] > 0 and R.dc_points(pos):
            lam_dc = rates["dc90"] * share
            pts_dc = poisson_at_least(threshold, lam_dc) * R.dc_points(pos)

        # short_play for 1-59 minutes, long_play for 60+ (not additive)
        pts_appearance = (mins["p_play"] - mins["p60"]) * R.short_play() + mins["p60"] * R.long_play()
        pts_bonus = bonus_from_bps(rates["bps90"]) * share * R.bonus_unit()
        pts_cards = rates["yc90"] * share * R.yellow()

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
            "loan_blocked": loan_block,
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
            legs = [self.player_fixture_xpts(player_id, f, minutes_override, gw - start_gw)
                    for f in fixtures]
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
