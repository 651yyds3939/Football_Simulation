"""Regression checks for the live 4v4 goalkeeper policy."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Four_vs_Four'))
from run import Model, create_match


class GoalkeepingTests(unittest.TestCase):
    def make_shot(self, policy='coordinated', direction=1):
        sim = create_match(27, red=policy, blue='relay', model=Model(dt=.04))
        match = sim.engine
        match.phase = 'PLAYING'
        match.half_started = 0
        match.red_direction = direction
        match.restart_team = None
        match.restart = 'DROP_BALL'
        match.released = True
        match.restart_goal_guard = False
        match.kickoff_restriction = False
        yaw = -1.675 if direction == 1 else math.pi + 1.675
        sim.players['RedGoalkeeper'].update(position=[-4.3753 * direction, .6194, .334], yaw=yaw)
        sim.ball = [-4.2456 * direction, .8491, .07]
        sim.velocity = [-.533 * direction, -.0266, 0.]
        match.restart_point = sim.ball.copy()
        return sim

    def test_near_post_move_starts_on_first_tick_and_blocks(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                sim = self.make_shot(direction=direction)
                sim.step()
                self.assertEqual(sim.last_decisions['RedGoalkeeper'], 'KEEPER_SHOT')
                self.assertIn(sim.last_actions['RedGoalkeeper'],
                              ('walk', 'back', 'step_left', 'step_right'))
                for _ in range(34):
                    sim.step()
                self.assertTrue(any(event['event'] == 'contact' and event['robot'] == 'RedGoalkeeper'
                                    for event in sim.events))
                self.assertEqual(sim.engine.score, [0, 0])

    def test_relay_policy_reproduces_the_late_turn(self):
        sim = self.make_shot(policy='relay')
        sim.step()
        self.assertTrue(sim.last_actions['RedGoalkeeper'].startswith(('left', 'right')))
        for _ in range(34):
            sim.step()
        self.assertEqual(sim.engine.score, [0, 1])

    def test_restart_and_receding_ball_do_not_trigger_shot_reaction(self):
        sim = self.make_shot()
        sim.engine.released = False
        self.assertFalse(sim.decide_all(sim.observation())['RedGoalkeeper'].behaviour.startswith('KEEPER_'))
        sim.engine.released = True
        sim.velocity[0] *= -1
        self.assertNotEqual(sim.decide_all(sim.observation())['RedGoalkeeper'].behaviour, 'KEEPER_SHOT')

    def test_near_post_ball_must_fit_through_the_goal(self):
        sim = self.make_shot()
        sim.ball[1] = 1.27
        sim.velocity[1] = 0.
        self.assertNotEqual(sim.decide_all(sim.observation())['RedGoalkeeper'].behaviour, 'KEEPER_SHOT')


if __name__ == '__main__':
    unittest.main()
