from pathlib import Path
import importlib.util,unittest,math,os
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('terminal_test',Path(os.environ.get('FOOTBALL_TEST_APP',str(H/'production-app')))/'server.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TerminalTests(unittest.TestCase):
 def scene(self,x,y=0):
  s=m.SharedScene(27,seconds=180)
  s.ball=[x,y,.07];s.engine.previous=[4.4 if x>0 else -4.4,y,.07]
  s.touch=s.engine.last_touch='RedForwardA' if x>0 else 'BlueDefender'
  return s
 def check_end(self,s,outcome):
  before={n:(tuple(p['position']),p['yaw']) for n,p in s.players.items()}
  for n in s.navigators:
   s.navigators[n].choose=lambda *a,**k:(_ for _ in ()).throw(AssertionError('post-terminal navigation'))
  self.assertFalse(s.step());self.assertEqual(s.outcome,outcome)
  self.assertEqual(before,{n:(tuple(p['position']),p['yaw']) for n,p in s.players.items()})
  snap=s.snapshot()
  for name in ['attacker','defender']:
   self.assertEqual(snap[name]['state'],'FINISHED');self.assertEqual(snap[name]['action'],'stand')
  self.assertFalse(s.step())
 def test_red_goal_no_post_goal_formation(self):self.check_end(self.scene(4.58),'GOAL')
 def test_blue_goal_no_post_goal_formation(self):self.check_end(self.scene(-4.58),'CLEARED_GOAL')
 def test_out_stops_before_restart_commands(self):self.check_end(self.scene(4.58,2),'OUT')
 def test_running_scene_still_moves(self):
  s=m.SharedScene(27,seconds=180);p=s.players['RedForwardA'];before=(tuple(p['position']),p['yaw']);self.assertTrue(s.step());self.assertGreater(s.time,0);self.assertNotEqual(before,(tuple(p['position']),p['yaw']))
if __name__=='__main__':unittest.main(verbosity=2)
