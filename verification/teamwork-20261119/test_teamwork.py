from pathlib import Path
import unittest,sys,copy,json,hashlib
H=Path(__file__).resolve().parent;APP=H/'selected-app';ROOT=H.parents[1]
sys.path.insert(0,str(APP/'backend/tools'))
from soccer2d import Model
from Utils.TeamNavigation import TeamSimulation,CooperativeNavigator
from Utils.TeamTactics import TacticalPolicy
from Utils.PreviousTactics import TacticalPolicy as PreviousPolicy
from Utils.TeamPolicy import Decision
from Utils.Navigation import Navigator
class TeamworkTests(unittest.TestCase):
 def setUp(self):
  self.s=TeamSimulation(27,candidate='baseline');self.s.engine.phase='PLAYING';self.s.engine.released=True;self.s.engine.red_direction=1;self.s.engine.last_touch='RedForwardA';self.s.ball=[0.,0.,.07]
  positions={'RedForwardA':(-.2,-.05),'RedForwardB':(.8,1.1),'RedDefender':(-2.,0.),'RedGoalkeeper':(-4.,0.),'BlueForwardA':(2.,0.),'BlueForwardB':(2.,1.6),'BlueDefender':(3.,0.),'BlueGoalkeeper':(4.,0.)}
  for n,p in positions.items():self.s.players[n].update(position=[*p,.334],yaw=0.)
 def test_support_search_when_team_controls_ball(self):
  d=TacticalPolicy('RedForwardB').decide(self.s.observation());self.assertEqual(d.behaviour,'FIND_PASS_LANE');self.assertGreaterEqual(abs(d.target[0])**2+abs(d.target[1])**2,.9**2-1e-9);self.assertLessEqual(abs(d.target[0]),3.8);self.assertLessEqual(abs(d.target[1]),2.35)
 def test_search_does_not_replace_ball_carrier(self):
  w=self.s.observation();a=TacticalPolicy('RedForwardA').decide(copy.deepcopy(w));b=PreviousPolicy('RedForwardA').decide(copy.deepcopy(w));self.assertEqual(a,b)
 def test_no_search_when_opponent_has_ball(self):
  self.s.engine.last_touch='BlueForwardA';d=TacticalPolicy('RedForwardB').decide(self.s.observation());self.assertEqual(d.behaviour,'SUPPORT')
 def test_small_ball_sway_keeps_support_target(self):
  p=TacticalPolicy('RedForwardB');a=p.decide(self.s.observation());self.s.time=.2;self.s.ball[0]+=.03;b=p.decide(self.s.observation());self.assertEqual(a.target,b.target)
 def test_observation_is_not_modified(self):
  w=self.s.observation();before=copy.deepcopy(w);TacticalPolicy('RedForwardB').decide(w);self.assertEqual(w,before)
 def test_receiver_intent_filter_does_not_edit_shared_message(self):
  w=self.s.observation();w['pass_intent']={'sender':'RedForwardA','receiver':'RedForwardB','expires':24.};before=copy.deepcopy(w);TacticalPolicy('RedForwardB').decide(w);self.assertEqual(w,before)
 def test_noncarrier_yields_from_enemy_contest(self):
  self.s.engine.last_touch='BlueForwardA';self.s.players['RedForwardB']['position']=[.3,.5,.334];d=TacticalPolicy('RedForwardB').decide(self.s.observation());self.assertEqual(d.behaviour,'YIELD_TO_CARRIER')
 def test_offball_can_back_up_without_full_turn(self):
  d=Decision('FIND_PASS_LANE',(-.4,0),(1,0));action,_=CooperativeNavigator().choose(d,(0,0),0,(1,0));self.assertEqual(action,'back')
 def test_navigation_does_not_change_attack_execution(self):
  d=Decision('DRIBBLE',(-.19,0),(4.5,0));a=CooperativeNavigator().choose(d,(-.2,0),0,(0,0));b=Navigator().choose(d,(-.2,0),0,(0,0));self.assertEqual(a,b)
 def test_halftime_installs_only_candidate_navigators(self):
  self.s.policies['RedForwardA']=TacticalPolicy('RedForwardA');self.s.policies['BlueForwardA']=PreviousPolicy('BlueForwardA');self.s.install_team_navigators();self.assertIsInstance(self.s.navigators['RedForwardA'],CooperativeNavigator);self.s._place_formation(True);self.assertIsInstance(self.s.navigators['RedForwardA'],CooperativeNavigator);self.assertNotIsInstance(self.s.navigators['BlueForwardA'],CooperativeNavigator)
 def test_goalkeeper_and_ready_preserved(self):
  w=self.s.observation();self.assertEqual(TacticalPolicy('RedGoalkeeper').decide(w),PreviousPolicy('RedGoalkeeper').decide(w));w['match']['phase']='READY';self.assertEqual(TacticalPolicy('RedForwardB').decide(w),PreviousPolicy('RedForwardB').decide(w))
 def test_physics_and_carrier_code_preserved(self):
  for rel in ['tools/soccer2d.py','Wenao/controllers/Utils/TeamPolicy.py','Wenao/controllers/Utils/Navigation.py','Wenao/controllers/Utils/MatchEngine.py']:
   self.assertEqual((APP/'backend'/rel).read_bytes(),(H/'previous-app/backend'/rel).read_bytes(),rel)
 def test_existing_one_v_one_preserved(self):
  for rel,digest in json.loads((H/'one-v-one-before.json').read_text()).items():self.assertEqual(hashlib.sha256((ROOT/'2D_Shared_Policy_2026-11-11'/rel).read_bytes()).hexdigest(),digest,rel)
if __name__=='__main__':unittest.main(verbosity=2)
