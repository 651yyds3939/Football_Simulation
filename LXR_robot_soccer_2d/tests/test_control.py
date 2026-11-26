"""Control verification against the scenario limits in docs/control_design.md."""
import math
import random
import unittest
from functools import partial
from unittest.mock import patch

from robot_soccer.behaviours.approach import walk_to
from robot_soccer.behaviours.navigation import navigate_to
from robot_soccer.environment.ball import Ball, BallParams, ball_kick
from robot_soccer.environment.pitch import PitchParams
from robot_soccer.environment.world import Robot
from robot_soccer.geometry import wrap_angle
from robot_soccer.robot.motion import RobotParams, RobotState, WalkCmd, robot_step
from robot_soccer.sensors.percept import Percept
from robot_soccer.simulations.match import play_match

from sim_runner import DT


class ControlChecks(unittest.TestCase):
    def setUp(self):
        self.rp = RobotParams()
        self.pp = PitchParams()
        self.rng = random.Random(42)

    def test_basic_walk_and_turn_commands_reach_but_do_not_exceed_limit(self):
        rp = self.rp
        cases = (
            ('forward', WalkCmd(vx=2), 0, rp.v_forward),
            ('backward', WalkCmd(vx=-2), 0, -rp.v_backward),
            ('left', WalkCmd(vy=2), 1, rp.v_side),
            ('right', WalkCmd(vy=-2), 1, -rp.v_side),
            ('turn left', WalkCmd(omega=5), 2, rp.turn_rate),
            ('turn right', WalkCmd(omega=-5), 2, -rp.turn_rate),
        )
        for label, cmd, axis, limit in cases:
            with self.subTest(action=label):
                robot, state = Robot((0, 0), 0, 1), RobotState()
                for _ in range(round(1 / DT)):
                    robot_step(robot, state, cmd, rp, DT, self.rng)
                    for i, velocity in enumerate(state.v_body):
                        if i == axis:
                            self.assertLessEqual(abs(velocity), abs(limit) + 1e-12)
                        else:
                            self.assertEqual(velocity, 0)
                self.assertAlmostEqual(state.v_body[axis], limit)
                actual_motion = (*robot.pos, robot.heading)[axis]
                self.assertGreater(actual_motion * limit, 0)

    def test_walk_limit_and_acceleration_hold_at_every_command_transition(self):
        rp = self.rp
        robot, state = Robot((0, 0), 0, 1), RobotState()
        sequence = [WalkCmd(vx=2), WalkCmd(omega=10), WalkCmd(vx=-2, vy=2, omega=-10),
                    WalkCmd(vx=2, vy=-2, omega=10), WalkCmd()]
        for cmd in sequence:
            for _ in range(round(1 / DT)):
                before = state.v_body[:2]
                robot_step(robot, state, cmd, rp, DT, self.rng)
                self._assert_walk_budget(state, rp)
                self.assertLessEqual(math.dist(before, state.v_body[:2]), rp.accel * DT + 1e-12)
        self.assertEqual(state.v_body, (0, 0, 0))

    def test_walk_limit_in_both_match_modes(self):
        def audited_step(robot, state, command, params, dt, rng):
            contact = robot_step(robot, state, command, params, dt, rng)
            self._assert_walk_budget(state, params)
            return contact

        for use_navigation in (False, True):
            with self.subTest(use_navigation=use_navigation), patch(
                'robot_soccer.simulations.match.robot_step', new=audited_step
            ):
                play_match(20, control_design=use_navigation)

    def test_kick_holds_pose_and_touches_the_ball_once_then_releases(self):
        rp = self.rp
        robot, state = Robot((0, 0), 0, 1), RobotState(v_body=(0.15, 0, 0.2))
        ball = Ball(pos=(0.25, 0))
        bp = BallParams(kick_sig_dir=0, kick_sig_speed=0)
        contacts = []
        for step in range(1, round(rp.kick_time / DT) + 1):
            cmd = WalkCmd(vx=1, omega=1, kick=(step == 1), kick_dir=0, kick_speed=1)
            if robot_step(robot, state, cmd, rp, DT, self.rng):
                contacts.append(step * DT)
                self.assertTrue(ball_kick(ball, robot, 0, state.kick_dir, state.kick_speed, bp, self.rng))
            self.assertEqual((robot.pos, robot.heading, state.v_body), ((0, 0), 0, (0, 0, 0)))
            self.assertEqual(state.kick_t is None, step * DT >= rp.kick_time)
            if step * DT < rp.kick_contact:
                self.assertIsNone(ball.last_touch_robot)
        self.assertEqual(len(contacts), 1)
        self.assertAlmostEqual(contacts[0], rp.kick_contact)
        self.assertEqual((ball.last_touch_robot, ball.vel), (0, (1, 0)))
        self.assertFalse(robot_step(robot, state, WalkCmd(vx=1), rp, DT, self.rng))
        self.assertGreater(robot.pos[0], 0)

    def test_walk_to_reaches_fixed_targets_and_headings(self):
        cases = (
            ('pure side step', (-4.1, 0), 0, (-4.1, 0.6), 0, 7),
            ('diagonal and turn', (-3, -1), -0.3, (-2.35, -1.45), 0.2, 8),
            ('forward and turn', (0, 0), 0.7, (1, 0), 0, 8),
            ('heading across the angle wrap', (0.3, 0.1), -3.05, (-0.7, 0.1), 3.05, 8),
        )
        for name, start, heading, target, face, timeout in cases:
            with self.subTest(scenario=name):
                self._drive_to(walk_to, start, heading, target, face, timeout)

    def test_detour_uses_mate_or_opponent_observations_and_respects_pitch(self):
        guide = partial(navigate_to, pp=self.pp, rp=self.rp)
        for label, y in (('mates', 0), ('opponents', 2.55)):
            with self.subTest(observation=label):
                obstacle = (0, y)
                path = self._drive_to(guide, (-1, y), 0, (1, y), 0, 16, {label: [obstacle]})
                self.assertGreaterEqual(min(math.dist(pos, obstacle) for pos in path), 0.41)
                for x, py in path:
                    self.assertLessEqual(abs(x), self.pp.half_length - self.rp.radius)
                    self.assertLessEqual(abs(py), self.pp.half_width - self.rp.radius)
                if label == 'opponents':
                    self.assertLess(min(py for _, py in path), y - 0.41)

    def test_navigation_escapes_when_already_inside_clearance_margin(self):
        guide = partial(navigate_to, pp=self.pp, rp=self.rp)
        cases = (
            ('diagonal teammate', (0, 0), (1.4, 0), [(0.15, 0.32)], []),
            ('head-on teammate', (0, 0), (1.4, 0), [(0.32, 0)], []),
            ('opponent near touchline', (0, 2.68), (1.4, 2.68), [], [(0.32, 2.68)]),
            ('two staggered players', (0, 0), (1.4, 0), [(0.32, 0)], [(0.8, 0.35)]),
        )
        for label, start, target, mates, opponents in cases:
            with self.subTest(scenario=label):
                path = self._drive_to(guide, start, 0, target, 0, 14, dict(mates=mates, opponents=opponents))
                self.assertGreaterEqual(min(math.dist(pos, obstacle) for pos in path
                                            for obstacle in mates + opponents), 2 * self.rp.radius)
                self.assertLessEqual(max(abs(y) for _, y in path), self.pp.half_width - self.rp.radius)

    def test_navigation_can_approach_occupied_destination_then_continue_when_clear(self):
        robot, state = Robot((-0.8, 0), 0, 1), RobotState()
        guide = partial(navigate_to, pp=self.pp, rp=self.rp)
        for _ in range(round(7 / DT)):
            p = Percept(self_pos=robot.pos, self_heading=robot.heading, mates=[(0, 0)])
            robot_step(robot, state, guide(p, (0, 0), 0), self.rp, DT, self.rng)
            self.assertGreaterEqual(math.hypot(*robot.pos), 0.41 - 1e-9)
        self.assertLess(math.hypot(*robot.pos), 0.45)
        for _ in range(round(5 / DT)):
            p = Percept(self_pos=robot.pos, self_heading=robot.heading)
            robot_step(robot, state, guide(p, (0, 0), 0), self.rp, DT, self.rng)
        self.assertLess(math.hypot(*robot.pos), 0.05)

    def _assert_walk_budget(self, state, params):
        vx, vy, omega = state.v_body
        x_limit = params.v_forward if vx >= 0 else params.v_backward
        self.assertLessEqual(math.hypot(vx / x_limit, vy / params.v_side, omega / params.turn_rate),
                             1 + 1e-12)

    def _drive_to(self, guide, start, heading, target, face, timeout, observations=None):
        """Drive with a supplied percept. The truth is used only to judge the test."""
        robot, state = Robot(start, heading, 1), RobotState()
        stable_steps = 0
        path = [start]
        for _ in range(round(timeout / DT)):
            p = Percept(self_pos=robot.pos, self_heading=robot.heading, **(observations or {}))
            robot_step(robot, state, guide(p, target, face), self.rp, DT, self.rng)
            path.append(robot.pos)
            error = math.dist(robot.pos, target)
            heading_error = abs(wrap_angle(robot.heading - face))
            if error <= 0.05 and heading_error <= math.radians(5):
                stable_steps += 1
                if stable_steps >= round(0.2 / DT):
                    return path
            else:
                stable_steps = 0
        self.fail(f'Not settled within {timeout} s: {error:.3f} m, {math.degrees(heading_error):.1f}°')
