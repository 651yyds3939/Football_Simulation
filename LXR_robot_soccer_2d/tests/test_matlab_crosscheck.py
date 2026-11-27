"""The historical Python keeper and motion configuration must reproduce MATLAB.

golden/matlab_traces.json comes from golden/make_matlab_traces.m. Each trace is
compared every 0.5 s: positions, headings, the ball and each robot's state.
"""
import json
import unittest
from dataclasses import replace
from pathlib import Path

from robot_soccer.behaviours.ball_prediction import ball_path, intercept_point, pass_speed
from robot_soccer.behaviours.goalkeeper import MATLAB_KEEPER
from robot_soccer.environment.ball import Ball, BallParams
from robot_soccer.environment.pitch import PitchParams
from robot_soccer.environment.world import Robot, World
from robot_soccer.robot.motion import RobotParams
from robot_soccer.sensors.params import SensorParams
from robot_soccer.simulations.demo_pitch_ball import demo_pitch_ball

from sim_runner import run_sim

GOLDEN = json.loads((Path(__file__).parent / 'golden' / 'matlab_traces.json').read_text())
TOLERANCE = 1e-6    # m or rad

PP = PitchParams()
BP = replace(BallParams(), kick_sig_dir=0.0, kick_sig_speed=0.0)
RP = RobotParams(odo_sig_trans=0.0, odo_sig_rot=0.0, strict_walk_limit=False)
SENSORS = {'perfect': SensorParams(mode='perfect'),
           'quiet': replace(SensorParams(), sig_range_rel=0.0, sig_range_abs=0.0, sig_bearing=0.0,
                            p_miss=0.0, sig_loc_pos=0.0, sig_loc_heading=0.0)}


class MatlabCrossCheck(unittest.TestCase):
    def test_trajectories_match_matlab(self):
        for trace in GOLDEN['traces']:
            with self.subTest(trace['name'], sensors=trace['sensors']):
                values = trace['robots']            # x, y, heading, team of each robot in turn
                robots = [Robot((values[i], values[i + 1]), values[i + 2], int(values[i + 3]))
                          for i in range(0, len(values), 4)]
                w = World(ball=Ball(pos=tuple(trace['ball_start']), vel=tuple(trace['ball_vel'])),
                          robots=robots)
                outcome, info = run_sim(w, trace['roles'], SENSORS[trace['sensors']], PP, BP, RP, 40,
                                        sample_every=25, keeper_params=MATLAB_KEEPER)
                self.assertEqual(outcome, trace['outcome'])
                self.assertAlmostEqual(w.t, trace['t_end'], delta=1e-9)
                self.assertEqual(len(info.samples), len(trace['samples']))
                for mine, theirs in zip(info.samples, trace['samples']):
                    self.assertEqual(mine['states'], theirs['states'], f"t = {theirs['t']:.2f}")
                    for a, b in zip(mine['ball'] + mine['poses'], theirs['ball'] + theirs['poses']):
                        self.assertAlmostEqual(a, b, delta=TOLERANCE, msg=f"t = {theirs['t']:.2f}")

    def test_ball_prediction_values_match_matlab(self):
        v = GOLDEN['values']
        _, _, t_stop, d_stop = ball_path((0.0, 0.0), (1.5, 0.0), [0.0], BP)
        target, t_meet = intercept_point((0.0, 0.0), (1.5, 0.0), (1.2, 0.2), RP, BP)
        self.assertAlmostEqual(t_stop, v['t_stop'], delta=1e-12)
        self.assertAlmostEqual(d_stop, v['d_stop'], delta=1e-12)
        self.assertAlmostEqual(pass_speed(1.5, BP)[0], v['pass_speed'], delta=1e-9)
        self.assertAlmostEqual(target[0], v['intercept_target'][0], delta=1e-9)
        self.assertAlmostEqual(target[1], v['intercept_target'][1], delta=1e-9)
        self.assertAlmostEqual(t_meet, v['intercept_time'], delta=1e-9)

    def test_ball_demo_outcomes_match_matlab(self):
        self.assertEqual([r.outcome for r in demo_pitch_ball(verbose=False)], GOLDEN['demo_outcomes'])


if __name__ == '__main__':
    unittest.main()
