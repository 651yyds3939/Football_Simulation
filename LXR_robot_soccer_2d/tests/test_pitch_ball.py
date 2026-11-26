"""Self-checks for the pitch, ball and rule models (15 checks)."""
import copy
import math
import random
import unittest
from dataclasses import replace

from robot_soccer.environment.ball import Ball, BallParams, ball_kick, ball_step
from robot_soccer.environment.pitch import PitchParams
from robot_soccer.environment.referee import referee_step
from robot_soccer.environment.world import Robot, world_init, world_step
from robot_soccer.geometry import norm, sign

DT = 0.02


def run_until_event(w, pp, bp):
    for _ in range(500):
        event = world_step(w, pp, bp, DT)
        if event is not None:
            return event
    return None


class PitchBallChecks(unittest.TestCase):
    def setUp(self):
        self.pp = PitchParams()
        self.bp = replace(BallParams(), kick_sig_dir=0.0, kick_sig_speed=0.0)   # no kick noise
        self.contact = self.bp.robot_radius + self.bp.radius
        self.rng = random.Random(42)

    def world_without_robots(self):
        w = world_init(self.pp)
        w.robots = []
        return w

    def test_01_pitch_equals_table_1(self):
        pp = self.pp
        values = [pp.length, pp.width, pp.goal_depth, pp.goal_width, pp.goal_height,
                  pp.goal_area_length, pp.goal_area_width, pp.penalty_mark_dist,
                  pp.centre_circle_d, pp.border_width, pp.penalty_area_length, pp.penalty_area_width]
        self.assertEqual(values, [9, 6, 0.6, 2.6, 1.2, 1, 3, 1.5, 1.5, 1, 2, 5])

    def test_02_ball_circumference_45_cm(self):
        self.assertAlmostEqual(2 * math.pi * self.bp.radius, 0.45, delta=1e-12)

    def test_03_ball_stops_where_the_formula_says(self):
        bp = self.bp
        v0 = 2.0
        b = Ball(vel=(v0, 0.0))
        for _ in range(1000):
            ball_step(b, [], self.pp, bp, DT)
        exact = v0 / bp.drag - bp.roll_decel / bp.drag ** 2 * math.log(1 + bp.drag * v0 / bp.roll_decel)
        self.assertEqual(b.vel, (0.0, 0.0))
        self.assertLess(abs(b.pos[0] / exact - 1), 0.03)
        self.assertEqual(b.pos[1], 0)

    def test_04_rolling_never_speeds_up_and_rest_stays_at_rest(self):
        b = Ball(vel=(1.5, 0.5))
        speeds = []
        for _ in range(200):
            ball_step(b, [], self.pp, self.bp, DT)
            speeds.append(norm(b.vel))
        self.assertTrue(all(y - x <= 1e-12 for x, y in zip(speeds, speeds[1:])))
        still = Ball(pos=(1.0, 1.0))
        for _ in range(50):
            ball_step(still, [], self.pp, self.bp, DT)
        self.assertEqual((still.pos, still.vel), ((1.0, 1.0), (0.0, 0.0)))

    def test_05_ball_bounces_off_a_standing_robot(self):
        robot = Robot((1.0, 0.0), math.pi, 2)
        b = Ball(vel=(1.5, 0.0))
        inside = False
        ratio = math.nan
        for _ in range(100):
            before = b.vel[0]
            ball_step(b, [robot], self.pp, self.bp, DT)
            inside = inside or norm((b.pos[0] - 1.0, b.pos[1])) < self.contact - 1e-9
            if b.vel[0] < 0:
                ratio = -b.vel[0] / before
                break
        self.assertFalse(inside)
        self.assertLess(abs(ratio - self.bp.e_robot), 0.03)
        self.assertEqual(b.vel[1], 0)
        self.assertEqual(b.last_touch_team, 2)

    def test_06_walking_robot_dribbles_the_ball(self):
        robot = Robot((0.0, 0.0), 0.0, 1, vel=(0.3, 0.0))
        b = Ball(pos=(self.contact + 0.01, 0.0))
        for _ in range(100):
            robot.pos = (robot.pos[0] + robot.vel[0] * DT, robot.pos[1])
            ball_step(b, [robot], self.pp, self.bp, DT)
            self.assertGreaterEqual(b.pos[0], robot.pos[0] + self.contact - 1e-9)
        self.assertGreater(b.pos[0], 0.6)
        self.assertLess(abs(b.pos[1]), 1e-12)
        self.assertEqual(b.last_touch_team, 1)

    def test_07_fast_ball_cannot_pass_through_a_post(self):
        pp = self.pp
        b = Ball(pos=(3.5, -pp.post_y), vel=(8.0, 0.0))
        x_max = -math.inf
        for _ in range(30):
            ball_step(b, [], pp, self.bp, DT)
            x_max = max(x_max, b.pos[0])
        self.assertLessEqual(x_max, pp.half_length - pp.post_radius - self.bp.radius + 1e-9)
        self.assertLess(b.vel[0], 0)

    def test_08_goal_scores_and_other_team_kicks_off(self):
        w = self.world_without_robots()
        w.ball.pos, w.ball.vel, w.ball.last_touch_team = (4.3, 0.0), (2.0, 0.0), 1
        ev = run_until_event(w, self.pp, self.bp)
        self.assertEqual((ev.type, ev.team), ('goal', 1))
        self.assertEqual(w.score, [1, 0])
        self.assertEqual((w.restart.type, w.restart.team), ('kickoff', 2))
        self.assertEqual((w.ball.pos, w.ball.vel), ((0.0, 0.0), (0.0, 0.0)))
        self.assertGreater(abs(ev.pos[0]), self.pp.half_length + self.bp.radius)

    def test_09_net_keeps_the_ball_inside_the_goal(self):
        pp, bp = self.pp, self.bp
        b = Ball(pos=(4.6, 0.0), vel=(3.0, 0.0))
        x_max = -math.inf
        for _ in range(100):
            ball_step(b, [], pp, bp, DT)
            x_max = max(x_max, b.pos[0])
        b2 = Ball(pos=(4.8, 0.0), vel=(0.0, 3.0))
        y_max = -math.inf
        for _ in range(100):
            ball_step(b2, [], pp, bp, DT)
            y_max = max(y_max, b2.pos[1])
        self.assertLessEqual(x_max, pp.half_length + pp.goal_depth - bp.radius + 1e-9)
        self.assertLessEqual(y_max, pp.post_y - bp.radius + 1e-9)

    def test_10_ball_cannot_enter_the_goal_from_behind(self):
        pp, bp = self.pp, self.bp
        b = Ball(pos=(pp.half_length + pp.goal_depth + 0.3, 0.0), vel=(-3.0, 0.0))
        x_min = math.inf
        for _ in range(100):
            ball_step(b, [], pp, bp, DT)
            x_min = min(x_min, b.pos[0])
        self.assertGreaterEqual(x_min, pp.half_length + pp.goal_depth + bp.radius - 1e-9)

    def test_11_goal_kick_or_corner_depends_on_last_touch(self):
        pp = self.pp
        w = self.world_without_robots()
        w.ball.pos, w.ball.vel = (4.4, 2.0), (2.0, 0.0)
        w1, w2 = copy.deepcopy(w), copy.deepcopy(w)
        w1.ball.last_touch_team = 1          # team 1 attacks +x
        w2.ball.last_touch_team = 2
        ev1 = run_until_event(w1, pp, self.bp)
        ev2 = run_until_event(w2, pp, self.bp)
        self.assertEqual((ev1.type, w1.restart.type, w1.restart.team),
                         ('out_goal_line', 'goal_kick', 2))
        self.assertEqual(w1.restart.pos, (pp.half_length - pp.goal_area_length, pp.goal_area_width / 2))
        self.assertEqual((ev2.type, w2.restart.type, w2.restart.team),
                         ('out_goal_line', 'corner_kick', 1))
        self.assertEqual(w2.restart.pos, (pp.half_length, pp.half_width))
        self.assertEqual(w1.score, [0, 0])

    def test_12_throw_in_where_the_ball_left(self):
        w = self.world_without_robots()
        w.ball.pos, w.ball.vel, w.ball.last_touch_team = (1.0, 2.9), (0.5, 1.0), 1
        ev = run_until_event(w, self.pp, self.bp)
        self.assertEqual((ev.type, w.restart.type, w.restart.team), ('out_touchline', 'throw_in', 2))
        self.assertEqual(w.restart.pos, (ev.pos[0], self.pp.half_width))

    def test_13_kick_limits(self):
        bp, c = self.bp, self.contact
        robot = Robot((0.0, 0.0), 0.0, 1)
        self.assertFalse(ball_kick(Ball(pos=(1.0, 0.0)), robot, 0, 0.0, 1.5, bp, self.rng))
        self.assertFalse(ball_kick(Ball(pos=(-(c + 0.05), 0.0)), robot, 0, 0.0, 1.5, bp, self.rng))
        b3, b4, b5 = (Ball(pos=(c + 0.05, 0.0)) for _ in range(3))
        self.assertTrue(ball_kick(b3, robot, 0, 0.3, 1.5, bp, self.rng))
        ball_kick(b4, robot, 0, 0.0, 10.0, bp, self.rng)
        ball_kick(b5, robot, 0, math.pi / 2, 1.0, bp, self.rng)
        self.assertAlmostEqual(norm(b3.vel), 1.5, delta=1e-12)
        self.assertAlmostEqual(math.atan2(b3.vel[1], b3.vel[0]), 0.3, delta=1e-12)
        self.assertEqual(b3.last_touch_team, 1)
        self.assertAlmostEqual(norm(b4.vel), bp.kick_speed_max, delta=1e-12)
        self.assertAlmostEqual(math.atan2(b5.vel[1], b5.vel[0]), bp.kick_dir_max, delta=1e-12)

    def test_14_ball_on_the_line_is_in_play(self):
        w = self.world_without_robots()
        w.ball.pos = (self.pp.half_length - 0.01, self.pp.half_width - 0.01)
        self.assertIsNone(referee_step(w, self.pp, self.bp))
        self.assertEqual((w.events, w.score), ([], [0, 0]))

    def test_15_world_has_four_robots_per_team_in_their_own_half(self):
        w = world_init(self.pp)
        self.assertEqual(len(w.robots), 8)
        for team in (1, 2):
            members = [r for r in w.robots if r.team == team]
            self.assertEqual(len(members), 4)
            self.assertTrue(all(sign(r.pos[0]) == sign(self.pp.own_goal_x(team)) for r in members))


if __name__ == '__main__':
    unittest.main()
