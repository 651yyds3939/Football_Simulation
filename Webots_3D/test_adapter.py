"""Pure Python regression checks for the shared tactical interface."""
import math
from types import SimpleNamespace
import unittest

from Webots_3D.adapter import SharedTactics, WebotsMotionProfile, WebotsNavigation
from Four_vs_Four.backend.Wenao.controllers.Utils.DefensivePlan import route
from Four_vs_Four.backend.Wenao.controllers.Utils.TeamPolicy import Decision, TeamPolicy


def world(phase="PLAYING"):
    names = {
        "RedForwardA": (-.24, 0., 0.),
        "RedForwardB": (-.37, .7, 0.),
        "RedDefender": (-1.7, .04, 0.),
        "RedGoalkeeper": (-4.14, 0., 0.),
        "BlueForwardA": (.27, 0., math.pi),
        "BlueForwardB": (1.35, .75, math.pi),
        "BlueDefender": (2.1, .2, math.pi),
        "BlueGoalkeeper": (4.14, 0., math.pi),
    }
    return {"time": 4.0, "robots": {
        name: {"position": [x, y, .334], "yaw": yaw, "standing": True}
        for name, (x, y, yaw) in names.items()
    }, "ball": {"position": [0., 0., .07], "velocity": [0., 0., 0.]}, "penalties": {},
        "match": {"phase": phase, "red_direction": 1, "released": phase == "PLAYING",
                  "last_touch": None, "restart_point": [0., 0., .07], "restart_team": None,
                  "restart": "DROP_BALL"}}


def policy(mode="flow", player="RedForwardB"):
    controller = SimpleNamespace(name=player, policy=TeamPolicy(player), pass_intent=None)
    return SharedTactics(controller, mode, TeamPolicy, Decision)


class AdapterTests(unittest.TestCase):
    def test_wait_phase_uses_original_controller(self):
        p = policy()
        snapshot = world("SET")
        p.prepare(snapshot)
        self.assertEqual(p.decide(snapshot).behaviour, "WAIT")

    def test_same_snapshot_reuses_one_update(self):
        p = policy()
        snapshot = world()
        p.prepare(snapshot)
        first = p.plan
        p.prepare(snapshot)
        self.assertIs(p.plan, first)

    def test_support_uses_the_shared_planner(self):
        p = policy("support")
        snapshot = world()
        snapshot["robots"]["BlueForwardA"]["position"] = [1.3, 1.5, .334]
        p.prepare(snapshot)
        self.assertIn(p.decide(snapshot).behaviour, {"OFFER_OUTLET", "DOUBLE_COVER"})

    def test_keeper_cover_uses_actual_motion_primitives(self):
        nav = WebotsNavigation(None, route, None, None)
        decision = Decision("KEEPER_SHOT", (-4.12, 0.32), (-3.4, 0))
        action, stage = nav.choose(decision, (-4.12, 0), 0, (-3.4, 0))
        self.assertEqual(action, "step_left")
        self.assertEqual(stage, "TRANSFER_GOAL_COVER")

    def test_short_pass_profile_does_not_use_planar_power(self):
        for mode in ("support", "flow", "passing"):
            p = policy(mode)
            self.assertFalse(p.flows.tap_enabled)
            self.assertFalse(p.flows.use_wider_pass)
            self.assertFalse(p.flows.allow_trap)
        self.assertLess(WebotsMotionProfile().pass_range, .4)

    def test_opponent_in_lane_blocks_aligned_pass(self):
        p = policy("passing", "RedForwardA")
        snapshot = world()
        p.controller.observation = SimpleNamespace(world=snapshot)
        physical = SimpleNamespace(choose=lambda *_: ("pass", "KICK_READY"))
        nav = WebotsNavigation(physical, route, p.controller, p)
        order = Decision("TRANSFER_PASS", (0.0, 0.0), (0.48, 0.0), "pass", "RedForwardB")
        args = (order, (-0.19, -0.05), 0.0, (0.0, 0.0))
        self.assertEqual(nav.choose(*args), ("stand", "TRANSFER_PASS_LANE_BLOCKED"))
        snapshot["robots"]["BlueForwardA"]["position"] = [1.6, 0.8, .334]
        self.assertEqual(nav.choose(*args), ("pass", "KICK_READY"))


if __name__ == "__main__":
    unittest.main()
