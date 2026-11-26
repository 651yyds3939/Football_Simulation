"""Self-checks for the motion model and the behaviours (19 checks)."""
import io
import math
import random
import unittest
from contextlib import redirect_stdout
from dataclasses import replace

from robot_soccer.behaviours.approach import odometry_update
from robot_soccer.behaviours.ball_prediction import ball_path, intercept_point, pass_speed, track_ball
from robot_soccer.behaviours.goalkeeper import goalkeeper_behaviour
from robot_soccer.behaviours.striker import striker_behaviour
from robot_soccer.environment.ball import Ball, BallParams, ball_step
from robot_soccer.environment.pitch import PitchParams
from robot_soccer.environment.world import Robot, World, world_init
from robot_soccer.geometry import is_finite, norm, wrap_angle
from robot_soccer.robot.motion import (RobotParams, RobotState, WalkCmd, keep_apart, robot_state_init,
                                       robot_step)
from robot_soccer.sensors.params import SensorParams
from robot_soccer.sensors.percept import Percept
from robot_soccer.sensors.sensor_layer import sensor_init, sensor_step
from robot_soccer.simulations.striker_keeper_drill import striker_keeper_drill

from sim_runner import DT, run_sim

OUTCOMES = {'goal', 'saved', 'missed', 'timeout'}


def drive(cmd, rp, n_steps, rng):
    """One robot from the origin, facing +x, given the same command n_steps times."""
    robot = Robot((0.0, 0.0), 0.0, 1)
    rs = RobotState()
    for _ in range(n_steps):
        robot_step(robot, rs, cmd, rp, DT, rng)
    return robot, rs


def keeper_reaction(ball0, vel0, pp, bp, rp):
    """Keeper sees a ball rolling in six images; returns its state and wanted world y velocity."""
    pk = Percept(self_pos=(pp.own_goal_x(2) - 0.4, 0.0), self_heading=math.pi, ball_visible=True)
    mem = None
    for i in range(6):
        pk.t_measured = 0.1 * i
        pk.ball_pos = ball_path(ball0, vel0, [0.1 * i], bp)[0][0]
        d = (pk.ball_pos[0] - pk.self_pos[0], pk.ball_pos[1] - pk.self_pos[1])
        pk.ball_range = norm(d)
        pk.ball_bearing = wrap_angle(math.atan2(d[1], d[0]) - pk.self_heading)
        cmd, mem = goalkeeper_behaviour(pk, mem, 2, pp, bp, rp)
    return mem.state, math.sin(pk.self_heading) * cmd.vx + math.cos(pk.self_heading) * cmd.vy


class StrikerKeeperChecks(unittest.TestCase):
    def setUp(self):
        self.pp = PitchParams()
        self.bp = BallParams()
        self.rp = RobotParams()
        self.spp = SensorParams(mode='perfect')
        self.rng = random.Random(42)

    def quiet_drill(self, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            return striker_keeper_drill(*args, **kwargs)

    def test_01_walk_speed_and_acceleration_limits(self):
        rp = self.rp
        robot = Robot((0.0, 0.0), 0.0, 1)
        rs = RobotState()
        v_max = 0.0
        for _ in range(150):                     # 3 s
            robot_step(robot, rs, WalkCmd(1.0, 0.0, 0.0), rp, DT, self.rng)
            v_max = max(v_max, rs.v_body[0])
        expected = rp.v_forward * 3 - rp.v_forward ** 2 / (2 * rp.accel)
        self.assertAlmostEqual(v_max, rp.v_forward, delta=1e-12)
        self.assertLess(abs(robot.pos[0] - expected), 0.01)
        self.assertEqual((robot.pos[1], robot.heading), (0.0, 0.0))

    def test_02_walking_and_turning_share_one_limit(self):
        rp = self.rp
        _, rs = drive(WalkCmd(1.0, 1.0, 10.0), rp, 100, self.rng)
        v = rs.v_body
        f = math.sqrt((v[0] / rp.v_forward) ** 2 + (v[1] / rp.v_side) ** 2 + (v[2] / rp.turn_rate) ** 2)
        self.assertLess(abs(f - 1), 1e-6)

    def test_03_kick_timing(self):
        rp = self.rp
        robot = Robot((0.0, 0.0), 0.0, 1)
        rs = RobotState(v_body=(0.2, 0.0, 0.0))
        cmd = WalkCmd(0.2, 0.0, 0.0, kick=True, kick_dir=0.0, kick_speed=1.0)
        contact = []
        for i in range(1, round(rp.kick_time / DT) + 1):
            before = robot.pos
            if robot_step(robot, rs, cmd, rp, DT, self.rng):
                contact.append(i * DT)
            self.assertEqual(robot.pos, before)
        robot_step(robot, rs, WalkCmd(0.2, 0.0, 0.0), rp, DT, self.rng)
        self.assertEqual(len(contact), 1)
        self.assertAlmostEqual(contact[0], rp.kick_contact, delta=1e-9)
        self.assertIsNone(rs.kick_t)
        self.assertGreater(rs.v_body[0], 0)

    def test_04_robots_kept_apart_and_on_the_carpet(self):
        pp, rp = self.pp, self.rp
        robots = [Robot((0.0, 0.0), 0.0, 1), Robot((0.1, 0.0), 0.0, 2), Robot((6.0, -5.0), 0.0, 2)]
        keep_apart(robots, pp, rp)
        x_max = pp.half_length + pp.border_width - rp.radius
        y_max = pp.half_width + pp.border_width - rp.radius
        self.assertAlmostEqual(norm((robots[1].pos[0] - robots[0].pos[0], 0.0)), 2 * rp.radius, delta=1e-12)
        self.assertAlmostEqual((robots[0].pos[0] + robots[1].pos[0]) / 2, 0.05, delta=1e-12)
        self.assertEqual(robots[2].pos, (x_max, -y_max))

    def test_05_striker_alone_scores_from_three_starts(self):
        for pos, heading, ball in (((-1.0, 0.0), 0.0, (0.0, 0.0)), ((1.0, 0.2), 0.0, (0.0, 0.0)),
                                   ((-1.0, 2.0), -math.pi / 2, (2.0, -1.5))):
            w = World(ball=Ball(pos=ball), robots=[Robot(pos, heading, 1)])
            outcome, _ = run_sim(w, ['striker'], self.spp, self.pp, self.bp, self.rp, 60, rng=self.rng)
            self.assertEqual(outcome, 'goal', f'from {pos}')

    def test_06_keeper_guards_the_line_to_the_ball(self):
        w = World(ball=Ball(pos=(2.0, 1.5)), robots=[Robot((4.15, 0.0), math.pi, 2)])
        run_sim(w, ['keeper'], self.spp, self.pp, self.bp, self.rp, 10, rng=self.rng)
        goal = (self.pp.own_goal_x(2), 0.0)
        to_ball = (w.ball.pos[0] - goal[0], w.ball.pos[1])
        target = (goal[0] + 0.5 * to_ball[0] / norm(to_ball), 0.5 * to_ball[1] / norm(to_ball))
        keeper = w.robots[0]
        d = (w.ball.pos[0] - keeper.pos[0], w.ball.pos[1] - keeper.pos[1])
        self.assertLess(norm((keeper.pos[0] - target[0], keeper.pos[1] - target[1])), 0.05)
        self.assertLess(abs(wrap_angle(math.atan2(d[1], d[0]) - keeper.heading)), 5 * math.pi / 180)

    def test_07_keeper_clears_a_nearby_ball(self):
        w = World(ball=Ball(pos=(3.7, 0.4)), robots=[Robot((4.15, 0.0), math.pi, 2)])
        outcome, _ = run_sim(w, ['keeper'], self.spp, self.pp, self.bp, self.rp, 10, rng=self.rng)
        self.assertEqual(outcome, 'cleared')
        self.assertLess(w.ball.vel[0], 0)

    def test_08_drill_runs_with_realistic_sensors(self):
        results = self.quiet_drill(3, 'realistic')
        self.assertEqual(len(results), 3)
        self.assertTrue({r.outcome for r in results} <= OUTCOMES)

    def test_09_each_robot_can_have_its_own_sensor_setting(self):
        w = world_init(self.pp)
        w.robots = [w.robots[0], w.robots[4]]
        ss = sensor_init(2)
        noisy = False
        for _ in range(20):
            pa = sensor_step(w, 0, ss[0], self.spp, DT, rng=self.rng)
            pb = sensor_step(w, 1, ss[1], SensorParams(), DT, rng=self.rng)
            self.assertEqual(pa.self_pos, w.robots[0].pos)
            noisy = noisy or (is_finite(pb.self_pos) and pb.self_pos != w.robots[1].pos)
            w.t += DT
        self.assertTrue(noisy)
        mixed = self.quiet_drill(2, ('perfect', 'realistic'))
        own = self.quiet_drill(1, ('realistic', replace(SensorParams(), range_ball=6.0)))
        self.assertTrue({r.outcome for r in mixed + own} <= OUTCOMES)
        with self.assertRaises(ValueError):
            self.quiet_drill(1, 'perfec')

    def test_10_starting_spots_do_not_depend_on_sensor_settings(self):
        a = self.quiet_drill(4, 'perfect')
        b = self.quiet_drill(4, ('realistic', 'perfect'))
        self.assertEqual([r.ball_start for r in a], [r.ball_start for r in b])
        self.assertEqual([r.striker_start for r in a], [r.striker_start for r in b])

    def test_11_odometry(self):
        rp0 = replace(self.rp, odo_sig_trans=0.0, odo_sig_rot=0.0)
        robot, rs = drive(WalkCmd(0.2, 0.05, 0.4), rp0, 250, self.rng)
        self.assertLess(norm((rs.odom[0] - robot.pos[0], rs.odom[1] - robot.pos[1])), 1e-9)
        self.assertLess(abs(wrap_angle(rs.odom[2] - robot.heading)), 1e-9)
        robot, rs = drive(WalkCmd(0.2, 0.0, 0.0), self.rp, 250, self.rng)      # straight, 5 s
        error = norm((rs.odom[0] - robot.pos[0], rs.odom[1] - robot.pos[1]))
        self.assertAlmostEqual(error, abs(rs.odo_scale[0] - 1) * norm(robot.pos), delta=1e-9)
        robot, rs = drive(WalkCmd(0.0, 0.0, 0.5), self.rp, 100, self.rng)      # turn on the spot, 2 s
        self.assertAlmostEqual(abs(rs.odom[2] - robot.heading),
                               abs(rs.odo_scale[1] - 1) * abs(robot.heading), delta=1e-9)

    def test_12_odometry_update_brings_the_percept_up_to_now(self):
        p = Percept(self_pos=(0.0, 0.0), self_heading=0.0, odom=(5.0, 5.0, math.pi / 2),
                    ball_visible=True, ball_range=1.0, ball_bearing=0.0, ball_pos=(1.0, 0.0))
        ten = 10 * math.pi / 180
        q = odometry_update(p, (5.0, 5.1, math.pi / 2 + ten))                  # 0.1 m forward
        self.assertLess(norm((q.self_pos[0] - 0.1, q.self_pos[1])), 1e-12)
        self.assertAlmostEqual(q.self_heading, ten, delta=1e-12)
        self.assertAlmostEqual(q.ball_range, 0.9, delta=1e-12)
        self.assertAlmostEqual(q.ball_bearing, -ten, delta=1e-12)
        self.assertEqual(q.ball_pos, (1.0, 0.0))
        self.assertIs(odometry_update(p, None), p)

    def test_13_pass_speed_agrees_with_the_ball_model(self):
        bp = self.bp
        v_pass, reachable = pass_speed(1.5, bp)
        b = Ball(vel=(v_pass, 0.0))
        for _ in range(500):
            ball_step(b, [], self.pp, bp, DT)
        v_far, far_ok = pass_speed(5.0, bp)
        self.assertTrue(reachable)
        self.assertLess(abs(ball_path((0.0, 0.0), (v_pass, 0.0), [0.0], bp)[3] - 1.5), 1e-6)
        self.assertLess(abs(b.pos[0] / 1.5 - 1), 0.03)
        self.assertFalse(far_ok)
        self.assertEqual(v_far, bp.kick_speed_max)

    def test_14_ball_tracking(self):
        b = Ball(vel=(1.6, 0.6))
        tr = None
        pk = Percept(ball_visible=True)
        v_early = (0.0, 0.0)
        for i in range(51):                      # 1 s
            if i % 5 == 0:                       # an image every 0.1 s
                pk.t_measured = i * DT
                pk.ball_pos = b.pos
                v_est, tr = track_ball(pk, tr, self.bp)
                if i == 5:
                    v_early = v_est              # only 2 sightings so far
            if i < 50:
                ball_step(b, [], self.pp, self.bp, DT)
        self.assertFalse(is_finite(v_early))
        self.assertLess(norm((v_est[0] - b.vel[0], v_est[1] - b.vel[1])), 0.1)

    def test_15_intercept_point(self):
        rp, bp = self.rp, self.bp
        ball, vel, robot = (0.0, 0.0), (1.5, 0.0), (1.2, 0.2)
        target, t_meet = intercept_point(ball, vel, robot, rp, bp)
        _, _, t_stop, d_stop = ball_path(ball, vel, [0.0], bp)
        reach = norm((target[0] - robot[0], target[1] - robot[1])) / rp.v_forward + 0.3
        self.assertLess(abs(target[1]), 1e-12)
        self.assertTrue(0 < target[0] < d_stop)
        self.assertLess(t_meet, t_stop)
        self.assertLessEqual(reach, t_meet + 1e-9)
        far, _ = intercept_point(ball, (2.0, 0.0), (-3.0, 0.0), rp, bp)
        stop2 = ball_path(ball, (2.0, 0.0), [0.0], bp)[3]
        self.assertLess(norm((far[0] - stop2, far[1])), 1e-9)

    def test_16_keeper_steps_into_a_shot_and_ignores_a_wide_ball(self):
        state, vy = keeper_reaction((2.6, 0.0), (1.9, 0.35), self.pp, self.bp, self.rp)
        wide, _ = keeper_reaction((2.6, 0.0), (1.2, 1.5), self.pp, self.bp, self.rp)
        self.assertEqual((state, wide), ('intercept', 'guard'))
        self.assertGreater(vy, 0)

    def test_17_striker_heads_for_the_intercept_point(self):
        pk = Percept(self_pos=(0.0, 1.0), self_heading=0.0, ball_visible=True)
        mem = None
        for i in range(6):
            pk.t_measured = 0.1 * i
            pk.ball_pos = ball_path((0.0, 0.0), (1.5, 0.0), [0.1 * i], self.bp)[0][0]
            pk.ball_range = norm((pk.ball_pos[0], pk.ball_pos[1] - 1))
            pk.ball_bearing = math.atan2(pk.ball_pos[1] - 1, pk.ball_pos[0])
            cmd, mem = striker_behaviour(pk, mem, 1, self.pp, self.bp, self.rp)
        self.assertEqual(mem.state, 'intercept')
        self.assertGreater(cmd.vx, 0)
        self.assertLess(cmd.vy, 0)

    def test_18_passing_to_a_team_mate(self):
        w = World(ball=Ball(), robots=[Robot((-0.5, 0.0), 0.0, 1), Robot((1.4, -1.0), math.pi, 1)])
        _, info = run_sim(w, ['striker', 'striker'], self.spp, self.pp, self.bp, self.rp, 15,
                          stop_on_receive=True, rng=self.rng)
        self.assertGreaterEqual(info.passes, 1)
        self.assertGreaterEqual(info.received, 1)
        self.assertIn('support', info.states[1])

    def test_19_drill_with_two_attackers_counts_passes(self):
        results = self.quiet_drill(3, 'realistic', n_attackers=2)
        self.assertEqual(len(results), 3)
        self.assertTrue({r.outcome for r in results} <= OUTCOMES)
        self.assertTrue(all(r.passes_received <= r.passes for r in results))
        self.assertTrue(all(r.support_start is not None for r in results))


if __name__ == '__main__':
    unittest.main()
