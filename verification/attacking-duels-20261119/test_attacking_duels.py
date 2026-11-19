"""Behavioural regressions for carrying plans and first-contest foot care."""
from pathlib import Path
import importlib.util,os,unittest,math,copy,ast
H=Path(__file__).resolve().parent
APP=Path(os.environ.get('FOOTBALL_TEST_APP',str(H/'production-app')))
spec=importlib.util.spec_from_file_location('attacking_test',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from Utils.TeamPolicy import TeamPolicy,Decision
from Utils.Navigation import Navigator
from Utils.DefensivePlan import SETTINGS
class AttackTests(unittest.TestCase):
 def setUp(self):self.saved=dict(SETTINGS)
 def tearDown(self):SETTINGS.clear();SETTINGS.update(self.saved)
 def policy(self):
  p=TeamPolicy('RedForwardA',goal_depth=.3);p.now=0;p.own_yaw=0;p.has_recent_foot=True
  p.opponent_states=[{'position':[1.,0.,.334],'yaw':math.pi}]
  return p
 def test_clear_lane_keeps_goal_target(self):
  p=self.policy();goal=(4.8,0);self.assertEqual(p.carry_around([-.2,0],[0,0],goal,1,[[1,1.5]]),goal);self.assertIsNone(p.carry_plan)
 def test_already_beaten_opponent_does_not_trigger_evasion(self):
  p=self.policy();goal=(4.8,0);self.assertEqual(p.carry_around([-.2,0],[0,0],goal,1,[[-.5,0]]),goal)
 def test_close_tackle_does_not_start_large_evasion_turn(self):
  p=self.policy();goal=(4.8,0);self.assertEqual(p.carry_around([-.2,0],[0,0],goal,1,[[.34,0]]),goal);self.assertIsNone(p.carry_plan)
 def test_plan_commits_to_same_side_through_small_opponent_motion(self):
  p=self.policy();goal=(4.8,0);a=p.carry_around([-.2,0],[0,0],goal,1,[[1,0]])
  self.assertIsNotNone(p.carry_plan);p.now=1;b=p.carry_around([-.19,0],[.01,0],goal,1,[[1,.08]])
  self.assertEqual(a,b);self.assertLessEqual(abs(a[1]),2.35)
 def test_passed_defender_releases_plan(self):
  p=self.policy();goal=(4.8,0);p.carry_around([-.2,0],[0,0],goal,1,[[1,0]])
  self.assertEqual(p.carry_around([1.15,0],[1.4,0],goal,1,[[1,0]]),goal);self.assertIsNone(p.carry_plan)
 def test_restart_clears_plan(self):
  s=m.SharedScene(27);p=s.policies['RedForwardA'];p.carry_plan=(0,(1,0),(1.35,.65));w=s.observation();w['match']['phase']='READY';p.decide(w);self.assertIsNone(p.carry_plan)
 def test_counterpress_discards_old_carry_plan(self):
  s=m.SharedScene(27);p=s.policies['RedForwardA'];p.carry_plan=(0,(1,0),(1.35,.65));w=s.observation();w['robots']['RedForwardA']['position']=[0,0,.334];w['robots']['BlueDefender']['position']=[1.1,0,.334];w['ball']['position']=[1,0,.07];w['match']['last_touch']='BlueDefender';d=p.decide(w);self.assertIn(d.behaviour,('COUNTERPRESS','DUEL_ESCAPE'));self.assertIsNone(p.carry_plan)
 def test_turning_plan_has_precise_heading_gate(self):
  n=Navigator();n.aligned=True;face=(2*math.cos(math.radians(20)),2*math.sin(math.radians(20)))
  d=Decision('EVADE_DRIBBLE',(-.19,0),face);action,stage=n.choose(d,[0,0],0,[.2,0],[])
  self.assertTrue(action.startswith('left'))
 def test_ordinary_dribble_retains_heading_tolerance(self):
  n=Navigator();n.aligned=True;face=(2*math.cos(math.radians(20)),2*math.sin(math.radians(20)));d=Decision('DRIBBLE',(-.19,0),face)
  action,stage=n.choose(d,[0,0],0,[.2,0],[]);self.assertEqual(action,'walk')
 def test_plan_stays_inside_field_near_touchline(self):
  p=self.policy();a=p.carry_around([-.2,2.2],[0,2.2],(4.8,0),1,[[1,2.1]]);self.assertLessEqual(abs(a[1]),2.35)
 def test_mirrored_attack_chooses_goalward_lane(self):
  p=self.policy();p.own_yaw=math.pi;p.opponent_states=[{'position':[-1,0,.334],'yaw':0}];a=p.carry_around([.2,0],[0,0],(-4.8,0),-1,[[-1,0]])
  self.assertLess(a[0],0);self.assertIsNotNone(p.carry_plan)
 def test_valid_forward_foot_is_not_abandoned_after_three_seconds(self):
  p=self.policy();p.duel_anchor=((.2,0),0);w={'time':4.,'robots':{'RedForwardA':{'yaw':0}}}
  self.assertIsNone(p.unblock_duel(w,[0,0],[.2,0],[[.4,0]]))
 def test_invalid_foot_geometry_can_realign_promptly(self):
  p=self.policy();p.duel_anchor=((.2,.18),0);w={'time':4.,'robots':{'RedForwardA':{'yaw':0}}};d=p.unblock_duel(w,[0,0],[.2,.18],[[.3,.18]])
  self.assertIsNotNone(d);self.assertEqual(d.behaviour,'DUEL_ESCAPE')
 def test_body_and_ball_physics_are_identical(self):
  self.assertEqual((APP/'backend/tools/soccer2d.py').read_bytes(),(H/'baseline-app/backend/tools/soccer2d.py').read_bytes())
 def test_no_restart_or_defender_evasive_carry(self):
  p=self.policy();d=p.attack([0,0],[.2,0],1,{'RedForwardA':[0,0]},[[1,0]],'RESTART');self.assertEqual(d.behaviour,'RESTART')
  p=TeamPolicy('BlueDefender',goal_depth=.3);d=p.attack([1,0],[.8,0],-1,{'BlueDefender':[1,0]},[[0,0]]);self.assertEqual(d.behaviour,'CLEAR')
if __name__=='__main__':unittest.main(verbosity=2)
