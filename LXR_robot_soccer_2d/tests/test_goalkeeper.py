"""Goalkeeper targets and state transitions driven by constructed percepts."""
import math
import unittest
from dataclasses import FrozenInstanceError, replace

from robot_soccer.behaviours.approach import walk_to
from robot_soccer.behaviours.ball_prediction import ball_path
from robot_soccer.behaviours.goalkeeper import DEFAULT_KEEPER, MATLAB_KEEPER, goalkeeper_behaviour
from robot_soccer.environment.ball import BallParams
from robot_soccer.environment.pitch import PitchParams
from robot_soccer.geometry import wrap_angle
from robot_soccer.robot.motion import RobotParams, WalkCmd
from robot_soccer.sensors.percept import Percept
from robot_soccer.simulations.keeper_saves import generate_shots, run_shots


PP, BP, RP = PitchParams(), BallParams(), RobotParams()


def image(t, ball, *, pose=(4.15, 0.0), team=2, opponents=(), odom=(0.0, 0.0, 0.0)):
    heading = math.pi if team == 2 else 0.0
    dx, dy = ball[0] - pose[0], ball[1] - pose[1]
    return Percept(t_measured=t, self_pos=pose, self_heading=heading, odom=odom,
                   ball_visible=True, ball_pos=ball, ball_last_seen=t,
                   ball_range=math.hypot(dx, dy),
                   ball_bearing=wrap_angle(math.atan2(dy, dx) - heading),
                   opponents=list(opponents))


class GoalkeeperTests(unittest.TestCase):
    def decide(self, percept, memory=None, team=2, *, params=DEFAULT_KEEPER, odom=None):
        targets = []

        def guide(p, target, face):
            targets.append((target, face))
            return walk_to(p, target, face)

        _, memory = goalkeeper_behaviour(percept, memory, team, PP, BP, RP, odom,
                                         params=params, guide=guide)
        return memory, targets

    def roll(self, start, velocity, *, pose, team=2, params=DEFAULT_KEEPER, odom=None):
        times = [0.0, 0.1, 0.2]
        points, _, _, _ = ball_path(start, velocity, times, BP)
        memory = None
        for t, position in zip(times, points):
            memory, targets = self.decide(image(t, position, pose=pose, team=team),
                                          memory, team, params=params, odom=odom)
        return memory, targets

    def test_home_state_accepts_an_empty_percept_and_returns_after_losing_the_ball(self):
        cmd, memory = goalkeeper_behaviour(Percept(), None, 2, PP, BP, RP)
        self.assertEqual((cmd, memory.state), (WalkCmd(), 'home'))

        pose = (3.4, 0.6)
        memory, _ = self.decide(image(0.0, (2.0, 0.6), pose=pose), memory)
        self.assertEqual(memory.state, 'guard')
        no_ball = Percept(t_measured=3.1, self_pos=pose, self_heading=math.pi)
        memory, [(target, face)] = self.decide(no_ball, memory)
        self.assertEqual(memory.state, 'home')
        self.assertEqual(target, (PP.own_goal_x(2) - DEFAULT_KEEPER.home_depth, 0.0))
        self.assertAlmostEqual(face, math.pi)

    def test_guard_keeps_its_target_in_front_until_estimate_exceeds_a_ball_radius(self):
        for team, side in ((1, -1), (2, 1)):
            goal_x = PP.own_goal_x(team)
            pose = (goal_x - side * 0.35, 0.0)
            limit = goal_x + side * BP.radius
            for estimated_x in (goal_x, goal_x + side * BP.radius / 2, limit):
                with self.subTest(team=team, estimated_x=estimated_x):
                    memory, [(target, _)] = self.decide(
                        image(0.0, (estimated_x, 0.3), pose=pose, team=team), team=team)
                    self.assertEqual(memory.state, 'guard')
                    self.assertGreater(side * (goal_x - target[0]), 0)
                    self.assertAlmostEqual(side * (goal_x - target[0]),
                                           0.5 * 0.05 / math.hypot(0.05, 0.3))
            outside = math.nextafter(limit, side * math.inf)
            memory, [(target, _)] = self.decide(
                image(0.0, (outside, 0.3), pose=pose, team=team), team=team)
            self.assertEqual(memory.state, 'home')
            self.assertEqual(target, (pose[0], 0.0))

    def test_guard_stays_on_ray_and_respects_gap_when_feasible(self):
        for team, side in ((1, -1), (2, 1)):
            goal_x = PP.own_goal_x(team)
            keeper = (goal_x - side * 0.35, 0.0)
            for depth, y, radius in ((1.4, 0.0, 0.9), (0.2, 0.1, 0.5), (4.0, 1.0, 1.5),
                                     (0.3, -2.0, 1.2 * math.hypot(0.3, 2.0) / 2.0)):
                with self.subTest(team=team, depth=depth, y=y):
                    ball = (goal_x - side * depth, y)
                    memory, [((target_x, target_y), face)] = self.decide(
                        image(0.0, ball, pose=keeper, team=team), team=team)
                    self.assertEqual(memory.state, 'guard')
                    self.assertAlmostEqual((target_x - goal_x) * y + side * target_y * depth, 0)
                    self.assertAlmostEqual(math.hypot(target_x - goal_x, target_y), radius)
                    self.assertGreaterEqual(side * (goal_x - target_x), 0)
                    self.assertLessEqual(side * (goal_x - target_x), PP.penalty_area_length)
                    self.assertLessEqual(abs(target_y), min(1.2, PP.penalty_area_width / 2) + 1e-12)
                    self.assertAlmostEqual(face, math.atan2(y - keeper[1], ball[0] - keeper[0]))

    def test_intercept_holds_odometry_corrected_depth_on_both_sides(self):
        for team, side in ((1, -1), (2, 1)):
            with self.subTest(team=team):
                memory, [((x, y), _)] = self.roll(
                    (side * 2.7, 0.1), (side * 1.9, 0.3), pose=(side * 3.1, 0.0),
                    team=team, odom=(-0.2, 0.0, 0.0))
                self.assertEqual(memory.state, 'intercept')
                self.assertAlmostEqual(x, side * 3.3)
                self.assertAlmostEqual(y, 0.1 + (3.3 - 2.7) * 0.3 / 1.9)

    def test_balls_that_stop_before_goal_or_go_wide_do_not_trigger_intercept(self):
        for start, velocity in (((2.7, 0.1), (0.9, 0.0)),
                                ((2.7, 0.1), (1.25, 0.0)),
                                ((3.65, 0.15), (0.7, 1.2))):
            with self.subTest(start=start, velocity=velocity):
                memory, _ = self.roll(start, velocity, pose=(3.3, 0.0))
                self.assertEqual(memory.state, 'guard')

        # This wide ball also passes within the old 0.8 m clearance radius.
        memory, _ = self.roll((3.65, 0.15), (0.7, 1.2), pose=(4.15, 0.0))
        self.assertEqual(memory.state, 'guard')

    def test_clear_requires_slow_ball_in_box_and_a_clear_lead(self):
        for ball, opponents, expected in (
            ((3.4, 0.0), ((3.1, 0.1),), 'guard'),  # Opponent is closer.
            ((3.4, 0.0), ((2.6, 0.0),), 'guard'),  # Keeper leads by only 0.2 s.
            ((2.8, 0.0), ((1.1, 0.0),), 'clear'),  # Keeper ahead, even outside 0.8 m.
            ((2.8, 0.0), (), 'clear'),
            ((2.4, 0.0), (), 'guard'),             # Beyond the penalty area.
        ):
            with self.subTest(ball=ball, opponents=opponents):
                memory = None
                for t in (0.0, 0.1, 0.2):
                    memory, _ = self.decide(image(t, ball, opponents=opponents), memory)
                self.assertEqual(memory.state, expected)

    def test_clear_hysteresis_requires_a_clear_opponent_lead_to_abandon(self):
        ball = (3.4, 0.0)
        memory = None
        for t in (0.0, 0.1, 0.2):
            memory, _ = self.decide(image(t, ball), memory)
        self.assertEqual(memory.state, 'clear')
        memory, _ = self.decide(image(0.3, ball, opponents=((2.7, 0.0),)), memory)
        self.assertEqual(memory.state, 'clear')
        memory, _ = self.decide(image(0.4, ball, opponents=((2.85, 0.0),)), memory)
        self.assertEqual(memory.state, 'guard')

    def test_clear_returns_to_guard_when_ball_leaves_box_or_speeds_up(self):
        for initial, changed in (
            ((2.51, 0.0), (2.49, 0.0)),  # Small motion across the front edge.
            ((3.4, 2.49), (3.4, 2.51)),  # Small motion across the side edge.
            ((3.4, 0.0), (3.1, 0.0)),    # Fast motion away from goal, inside the box.
        ):
            with self.subTest(initial=initial, changed=changed):
                memory = None
                for t in (0.0, 0.1, 0.2):
                    memory, _ = self.decide(image(t, initial), memory)
                self.assertEqual(memory.state, 'clear')
                memory, _ = self.decide(image(0.3, changed), memory)
                self.assertEqual(memory.state, 'guard')

    def test_slow_ball_that_can_reach_goal_is_intercepted_before_clearance(self):
        memory, [(target, _)] = self.roll((4.37, 0.18), (0.45, 0.0), pose=(4.47, 0.0))
        self.assertEqual(memory.state, 'intercept')
        self.assertAlmostEqual(target[0], 4.47)
        self.assertAlmostEqual(target[1], 0.18)

    def test_team_one_clears_upfield_from_its_own_penalty_area(self):
        ball = (-3.4, -0.2)
        direction = math.atan2(-DEFAULT_KEEPER.clear_side, 1)
        stand_off = RP.radius + BP.radius + 0.02
        pose = (ball[0] - stand_off * math.cos(direction),
                ball[1] - stand_off * math.sin(direction))
        memory = None
        for t in (0.0, 0.1, 0.2):
            percept = image(t, ball, pose=pose, team=1, opponents=((-2.6, -0.2),))
            percept = replace(percept, self_heading=direction, ball_bearing=0.0)
            command, memory = goalkeeper_behaviour(percept, memory, 1, PP, BP, RP)
        self.assertEqual(memory.state, 'clear')
        self.assertTrue(command.kick)
        self.assertGreater(math.cos(command.kick_dir), 0)
        self.assertLess(math.sin(command.kick_dir), 0)

    def test_recent_opponents_are_retained_and_expire_from_their_image_time(self):
        ball = (3.4, 0.0)
        memory = None
        for t in (0.0, 0.1, 0.2):
            percept = image(t, ball, opponents=((3.1, 0.1),))
            memory, _ = self.decide(percept, memory)
        for _ in range(5):
            memory, _ = self.decide(percept, memory)
        self.assertEqual(len(memory.opponent_frames), 3)
        for t in (1.8, 2.0, 2.1, 2.19):
            memory, _ = self.decide(image(t, ball, opponents=((2.1, 0.0),)), memory)
        self.assertEqual(memory.state, 'guard')
        memory, _ = self.decide(image(2.21, ball), memory)
        self.assertEqual(memory.state, 'clear')

    def test_matlab_configuration_keeps_fixed_intercept_and_parameter_objects_are_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_KEEPER.gap = 0.8
        memory, [(target, _)] = self.roll((2.7, 0.1), (1.9, 0.3), pose=(3.3, 0.0),
                                          params=MATLAB_KEEPER)
        self.assertEqual(memory.state, 'intercept')
        self.assertAlmostEqual(target[0], 4.1)


class GoalkeeperReplayTests(unittest.TestCase):
    def test_refined_keeper_replays_the_same_seeded_shots(self):
        shots = generate_shots(8, seed=2, aim='corner')
        first = run_shots(shots, 'realistic', 'updated')
        repeated_shots = generate_shots(8, seed=2, aim='corner')
        self.assertEqual(shots, repeated_shots)
        self.assertEqual(first, run_shots(repeated_shots, 'realistic', 'updated'))


if __name__ == '__main__':
    unittest.main()
