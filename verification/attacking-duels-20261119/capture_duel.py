"""Save a small timeline around first loss in a reproducible layout."""
from pathlib import Path
import argparse,importlib.util,json,math
H=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=80000);p.add_argument('--app',type=Path,default=H/'baseline-app');p.add_argument('--output',type=Path,required=True);p.add_argument('--tuning',type=json.loads,default={});a=p.parse_args()
spec=importlib.util.spec_from_file_location('captured_app',a.app/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from Utils.DefensivePlan import SETTINGS
SETTINGS.update(a.tuning);s=m.SharedScene(seed=a.seed);s._record=lambda:None
initial=json.loads((H/'train-layouts.json').read_text())[str(a.seed)];s.ball=list(initial['ball'])
for n,v in initial['robots'].items():s.players[n].update(v,standing=True)
frames=[]
while s.step():
 if round(s.time/s.model.dt)%10:continue
 frame={'t':round(s.time,2),'ball':[round(x,3) for x in s.ball[:2]],'touch':s.touch,'players':{}}
 for n,p in s.players.items():
  d=s.current_decisions[n];stage=s.navigation_stages[n];frame['players'][n]={'position':[round(x,3) for x in p['position'][:2]],'yaw':round(math.degrees(p['yaw']),1),'decision':d.behaviour,'target':[round(x,3) for x in d.target],'face':[round(x,3) for x in d.face],'action':s.last_actions[n],'stage':stage}
 frames.append(frame)
a.output.write_text(json.dumps({'initial':initial,'outcome':s.outcome,'frames':frames,'events':s.events},indent=2));print(a.seed,s.outcome)
