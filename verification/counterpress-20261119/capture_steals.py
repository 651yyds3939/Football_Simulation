"""Capture actual first Blue foot contacts from training fixtures only."""
from pathlib import Path
import importlib.util,json
H=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('steals_source',H/'baseline-app/server.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
layouts=json.loads((H/'train-layouts.json').read_text());out={};origins={}
for seed,initial in layouts.items():
 scene=m.SharedScene(int(seed),seconds=180);scene.ball=list(initial['ball'])
 for name,point in initial['robots'].items():scene.players[name].update(json.loads(json.dumps(point)),standing=True)
 seen=0
 while scene.step():
  if any(e['event']=='foot_control_change' and e['robot']=='BlueDefender' for e in scene.events[seen:]):
   key=str(70000+len(out));out[key]={'ball':scene.ball[:],'velocity':scene.velocity[:],'touch':'BlueDefender','robots':{n:{'position':p['position'][:],'yaw':p['yaw']} for n,p in scene.players.items()}}
   origins[key]={'source_seed':int(seed),'source_time':scene.time};break
  seen=len(scene.events)
 if len(out)>=80:break
(H/'steal-layouts.json').write_text(json.dumps(out));(H/'steal-origins.json').write_text(json.dumps(origins,indent=2));print('captured',len(out))
