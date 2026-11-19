"""Geometry, reproducibility and reachability checks for editable 1v1 starts."""
from pathlib import Path
import importlib.util
import math
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT/'2D_Shared_Policy_2026-11-11'
spec = importlib.util.spec_from_file_location('spawn_test_app', APP/'server.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from Utils.SpawnZones import SpawnZones
from Utils.DefensivePlan import interception, route


class SpawnChecks(unittest.TestCase):
    def test_random_regions_and_goal_side_margin(self):
        zones = SpawnZones()
        for seed in range(5000):
            with self.subTest(seed=seed):
                setup = zones.sample(seed)
                a = setup['robots']['RedForwardA']['position'][:2]
                d = setup['robots']['BlueDefender']['position'][:2]
                ball = setup['ball'][:2]
                for point, region in [(a,zones.attacker),(d,zones.defender)]:
                    self.assertTrue(region[0] <= point[0] <= region[1])
                    self.assertTrue(region[2] <= point[1] <= region[3])
                self.assertLessEqual(math.dist(d,(4.5,0))+zones.goal_side_margin,
                                     min(math.dist(a,(4.5,0)),math.dist(ball,(4.5,0))))
                self.assertGreaterEqual(math.dist(a,d),.34)
                self.assertGreaterEqual(math.dist(d,ball),.32)

    def test_repeat_seed_and_custom_regions(self):
        zones = SpawnZones.parse({'attacker':[-.5,.5,-.5,.5], 'defender':[2,3,-.8,.8]})
        for seed in range(20):
            self.assertEqual(zones.sample(seed),zones.sample(seed))
        self.assertNotEqual(zones.sample(27),zones.sample(28))

    def test_invalid_regions_are_rejected(self):
        for value in [[],{'extra':1},{'attacker':'bad'}, {'defender':[2,1,0,1]},
                      {'attacker':[0,.01,0,1]}, {'defender':[0,5,0,1]},
                      {'attacker':[0,1,float('nan'),1]}, {'goal_side_margin':True},
                      {'goal_side_margin':float('inf')}, {'goal_side_margin':0}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                SpawnZones.parse(value)

    def test_incompatible_regions_fail_without_invalid_fallback(self):
        zones = SpawnZones(attacker=(2,3,-.5,.5),defender=(-2,-1,-.5,.5))
        with self.assertRaisesRegex(ValueError,'valid goal-side defender'):
            zones.sample(27)

    def test_presets_are_goal_side(self):
        for scenario in ('random','duel','lane','shot','breakaway','block'):
            scene=m.SharedScene(27,scenario,30)
            a,d=(scene.players[n]['position'][:2] for n in m.NAMES)
            self.assertLess(math.dist(d,(4.5,0)),min(math.dist(a,(4.5,0)),math.dist(scene.ball[:2],(4.5,0))))

    def test_no_global_random_state_change(self):
        random.seed(91)
        state=random.getstate()
        SpawnZones().sample(27)
        self.assertEqual(random.getstate(),state)


class RouteChecks(unittest.TestCase):
    def test_short_reverse_does_not_require_half_turn(self):
        seconds,action,_=route((0,0),math.pi,(.35,0))
        self.assertEqual(action,'back')
        self.assertLess(seconds,10)

    def test_reachability_is_rotation_invariant(self):
        for own,yaw,target in [((2,.6),2.8,(1.8,0)),((2,1),1.2,(3.5,-.4)),((0,0),0,(-.3,.1))]:
            a=route(own,yaw,target)
            b=route(tuple(-x for x in own),yaw+math.pi,tuple(-x for x in target))
            self.assertAlmostEqual(a[0],b[0])
            self.assertEqual(a[1],b[1])

    def test_prediction_is_finite_and_inside_pitch(self):
        for direction in (-1,1):
            for x in (-3,0,3):
                target,predicted,horizon,reachable=interception((1,.4),2.8,(x,.2),(.08,0),direction,0)
                self.assertTrue(all(math.isfinite(v) for v in (*target,*predicted,horizon)))
                self.assertLessEqual(abs(target[0]),4.3)
                self.assertLessEqual(abs(target[1]),2.6)
                self.assertGreaterEqual(horizon,0)


if __name__=='__main__':
    unittest.main(verbosity=2)
