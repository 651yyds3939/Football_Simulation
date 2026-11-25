"""Regression checks for the current 2D match entry point."""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Four_vs_Four"))
from run import Model, create_match, play
from contact_motion import foot_entry, stop_conflicting_moves
from Utils.TeamNavigation import FlowNavigator
from Utils.TeamPolicy import Decision


def open_play(sim, direction=1):
    referee = sim.engine
    referee.phase = "PLAYING"
    referee.half_started = 0.0
    referee.red_direction = direction
    referee.restart = "DROP_BALL"
    referee.restart_team = None
    referee.restart_goal_guard = referee.kickoff_restriction = False
    referee.released = True


class MatchChecks(unittest.TestCase):
    def test_off_ball_player_makes_space_in_a_stationary_crowd(self):
        sim = create_match(27)
        ball = (0.0, 0.0)
        for name, point in {
            "RedDefender": (0.43, 0.0),
            "RedForwardA": (0.55, 0.30),
            "BlueDefender": (-0.20, 0.0),
        }.items():
            sim.players[name]["position"] = [*point, 0.334]
        decisions = {}
        sim.flow.open_crowded_lane(sim.players, ball, 0, 0, decisions, {}, None)
        sim.flow.open_crowded_lane(sim.players, ball, 0, 4.2, decisions, {}, None)
        self.assertEqual(decisions["RedForwardA"].behaviour, "MAKE_SPACE")
        self.assertNotIn("RedDefender", decisions)

    def test_demo_ball_still_moves_near_full_time(self):
        _, scene = play(294034, "flow", "flow", Model(), record=True)
        tail = [frame for frame in scene["frames"] if frame["t"] >= 560]
        self.assertTrue(
            any(math.dist(frame["ball"], tail[0]["ball"]) > 0.30 for frame in tail)
        )
        self.assertEqual(tail[-1]["match"]["phase"], "FINISHED")

    def test_pass_accounts_for_an_opponent_running_into_the_lane(self):
        flow = create_match(27).flow
        ball, target = (0.0, 0.0), (1.2, 0.0)
        rival = [(1.2, 0.52)]
        self.assertTrue(flow.safe_pass_path(ball, target, rival, 0.0))
        self.assertFalse(flow.safe_pass_path(ball, target, rival, 1.45))
        self.assertTrue(flow.safe_pass_path(ball, target, [(1.2, 1.0)], 1.45))

    def test_cancelled_pass_does_not_move_ball_or_retain_intent(self):
        sim = create_match(27)
        open_play(sim)
        sender, receiver = "RedForwardA", "RedForwardB"
        sim.ball = [0.0, 0.0, 0.07]
        sim.players[sender].update(position=[-0.2, 0.0, 0.334], yaw=0.0)
        sim.players[receiver].update(position=[1.3, 0.0, 0.334])
        sim.players["BlueDefender"].update(position=[0.7, 0.1, 0.334])
        sim.pass_intent = {"sender": sender, "stage": "preparing"}
        decision = Decision(
            "TOUCH_PASS", (-0.2, 0.0), (1.2, 0.0), "tap", receiver, kick_distance=1.2
        )
        sim._finish_kick(sender, decision)
        self.assertEqual(sim.velocity, [0.0, 0.0, 0.0])
        self.assertIsNone(sim.pass_intent)
        self.assertEqual(sim.events[-1]["reason"], "interception_risk")

    def test_both_teams_use_the_same_navigation_path(self):
        sim = create_match(27)
        self.assertTrue(all(isinstance(nav, FlowNavigator) for nav in sim.navigators.values()))

    def test_all_eight_reset_in_the_same_tick_as_a_goal(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                sim = create_match(27)
                open_play(sim, direction)
                sim.engine.previous = [direction * 4.51, 0.21, 0.07]
                sim.ball = [direction * 4.62, 0.21, 0.07]
                for i, robot in enumerate(sim.players.values()):
                    robot["position"] = [-0.30 + i * 0.43, 2.4, 0.334]
                    robot["yaw"] = 1.1
                sim.pending_pass = sim.pass_intent = {
                    "sender": "RedForwardA",
                    "receiver": "RedForwardB",
                }
                sim.kicking["RedForwardA"] = (
                    10.0,
                    Decision("SHOOT", (0.0, 0.0), (4.5, 0.0), "shoot"),
                )
                sim.step()
                self.assertEqual(sim.engine.score, [1, 0])
                self.assertEqual(sim.engine.phase, "READY")
                self.assertEqual(sim.engine.restart_team, "BLUE")
                self.assertEqual(sim.ball, [0, 0, 0.07])
                self.assertFalse(sim.kicking)
                self.assertIsNone(sim.pass_intent)
                self.assertIsNone(sim.pending_pass)
                for name, robot in sim.players.items():
                    policy = sim.policies[name]
                    attack = sim.engine.direction(policy.team)
                    home = (-attack * 0.3, 0.0) if name == "BlueForwardA" else policy.home(attack)
                    self.assertEqual(tuple(robot["position"][:2]), home)
                self.assertIn("goal_formation", [event["event"] for event in sim.events])

    def test_body_contact_leaves_idle_player_in_place(self):
        players = {
            "mover": {"position": [-0.32, 0.0, 0.334]},
            "idle": {"position": [0.0, 0.0, 0.334]},
        }
        positions = {"mover": [-0.18, 0.0, 0.334], "idle": [0.0, 0.0, 0.334]}
        blocked = stop_conflicting_moves(tuple(players), players, positions, 0.30)
        self.assertEqual(blocked, {"mover"})
        self.assertEqual(positions["idle"], [0.0, 0.0, 0.334])
        self.assertAlmostEqual(positions["mover"][0], -0.30)

    def test_head_on_contact_stops_both_without_crossing(self):
        players = {"a": {"position": [-0.19, 0.0, 0.334]}, "b": {"position": [0.19, 0.0, 0.334]}}
        positions = {"a": [0.13, 0.0, 0.334], "b": [-0.13, 0.0, 0.334]}
        blocked = stop_conflicting_moves(tuple(players), players, positions, 0.30)
        self.assertEqual(blocked, {"a", "b"})
        self.assertAlmostEqual(positions["b"][0] - positions["a"][0], 0.30)

    def test_receive_window_requires_actual_forward_foot_entry(self):
        self.assertIsNone(foot_entry((-0.5, 0.2), (0.3, 0), (0.0, 0.0), math.pi))
        self.assertIsNone(foot_entry((0.1, 0), (0.3, 0), (0.0, 0.0), math.pi))
        self.assertAlmostEqual(foot_entry((-0.5, 0.06), (0.3, 0), (0.0, 0.0), math.pi), 0.205 / 0.3)

    def test_trapping_pass_counts_only_on_contact(self):
        sim = create_match(27, model=Model(dt=0.04))
        open_play(sim)
        for robot in sim.players.values():
            robot["position"] = [3.4, 2.0, 0.334]
        receiver = "RedForwardB"
        sim.players[receiver].update(position=[0.51, 0.0, 0.334], yaw=math.pi)
        sim.ball = [0.20, 0.03, 0.07]
        sim.velocity = [0.65, 0.0, 0.0]
        sim.pending_pass = {"sender": "RedForwardA", "receiver": receiver, "expires": 2.0}
        sim.active_receiver = receiver
        sim._roll_ball()
        self.assertEqual(sim.velocity, [0.0, 0.0, 0.0])
        self.assertEqual(sim.previous_foot_contact, receiver)
        result = next(event for event in sim.events if event["event"] == "pass_result")
        self.assertEqual(result["contact_source"], "foot_trap")
        self.assertTrue(result["completed"])

    def test_boundary_recovery_selects_a_reachable_stance(self):
        sim = create_match(27)
        open_play(sim)
        ball = (-4.51, -2.24)
        defender = "RedDefender"
        opponent = "BlueForwardB"
        sim.players[defender].update(position=[-4.254, -2.176, 0.334], yaw=0.138)
        sim.players[opponent].update(position=[-4.283, -2.548, 0.334], yaw=1.398)
        sim.flow.anchor = (ball, 0.0, (defender, opponent))
        orders = {}
        self.assertTrue(
            sim.flow.free_boundary_ball(
                {defender: sim.players[defender]},
                {opponent: sim.players[opponent]},
                ball,
                (0.0, 0.0),
                1,
                5.0,
                orders,
                {},
            )
        )
        decision = orders[defender]
        self.assertEqual(decision.behaviour, "EDGE_RECOVERY")
        self.assertLessEqual(abs(decision.target[0]), 4.387)
        self.assertLessEqual(abs(decision.target[1]), 2.875)

    def test_goalkeeper_blocks_before_turning(self):
        sim = create_match(27, red="flow", blue="coordinated", model=Model(dt=0.04))
        open_play(sim)
        sim.players["RedGoalkeeper"].update(position=[-4.3753, 0.6194, 0.334], yaw=-1.675)
        sim.ball = [-4.2456, 0.8491, 0.07]
        sim.velocity = [-0.533, -0.0266, 0.0]
        sim.engine.restart_point = sim.ball.copy()
        sim.step()
        self.assertEqual(sim.last_decisions["RedGoalkeeper"], "KEEPER_SHOT")
        self.assertIn(sim.last_actions["RedGoalkeeper"], ("walk", "back", "step_left", "step_right"))
        for _ in range(34):
            sim.step()
        self.assertEqual(sim.engine.score, [0, 0])
        self.assertTrue(
            any(
                event["event"] == "contact" and event["robot"] == "RedGoalkeeper"
                for event in sim.events
            )
        )


if __name__ == "__main__":
    unittest.main()
