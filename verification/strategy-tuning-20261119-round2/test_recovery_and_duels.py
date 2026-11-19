"""Behaviour regressions for the second tuning session; no result quotas."""
from pathlib import Path
import importlib.util
import math
import os
import unittest

ROOT=Path(__file__).resolve().parents[2]
APP=Path(os.environ.get('FOOTBALL_TEST_APP', str(ROOT/'2D_Shared_Policy_2026-11-11')))
spec=importlib.util.spec_from_file_location('recovery_test_app',APP/'server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from Utils.DefensivePlan import recovery_action, route, SETTINGS
from Utils.Navigation import angle_to

class RecoveryChecks(unittest.TestCase):
    def test_coincident_face_point_has_no_invented_heading(self):
        for yaw in (-math.pi,-1,0,1,math.pi):
            self.assertEqual(angle_to((4.3,0),(4.3,0),yaw),0)

    def test_finite_window_uses_available_backward_cover(self):
        own=(2,.8);target=(4.18,.2);ball=(2.3,.6)
        self.assertTrue(route(own,math.pi,target,.1)[1].startswith(('left','right')))
        self.assertEqual(recovery_action(own,math.pi,target,ball),'back')

    def test_mirrored_ends_choose_same_body_action(self):
        for x in (-2,0,2,3.8):
            for yaw in (-2.7,-1.5,0,1.5,2.7):
                own=(x,.8);target=(4.18,.2);ball=(min(4.3,x+.3),.6)
                a=recovery_action(own,yaw,target,ball)
                b=recovery_action(tuple(-v for v in own),yaw+math.pi,
                                  tuple(-v for v in target),tuple(-v for v in ball))
                self.assertEqual(a,b)

    def test_reached_cover_point_holds_position(self):
        self.assertEqual(recovery_action((4.18,.2),2.,(4.18,.2),(3.,.4)),'stand')

    def test_clear_forward_route_keeps_walking(self):
        self.assertEqual(recovery_action((2,0),0,(4.18,0),(2.4,0)),'walk')

    def test_stationary_foot_duel_reaches_escape_timer(self):
        s=m.SharedScene(27,seconds=180)
        s.ball=[.8,0,.07]
        s.players['BlueDefender'].update(position=[1,0,.334],yaw=math.pi)
        s.players['RedForwardA'].update(position=[.68,.15,.334],yaw=0)
        p=s.policies['BlueDefender']
        world=s.observation();world['time']=0
        self.assertEqual(p.decide(world).behaviour,'CHALLENGE')
        world['time']=SETTINGS['duel_hold_seconds']-.1
        self.assertEqual(p.decide(world).behaviour,'CHALLENGE')
        world['time']=SETTINGS['duel_hold_seconds']+.1
        self.assertEqual(p.decide(world).behaviour,'DUEL_ESCAPE')

    def test_moving_ball_resets_duel_timer(self):
        s=m.SharedScene(27,seconds=180)
        s.ball=[.8,0,.07]
        s.players['BlueDefender'].update(position=[1,0,.334],yaw=math.pi)
        s.players['RedForwardA'].update(position=[.68,.15,.334],yaw=0)
        p=s.policies['BlueDefender'];w=s.observation();w['time']=0;p.decide(w)
        w['time']=9;w['ball']['position'][1]=.08
        self.assertEqual(p.decide(w).behaviour,'CHALLENGE')

if __name__=='__main__':unittest.main(verbosity=2)
