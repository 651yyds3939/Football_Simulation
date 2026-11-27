"""Checks for the GK-01 shot setup, replays, outcomes and paired report."""
import math
import unittest
from dataclasses import replace
from unittest.mock import patch

from robot_soccer.environment.ball import ball_step, rolling_range
from robot_soccer.simulations import keeper_saves as gk


class KeeperSavesTests(unittest.TestCase):
    def test_seeded_shots_respect_geometry_and_nominal_speed(self):
        goal_x = gk.PITCH.own_goal_x(2)
        for aim in ('uniform', 'corner'):
            shots = gk.generate_shots(40, seed=1, aim=aim)
            self.assertEqual(shots, gk.generate_shots(40, seed=1, aim=aim))
            self.assertNotEqual(shots, gk.generate_shots(40, seed=2, aim=aim))
            for shot in shots:
                x, y = shot.ball_pos
                self.assertAlmostEqual(math.hypot(goal_x - x, y), shot.distance)
                self.assertAlmostEqual(math.atan2(y, goal_x - x), shot.angle)
                self.assertTrue(1.0 <= shot.distance <= 2.3)
                self.assertLessEqual(abs(shot.angle), math.pi / 3)
                self.assertAlmostEqual(math.dist(shot.shooter_pos, shot.ball_pos), 0.30)
                self.assertAlmostEqual(y + (goal_x - x) * math.tan(shot.heading), shot.target_y)
                if aim == 'corner':
                    self.assertLess(shot.target_y * y, 0)
                    self.assertAlmostEqual(abs(shot.target_y), 0.95)
                else:
                    self.assertLessEqual(abs(shot.target_y), gk.PITCH.goal_width / 2 - gk.BALL.radius)
                travel = rolling_range(shot.nominal_speed, gk.BALL, gk.DT)
                self.assertGreater(x + travel * math.cos(shot.heading), goal_x + gk.BALL.radius)
                self.assertLessEqual(shot.nominal_speed, gk.BALL.kick_speed_max)
                self.assertLessEqual(math.hypot(*shot.velocity), gk.BALL.kick_speed_max + 1e-12)

    def test_replay_is_deterministic_and_keeps_shots_paired(self):
        shots = gk.generate_shots(30, seed=1, aim='uniform')
        realistic = gk.run_shots(shots, 'realistic', 'baseline')
        self.assertEqual(realistic, gk.run_shots(shots, 'realistic', 'baseline'))
        for sensors, design in [('perfect', 'baseline'), ('realistic', 'stationary')]:
            results = gk.run_shots(shots, sensors, design)
            self.assertEqual([result.shot for result in results], shots)
            self.assertTrue(all(result.shooter_seen for result in results))
        self.assertIn('cleared_early', {result.outcome for result in realistic})

    def test_launch_time_velocity_and_physical_outcomes(self):
        def shot(y, speed):
            return gk.Shot(math.hypot(1.2, y), math.atan2(y, 1.2), (3.3, y), (3.0, y),
                           y, 0.0, speed, (speed, 0.0), 1)

        shots = [shot(0.65, 2.0), shot(0.0, 2.0), shot(1.65, 2.0), shot(0.65, 0.3)]
        results = gk.run_shots(shots, 'perfect', 'stationary')
        self.assertEqual([r.outcome for r in results], ['goal', 'saved', 'wide', 'short'])

        glancing_shot = shot(0.224, 2.0)
        velocities = []
        contacts = []

        def observe(ball, robots, pitch, params, dt, *, on_robot_contact):
            self.assertEqual(robots[0].pos, glancing_shot.shooter_pos)
            velocities.append(ball.vel)

            def observe_contact(index):
                contacts.append(index)
                on_robot_contact(index)

            ball_step(ball, robots, pitch, params, dt, on_robot_contact=observe_contact)

        with patch.object(gk, 'ball_step', observe):
            result, = gk.run_shots([glancing_shot], 'perfect', 'stationary')
        setup_steps = round(8 / gk.DT)
        self.assertEqual(velocities[:setup_steps], [(0.0, 0.0)] * setup_steps)
        self.assertEqual(velocities[setup_steps], glancing_shot.velocity)
        self.assertIn(gk.KEEPER, contacts)
        self.assertEqual(result.outcome, 'goal')

    def test_paired_comparison_excludes_unscorable_attempts_and_checks_pairs(self):
        initial = gk.generate_shots(6, seed=1, aim='uniform')
        a = ['goal', 'goal', 'goal', 'goal', 'short', 'saved']
        b = ['saved', 'saved', 'saved', 'goal', 'saved', 'cleared_early']
        first = [gk.Attempt(shot, outcome, True) for shot, outcome in zip(initial, a)]
        second = [gk.Attempt(shot, outcome, True) for shot, outcome in zip(initial, b)]
        paired = gk.compare_paired(first, second)
        self.assertEqual(paired, gk.compare_paired(first, second))
        self.assertEqual((paired.n, paired.first_only_eligible, paired.second_only_eligible), (4, 1, 1))
        self.assertEqual((paired.first_only_saved, paired.second_only_saved), (0, 3))
        self.assertEqual(paired.change, 0.75)
        self.assertEqual(paired.p_value, 0.25)
        self.assertLessEqual(paired.interval[0], paired.change)
        self.assertGreaterEqual(paired.interval[1], paired.change)
        self.assertIsNone(gk.compare_paired(first[4:], second[4:]).change)
        with self.assertRaises(ValueError):
            gk.compare_paired(first, second[::-1])
        changed_kick = replace(initial[0], velocity=(0.0, 0.0))
        with self.assertRaises(ValueError):
            gk.compare_paired(first, [replace(second[0], shot=changed_kick), *second[1:]])


if __name__ == '__main__':
    unittest.main()
