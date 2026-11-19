from pathlib import Path
import importlib.util,os,unittest
H=Path(__file__).resolve().parent;APP=Path(os.environ.get('FOOTBALL_TEST_APP',str(H.parents[1]/'2D_Shared_Policy_2026-11-11')))
spec=importlib.util.spec_from_file_location('open_play_test',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class OpenPlayTests(unittest.TestCase):
 def crossing(self,name,end,real_restart=False):
  s=m.SharedScene(27);e=s.engine
  if real_restart:
   e.begin_restart('KICKOFF','RED',[0,0,.07],0);e.phase='PLAYING';e.released=True;e.kickoff_restriction=False
  e.last_touch=e.restart_touch=name;s.touch=name;e.previous=[end*4.55,0,.07];s.ball=[end*4.58,0,.07];s.step();return s
 def test_blue_first_toucher_scores_in_open_play(self):self.assertEqual(self.crossing('BlueDefender',-1).outcome,'CLEARED_GOAL')
 def test_red_own_goal_counts_in_open_play(self):self.assertEqual(self.crossing('RedForwardA',-1).outcome,'CLEARED_GOAL')
 def test_red_first_toucher_scores_in_open_play(self):self.assertEqual(self.crossing('RedForwardA',1).outcome,'GOAL')
 def test_real_restart_own_goal_still_disallowed(self):self.assertEqual(self.crossing('RedForwardA',-1,True).outcome,'OUT')
if __name__=='__main__':unittest.main(verbosity=2)
