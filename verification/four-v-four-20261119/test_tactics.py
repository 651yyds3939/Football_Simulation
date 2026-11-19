from pathlib import Path
import sys,unittest,math,json,copy,hashlib
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'Four_vs_Four'
sys.path.insert(0,str(APP/'backend/tools'))
from soccer2d import Simulation,Model
from Utils.TeamTactics import TacticalPolicy,SETTINGS
from Utils.TeamPolicy import TeamPolicy
class TacticsTests(unittest.TestCase):
 def setUp(self):self.saved=dict(SETTINGS);self.s=Simulation(27,candidate='baseline');self.s.engine.phase='PLAYING';self.s.engine.released=True;self.s.engine.red_direction=1;self.s.engine.restart_team='RED';self.s.ball=[0,0,.07];self.s.players['RedForwardA'].update(position=[-.2,0,.334],yaw=0);self.s.players['RedForwardB'].update(position=[2,1,.334],yaw=0)
 def tearDown(self):SETTINGS.clear();SETTINGS.update(self.saved)
 def intent(self,receiver='RedForwardB'):
  w=self.s.observation();w['pass_intent']={'sender':'RedForwardA','receiver':receiver,'expires':24.};return w
 def test_far_handoff_does_not_freeze_sender(self):
  p=TacticalPolicy('RedForwardA',goal_depth=.3);d=p.decide(self.intent());self.assertNotEqual(d.behaviour,'SUPPORT_PASS')
 def test_far_handoff_does_not_force_distant_receiver(self):
  p=TacticalPolicy('RedForwardB',goal_depth=.3);d=p.decide(self.intent());self.assertNotEqual(d.behaviour,'RECEIVE_PASS')
 def test_near_handoff_remains_supported(self):
  self.s.players['RedForwardB']['position']=[.4,0,.334];w=self.intent();d=TacticalPolicy('RedForwardA').decide(w);self.assertEqual(d.behaviour,'SUPPORT_PASS');d=TacticalPolicy('RedForwardB').decide(w);self.assertEqual(d.behaviour,'RECEIVE_PASS')
 def test_shared_observation_is_not_modified(self):
  w=self.intent();before=copy.deepcopy(w);TacticalPolicy('RedForwardA').decide(w);self.assertEqual(w,before)
 def test_missing_receiver_does_not_crash(self):
  d=TacticalPolicy('RedForwardA').decide(self.intent('Missing'));self.assertTrue(all(math.isfinite(x) for x in d.target))
 def test_cover_is_goal_side_and_bounded(self):
  w=self.s.observation();p=TacticalPolicy('RedDefender');d=p.decide(w);self.assertEqual(d.behaviour,'COVER_GOAL');self.assertLessEqual(d.target[0],-1.5);self.assertLessEqual(abs(d.target[1]),1.65)
 def test_mirrored_cover_has_same_geometry(self):
  w=self.s.observation();a=TacticalPolicy('RedDefender').decide(w);w=copy.deepcopy(w);w['match']['red_direction']=-1
  for p in w['robots'].values():p['position'][0]*=-1;p['yaw']=math.pi-p['yaw']
  w['ball']['position'][0]*=-1;b=TacticalPolicy('RedDefender').decide(w);self.assertAlmostEqual(a.target[0],-b.target[0]);self.assertAlmostEqual(a.target[1],b.target[1])
 def test_ready_and_restart_logic_preserved(self):
  w=self.s.observation();w['match']['phase']='READY';a=TacticalPolicy('RedForwardA').decide(copy.deepcopy(w));b=TeamPolicy('RedForwardA').decide(copy.deepcopy(w));self.assertEqual(a,b)
 def test_goalkeeper_logic_preserved(self):
  w=self.s.observation();a=TacticalPolicy('RedGoalkeeper').decide(copy.deepcopy(w));b=TeamPolicy('RedGoalkeeper').decide(copy.deepcopy(w));self.assertEqual(a,b)
 def test_core_policy_and_navigation_unchanged(self):
  for name in ['TeamPolicy.py','Navigation.py','MatchEngine.py','CourseSpecs.py','DefensivePlan.py']:
   rel='backend/Wenao/controllers/Utils/'+name;self.assertEqual((APP/rel).read_bytes(),(H/'baseline-app'/rel).read_bytes())
 def test_motion_and_contact_executor_unchanged(self):self.assertEqual((APP/'backend/tools/soccer2d.py').read_bytes(),(H/'baseline-app/backend/tools/soccer2d.py').read_bytes())
 def test_one_v_one_all_files_preserved(self):
  one=ROOT/'2D_Shared_Policy_2026-11-11';before=json.loads((H/'one-v-one-before.json').read_text())
  for name,digest in before.items():self.assertEqual(hashlib.sha256((one/name).read_bytes()).hexdigest(),digest,name)
if __name__=='__main__':unittest.main(verbosity=2)
