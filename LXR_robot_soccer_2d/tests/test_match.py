import unittest
from collections import Counter

from robot_soccer.environment.world import world_init
from robot_soccer.geometry import wrap_angle
from robot_soccer.simulations.match import play_match


class MatchTests(unittest.TestCase):
    def test_either_team_can_take_the_first_touch(self):
        for team in (1, 2):
            with self.subTest(team=team):
                result = play_match(5.35, kickoff_team=team, record=True)
                self.assertEqual(Counter(r.team for r in result.world.robots), {1: 4, 2: 4})
                self.assertAlmostEqual(result.world.t, 5.35)
                self.assertAlmostEqual(result.frames[-1].time, 5.35)
                first_index = next(i for i, frame in enumerate(result.frames) if frame.ball != (0, 0))
                first_motion = result.frames[first_index]
                waiting = result.frames[first_index - 1]
                self.assertEqual(waiting.states.index('kickoff') // 4 + 1, team)
                for k, (pos, _) in enumerate(waiting.poses):
                    if k != waiting.states.index('kickoff'):
                        self.assertEqual(pos, result.frames[0].poses[k][0])
                self.assertGreater(first_motion.ball[0] * (1 if team == 1 else -1), 0)

    def test_goal_counts_and_conceding_team_restarts_from_formation(self):
        # Seed 3 produces goals with the selected goalkeeper parameters.
        result = play_match(120, seed=3, record=True)
        goals = [event for event in result.world.events if event.type == 'goal']
        self.assertTrue(goals)
        count = Counter(goal.team for goal in goals)
        self.assertEqual(result.world.score, [count[1], count[2]])
        goal = goals[0]
        frames_after_goal = [frame for frame in result.frames if frame.time >= goal.t]
        formation = tuple((robot.pos, robot.heading) for robot in world_init().robots)
        self.assertEqual(frames_after_goal[0].ball, (0, 0))
        # By the next sample, the reset striker may already have begun to walk.
        restart_frame = next(frame for frame in frames_after_goal if 'kickoff' in frame.states)
        conceding_striker = (3 - goal.team) * 4 - 1
        self.assertEqual(restart_frame.states[conceding_striker], 'kickoff')
        for k, (pos, heading) in enumerate(restart_frame.poses):
            if k != conceding_striker:
                self.assertEqual(pos, formation[k][0])
                self.assertAlmostEqual(wrap_angle(heading - formation[k][1]), 0)

    def test_touchline_restart_does_not_immediately_send_ball_back_out(self):
        # Seed 2 produces a touchline exit with the refined goalkeeper.
        result = play_match(120, sensors='perfect', seed=2, kickoff_team=2, record=True)
        events = result.world.events
        index = next(k for k, event in enumerate(events) if event.type == 'out_touchline')
        out = events[index]
        self.assertIn(out.team, (1, 2))
        frame = next(f for f in result.frames if f.time > out.t and 'throw_in' in f.states)
        self.assertEqual(frame.states.index('throw_in') // 4 + 1, out.team)
        if index + 1 < len(events):
            self.assertGreater(events[index + 1].t - out.t, 0.2)
