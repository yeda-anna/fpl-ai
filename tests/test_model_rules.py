"""The rules the owner asked the transfer planner to follow, proven on a small made-up league:

1. minutes in previous gameweeks shape expected minutes (already in the model; kept honest here)
2. recent form and actual goals/assists move a player's scoring rate; P(score) is shown
3. FPL's chance of playing: below the threshold nobody is bought or captained
4. an opponent in poor recent form is treated as weaker

Run:  ./.venv/bin/python tests/test_model_rules.py
"""
from __future__ import annotations

import copy
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import solver   # noqa: E402
import xpts     # noqa: E402

TEAMS = [1, 2, 3, 4]
PAIRS = [(1, 2), (3, 4), (1, 3), (2, 4), (1, 4), (2, 3)]      # a round of everyone-plays-everyone


def league():
    """Four clubs, a forward per club plus a midfielder at club 1, five weeks played of ten."""
    teams = [{"id": t, "name": "Club %d" % t, "short_name": "C%d" % t, "code": t} for t in TEAMS]
    events = [{"id": g, "finished": g <= 5, "is_current": g == 5, "is_next": g == 6,
               "deadline_time": "2026-10-%02dT10:00:00Z" % g} for g in range(1, 11)]
    fixtures, fid = [], 1
    for g in range(1, 11):
        h, a = PAIRS[(g - 1) % len(PAIRS)]
        for (x, y) in ((h, a), tuple(t for t in TEAMS if t not in (h, a))):
            fixtures.append({"id": fid, "event": g, "team_h": x, "team_a": y, "finished": g <= 5,
                             "team_h_difficulty": 3, "team_a_difficulty": 3})
            fid += 1
    elements = []
    for t in TEAMS:
        elements.append(player(10 + t, t, 4, xg90=0.45, xa90=0.15, goals=2, assists=1))
    elements.append(player(99, 1, 3, xg90=0.20, xa90=0.20, goals=1, assists=1))
    return {"teams": teams, "events": events, "elements": elements}, fixtures


def player(pid, team, pos, xg90, xa90, goals, assists, minutes=450):
    return {"id": pid, "team": team, "element_type": pos, "web_name": "P%d" % pid, "now_cost": 70,
            "status": "a", "chance_of_playing_next_round": None, "news": "",
            "minutes": minutes, "starts": 5, "expected_goals_per_90": str(xg90),
            "expected_assists_per_90": str(xa90), "goals_scored": goals, "assists": assists,
            "expected_goals": str(xg90 * minutes / 90), "expected_assists": str(xa90 * minutes / 90),
            "expected_goals_conceded": "6.0", "bps": 100, "saves_per_90": 0, "yellow_cards": 0,
            "defensive_contribution_per_90": 0, "selected_by_percent": "10", "form": "4", "total_points": 20,
            "ep_next": "4", "penalties_order": None}


def live(xg_by_player, gws=(1, 2, 3, 4, 5)):
    """Per-gameweek stats: everyone plays 90, with the given xG a game."""
    return {gw: {"elements": [{"id": pid, "stats": {"minutes": 90, "starts": 1, "expected_goals": str(xg),
                                                    "expected_assists": "0.1", "goals_scored": 0, "assists": 0}}
                              for pid, xg in xg_by_player.items()]} for gw in gws}


def engine(live_by_gw=None, tweak=None):
    bs, fx = league()
    if tweak:
        tweak(bs)
    return xpts.Engine(bs, fx, live_by_gw=live_by_gw)


class TeamFormTests(unittest.TestCase):
    def test_a_club_creating_little_lately_is_a_weaker_attack_and_leakier_rivals_help_strikers(self):
        steady = {10 + t: 0.45 for t in TEAMS}
        slump = dict(steady); slump[12] = 0.05       # club 2's forward has stopped making chances
        base, form = engine(live(steady)), engine(live(slump))
        self.assertLess(form.team_rating(2)["attack"], base.team_rating(2)["attack"])
        self.assertLess(form.team_rating(2)["form_attack"], 1.0)
        # club 1's defenders face a blunter club 2: fewer goals expected against them
        fx = next(f for f in form.fixtures if f["event"] == 7 and 2 in (f["team_h"], f["team_a"]))
        other = fx["team_a"] if fx["team_h"] == 2 else fx["team_h"]
        self.assertLess(form.fixture_goals(other, 2, fx["team_h"] == other)[1],
                        base.fixture_goals(other, 2, fx["team_h"] == other)[1])

    def test_form_moves_a_rating_by_a_bounded_amount(self):
        wild = {10 + t: 0.45 for t in TEAMS}; wild[12] = 9.0
        e = engine(live(wild))
        lo, hi = xpts.TEAM_FORM_RANGE
        self.assertLessEqual(e.team_rating(2)["form_attack"], hi)
        self.assertGreaterEqual(e.team_rating(2)["form_attack"], lo)

    def test_no_live_data_means_no_form_adjustment(self):
        e = engine(None)
        self.assertEqual(e.team_rating(1)["form_attack"], 1.0)
        self.assertEqual(e.team_rating(1)["form_defence"], 1.0)


class PlayerFormTests(unittest.TestCase):
    def test_a_player_in_form_projects_more_than_his_season_rate(self):
        hot = {10 + t: 0.45 for t in TEAMS}; hot[99] = 0.9          # the midfielder has been flying
        cold = dict(hot); cold[99] = 0.0
        r_hot = engine(live(hot)).attacking_rates(engine(live(hot)).players[99])
        r_cold = engine(live(cold)).attacking_rates(engine(live(cold)).players[99])
        self.assertGreater(r_hot["xg90"], r_hot["xg90_season"])
        self.assertLess(r_cold["xg90"], r_cold["xg90_season"])
        self.assertLessEqual(r_hot["form_weight"], xpts.FORM_RATE_CAP)

    def test_real_goals_nudge_the_rate_but_only_a_little(self):
        def sharp(bs):
            next(p for p in bs["elements"] if p["id"] == 99)["goals_scored"] = 8   # 8 goals from 1.0 xG
        plain, finisher = engine(None), engine(None, sharp)
        a, b = plain.attacking_rates(plain.players[99]), finisher.attacking_rates(finisher.players[99])
        self.assertGreater(b["xg90"], a["xg90"])
        self.assertLessEqual(b["actual_weight"], xpts.FINISH_CAP)
        self.assertLess(b["xg90"], 8 / 5.0)          # nowhere near his raw 1.6 goals a game

    def test_chance_to_score_is_one_minus_exp_minus_xg(self):
        e = engine(None)
        fx = next(f for f in e.fixtures if f["event"] == 6 and 1 in (f["team_h"], f["team_a"]))
        leg = e.player_fixture_xpts(11, fx)
        self.assertAlmostEqual(leg["p_goal"], 1 - math.exp(-leg["xg"]), places=3)
        row = e.player_horizon(11, 6, 3)
        self.assertEqual(row["p_goal_next"], row["per_gw"][0]["p_goal"])

    def test_recent_minutes_drive_expected_minutes(self):
        benched = {10 + t: 0.45 for t in TEAMS}; benched[99] = 0.0
        lv = live(benched)
        for gw in lv:
            for el in lv[gw]["elements"]:
                if el["id"] == 99:
                    el["stats"].update(minutes=0, starts=0)
        e_bench, e_plain = engine(lv), engine(None)
        self.assertLess(e_bench.minutes_model(e_bench.players[99])["xmins"],
                        e_plain.minutes_model(e_plain.players[99])["xmins"])


def row(pid, pos, team, xp, chance=100, cost=50):
    return {"id": pid, "web_name": "R%d" % pid, "team": team, "team_short": "T%d" % team, "position": pos,
            "now_cost": cost, "price": cost / 10.0, "status": "a" if chance == 100 else "d",
            "selected_by_percent": 5.0, "chance_next": chance, "xpts_total": xp * 3,
            "per_gw": [{"gw": g, "xpts": xp, "fixtures": []} for g in (6, 7, 8)]}


class ChanceToPlayTests(unittest.TestCase):
    def squad(self):
        rows, owned, pid = [], [], 1
        for pos, n in ((1, 2), (2, 5), (3, 5), (4, 3)):
            for i in range(n):
                rows.append(row(pid, pos, 1 + pid % 10, 2.0))
                owned.append({"id": pid, "purchase_price": 50})
                pid += 1
        return rows, owned

    def test_a_doubtful_player_is_not_bought_at_75_but_is_when_allowed(self):
        rows, owned = self.squad()
        rows += [row(200, 3, 15, 9.0, chance=50), row(201, 3, 16, 7.0)]
        strict = solver.solve(rows, owned, 2.0, 1, 3, max_hits=0, min_chance=75)
        loose = solver.solve(rows, owned, 2.0, 1, 3, max_hits=0, min_chance=0)
        ins = lambda r: [x["id"] for x in r["gameweeks"][0]["transfers_in"]]
        self.assertTrue(strict["feasible"] and loose["feasible"])
        self.assertIn(201, ins(strict)); self.assertNotIn(200, ins(strict))
        self.assertIn(200, ins(loose))
        self.assertEqual([x["id"] for x in strict["passed_over"]], [200])

    def test_a_doubtful_player_already_owned_stays_but_never_wears_the_armband(self):
        rows, owned = self.squad()
        star = next(r for r in rows if r["position"] == 4)
        star.update(chance_next=50, status="d", per_gw=[dict(g, xpts=12.0) for g in star["per_gw"]], xpts_total=36)
        plan = solver.solve(rows, owned, 0.0, 1, 3, max_hits=0)
        gw = plan["gameweeks"][0]
        self.assertNotEqual(gw["captain"]["id"], star["id"])
        self.assertNotEqual(gw["vice_captain"]["id"], star["id"])
        self.assertIn(star["id"], [x["id"] for x in gw["starting_xi"]])
        self.assertEqual(plan["gameweeks"][1]["captain"]["id"], star["id"])   # later weeks: his odds recover


if __name__ == "__main__":
    unittest.main()
