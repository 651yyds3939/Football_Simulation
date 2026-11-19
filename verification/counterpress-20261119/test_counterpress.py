"""Semantic regressions: losing possession must not select goal-facing alignment."""
from pathlib import Path
import importlib.util,math,os,unittest
H=Path(__file__).resolve().parent
APP=Path(os.environ.get('FOOTBALL_TEST_APP',str(H/'round2-app')))
spec=importlib.util.spec_from_file_location('press_test_app',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from Utils.TeamPolicy import Decision
from Utils.Navigation import Navigator
class CounterpressTests(unittest.TestCase):
 def loss(self):
  s=m.SharedScene(27,seconds=180);s.ball=[0,0,.07]
  s.players['RedForwardA'].update(position=[1,0,.334],yaw=0)
  s.players['BlueDefender'].update(position=[.22,0,.334],yaw=math.pi)
  s.engine.last_touch='BlueDefender';return s
 def test_loss_selects_counterpress(self):
  s=self.loss();d=s.policies['RedForwardA'].decide(s.observation());self.assertEqual(d.behaviour,'COUNTERPRESS');self.assertEqual(d.face,(0,0))
 def test_loss_faces_ball_not_attacking_goal(self):
  s=self.loss();d=s.policies['RedForwardA'].decide(s.observation());a,stage=s.navigators['RedForwardA'].choose(d,[1,0],0,s.ball)
  self.assertTrue(a.startswith(('left','right')));self.assertEqual(stage,'PRESS_FACE_BALL')
 def test_body_touch_behind_is_not_regained_control(self):
  s=self.loss();p=s.policies['RedForwardA'];p.counterpressing=True;s.engine.last_touch='RedForwardA'
  self.assertEqual(p.decide(s.observation()).behaviour,'COUNTERPRESS')
 def test_own_foot_control_can_return_to_attack(self):
  s=self.loss();p=s.policies['RedForwardA'];p.counterpressing=True;s.engine.last_touch='RedForwardA'
  s.players['RedForwardA'].update(position=[-.20,0,.334],yaw=0)
  self.assertNotEqual(p.decide(s.observation()).behaviour,'COUNTERPRESS');self.assertFalse(p.counterpressing)
 def test_weak_opponent_body_touch_does_not_force_switch(self):
  s=self.loss();s.players['RedForwardA'].update(position=[-.20,0,.334],yaw=0)
  self.assertNotEqual(s.policies['RedForwardA'].decide(s.observation()).behaviour,'COUNTERPRESS')
 def test_restart_resets_counterpress_latch(self):
  s=self.loss();p=s.policies['RedForwardA'];p.counterpressing=True;s.engine.phase='READY'
  self.assertEqual(p.decide(s.observation()).behaviour,'FORMATION');self.assertFalse(p.counterpressing)
 def test_mirrored_attack_end(self):
  a=self.loss();b=self.loss();b.engine.red_direction=-1
  for player in b.players.values():player['position']=[-v for v in player['position'][:2]]+[.334];player['yaw']+=math.pi
  b.ball=[-v for v in b.ball[:2]]+[.07]
  da=a.policies['RedForwardA'].decide(a.observation());db=b.policies['RedForwardA'].decide(b.observation())
  self.assertEqual(da.behaviour,db.behaviour)
  self.assertAlmostEqual(da.target[0],-db.target[0]);self.assertAlmostEqual(da.target[1],-db.target[1])
 def test_close_contest_does_not_rotate_to_goal(self):
  d=Decision('COUNTERPRESS',(-.2,0),(-.2,0));a,stage=Navigator().choose(d,(0,0),math.pi,(-.2,0))
  self.assertEqual(a,'walk');self.assertEqual(stage,'PRESS_CONTEST_FOOT')
class FootSpaceTests(unittest.TestCase):
 def test_close_defensive_tackle_creates_front_space(self):
  a,stage=Navigator().choose(Decision('CHALLENGE',(.1,.2),(.1,.2)),(0,0),0,(.1,.2))
  self.assertEqual(a,'back');self.assertEqual(stage,'CREATE_SPACE_BEFORE_SIDE_ALIGN')
 def test_clearance_alignment_creates_space_before_side_step(self):
  d=Decision('CLEAR',(-.3,-.1),(-2.,0),'pass')
  a,stage=Navigator().choose(d,(0,0),math.pi,(-.1,-.2))
  self.assertEqual(a,'back');self.assertEqual(stage,'CREATE_SPACE_BEFORE_SIDE_ALIGN')
 def test_striker_dribble_alignment_is_not_replaced_by_defender_rule(self):
  d=Decision('DRIBBLE',(-.1,.2),(4.5,.2))
  a,stage=Navigator().choose(d,(0,0),0,(.1,.2))
  self.assertEqual(a,'step_left');self.assertEqual(stage,'ALIGN_FOOT_LATERALLY')

if __name__=='__main__':unittest.main(verbosity=2)
