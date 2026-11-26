"""Self-checks for the sensor layer."""
import math
import random
import statistics
import unittest
from dataclasses import replace

from robot_soccer.environment.ball import Ball
from robot_soccer.environment.world import Robot, World
from robot_soccer.geometry import is_finite, norm
from robot_soccer.sensors.params import SensorParams
from robot_soccer.sensors.percept import Percept
from robot_soccer.sensors.sensor_layer import (head_control, sense_once, sensor_init, sensor_step,
                                               update_percept)


def quiet_params(**changes):
    """Parameters with all randomness switched off."""
    return replace(SensorParams(), sig_range_rel=0.0, sig_range_abs=0.0, sig_bearing=0.0,
                   p_miss=0.0, sig_loc_pos=0.0, sig_loc_heading=0.0, **changes)


def make_world(pos, heading, ball, others=()):
    """Robot 0 is the observer (team 1); others = (x, y, team)."""
    robots = [Robot(pos, heading, 1)] + [Robot((x, y), 0.0, team) for x, y, team in others]
    return World(ball=Ball(pos=ball), robots=robots)


def correlation(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return sab / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def loc_error_samples(w, sp, n_images, rng, dt=0.02):
    """Capture actual image timestamps and the x position error at each image."""
    ss = sensor_init(1)[0]
    times, errors = [], []
    last_t = -math.inf
    # Allow for at least one vision interval per image plus delivery delay.
    steps = math.ceil((n_images * (dt + sp.update_period) + sp.latency) / dt) + 1
    for step in range(steps):
        w.t = step * dt
        p = sensor_step(w, 0, ss, sp, dt, rng=rng)
        if p.t_measured > last_t:
            times.append(p.t_measured)
            errors.append(p.self_pos[0] - w.robots[0].pos[0])
            last_t = p.t_measured
            if len(errors) == n_images:
                return times, errors
    raise AssertionError(f'Expected {n_images} vision samples; received {len(errors)}')


class SensorChecks(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(42)
        self.spq = quiet_params()

    def test_01_ball_ahead_exact(self):
        m = sense_once(make_world((0.0, 0.0), 0.0, (1.0, 0.0)), 0, 0.0, self.spq, rng=self.rng)
        self.assertTrue(m.ball_visible)
        self.assertAlmostEqual(m.ball_range, 1, delta=1e-12)
        self.assertAlmostEqual(m.ball_bearing, 0, delta=1e-12)
        self.assertLess(norm((m.ball_pos[0] - 1, m.ball_pos[1])), 1e-12)

    def test_02_ball_behind_not_seen(self):
        m = sense_once(make_world((0.0, 0.0), 0.0, (-1.0, 0.0)), 0, 0.0, self.spq, rng=self.rng)
        self.assertFalse(m.ball_visible)

    def test_03_ball_outside_field_of_view_not_seen(self):
        a = self.spq.fov_h / 2 + 0.02
        m = sense_once(make_world((0.0, 0.0), 0.0, (math.cos(a), math.sin(a))), 0, 0.0, self.spq,
                       rng=self.rng)
        self.assertFalse(m.ball_visible)

    def test_04_ball_beyond_range_not_seen(self):
        w = make_world((0.0, 0.0), 0.0, (self.spq.range_ball + 0.5, 0.0))
        self.assertFalse(sense_once(w, 0, 0.0, self.spq, rng=self.rng).ball_visible)

    def test_05_head_turned_left_sees_ball_on_the_left(self):
        m = sense_once(make_world((0.0, 0.0), 0.0, (0.0, 1.0)), 0, math.pi / 2, self.spq, rng=self.rng)
        self.assertTrue(m.ball_visible)
        self.assertAlmostEqual(m.ball_bearing, math.pi / 2, delta=1e-12)

    def test_06_occlusion(self):
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0), [(0.5, 0.0, 2)])
        self.assertFalse(sense_once(w, 0, 0.0, self.spq, rng=self.rng).ball_visible)
        off = replace(self.spq, occlusion=False)
        self.assertTrue(sense_once(w, 0, 0.0, off, rng=self.rng).ball_visible)

    def test_07_team_mates_and_opponents_told_apart(self):
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0), [(2.0, 0.3, 1), (2.0, -0.3, 2)])
        m = sense_once(w, 0, 0.0, self.spq, rng=self.rng)
        self.assertEqual((len(m.mates), len(m.opponents)), (1, 1))

    def test_08_perfect_mode_returns_the_truth(self):
        w = make_world((0.0, 0.0), 0.0, (-2.0, 1.0))
        p = sensor_step(w, 0, sensor_init(1)[0], SensorParams(mode='perfect'), 0.02, rng=self.rng)
        self.assertTrue(p.ball_visible)
        self.assertEqual(p.ball_pos, w.ball.pos)

    def test_09_latency(self):
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0))
        ss = sensor_init(1)[0]
        dt = 0.02
        for i in range(11):
            w.t = i * dt
            p = sensor_step(w, 0, ss, self.spq, dt, rng=self.rng)
            if w.t < self.spq.latency - 1e-9:
                self.assertFalse(math.isfinite(p.t_measured), 'result arrived too early')
            if abs(w.t - self.spq.latency) < 1e-9:
                self.assertEqual(p.t_measured, 0, 'result missing at t = latency')

    def test_10_noise_statistics(self):
        spn = replace(SensorParams(), p_miss=0.0, sig_loc_pos=0.0, sig_loc_heading=0.0)
        w = make_world((0.0, 0.0), 0.0, (2.0, 0.0))
        n = 3000
        images = [sense_once(w, 0, 0.0, spn, rng=self.rng) for _ in range(n)]
        eb = [m.ball_bearing for m in images]
        er = [m.ball_range - 2 for m in images]
        sr = spn.sig_range_rel * 2 + spn.sig_range_abs
        self.assertLess(abs(statistics.stdev(eb) / spn.sig_bearing - 1), 0.1)
        self.assertLess(abs(statistics.stdev(er) / sr - 1), 0.1)
        self.assertLess(abs(statistics.fmean(eb)), 3 * spn.sig_bearing / math.sqrt(n))
        self.assertLess(abs(statistics.fmean(er)), 3 * sr / math.sqrt(n))

    def test_11_missed_detections_at_the_set_rate(self):
        spm = replace(self.spq, p_miss=0.2)
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0))
        n = 3000
        seen = sum(sense_once(w, 0, 0.0, spm, rng=self.rng).ball_visible for _ in range(n))
        self.assertLess(abs(seen / n - 0.8), 0.03)

    def test_12_ball_memory(self):
        prev = Percept(ball_pos=(1.0, 0.0), ball_last_seen=0.0)
        kept = update_percept(prev, Percept(t_measured=self.spq.ball_memory - 0.5), self.spq)
        gone = update_percept(prev, Percept(t_measured=self.spq.ball_memory + 0.5), self.spq)
        self.assertEqual(kept.ball_pos, (1.0, 0.0))
        self.assertFalse(kept.ball_visible)
        self.assertFalse(is_finite(gone.ball_pos))

    def test_13_head_stops_at_the_joint_limit(self):
        ss = sensor_init(1)[0]
        ss.percept = Percept(self_pos=(0.0, 0.0), self_heading=0.0, ball_pos=(-1.0, 0.001),
                             ball_last_seen=0.0)
        self.assertAlmostEqual(head_control(ss, self.spq, 0.0, 10.0), self.spq.head_yaw_max, delta=1e-12)

    def test_14_localisation_error_drifts(self):
        sp = SensorParams()
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0))
        _, drift = loc_error_samples(w, sp, 6000, self.rng)
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0))
        _, fresh = loc_error_samples(w, replace(sp, loc_tau=0.0), 3000, self.rng)
        c_drift = correlation(drift[:-1], drift[1:])
        c_new = correlation(fresh[:-1], fresh[1:])
        spread = statistics.stdev(drift)
        self.assertLess(abs(c_drift - math.exp(-sp.update_period / sp.loc_tau)), 0.03)
        self.assertLess(abs(spread / sp.sig_loc_pos - 1), 0.15)
        self.assertLess(abs(c_new), 0.06)

    def test_15_percept_carries_odometry_from_the_image_time(self):
        w = make_world((0.0, 0.0), 0.0, (1.0, 0.0))
        ss = sensor_init(1)[0]
        got = False
        for i in range(31):
            w.t = i * 0.02
            p = sensor_step(w, 0, ss, self.spq, 0.02, (w.t, 0.0, 0.0), self.rng)
            if math.isfinite(p.t_measured):
                got = True
                self.assertAlmostEqual(p.odom[0], p.t_measured, delta=1e-12)
        self.assertTrue(got)

    def test_16_one_second_drift_correlation_at_fine_and_coarse_steps(self):
        sp = replace(SensorParams(), scan_amp=0.0)
        expected = math.exp(-1 / sp.loc_tau)
        for dt, one_second_lag in ((0.02, 10), (0.2, 5)):
            with self.subTest(dt=dt):
                # Keep the test about localisation: the ball starts out of view.
                w = make_world((0.0, 0.0), 0.0, (-1.0, 0.0))
                times, errors = loc_error_samples(w, sp, 10000, random.Random(42), dt)
                for earlier, later in zip(times, times[one_second_lag:]):
                    self.assertAlmostEqual(later - earlier, 1, delta=1e-9)
                rho = correlation(errors[:-one_second_lag], errors[one_second_lag:])
                self.assertAlmostEqual(rho, expected, delta=0.04)


if __name__ == '__main__':
    unittest.main()
