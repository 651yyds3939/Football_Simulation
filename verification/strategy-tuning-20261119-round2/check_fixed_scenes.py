"""Exercise shipped fixed scenarios without random-birth assumptions."""
from pathlib import Path
import argparse,importlib.util,json,time
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
spec=importlib.util.spec_from_file_location('fixed_scene_app',a.app/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
start=time.perf_counter();rows=[]
for scenario in ('duel','lane','shot','breakaway','block'):
 for seed in (27,28,29,30,31):
  s=m.SharedScene(seed,scenario,180)
  while s.step():pass
  rows.append(s.summary())
a.output.write_text(json.dumps({'runs':rows,'wall_seconds':time.perf_counter()-start,'source':m.source_info()},indent=2))
print([(r['scenario'],r['seed'],r['outcome'],round(r['seconds'],2)) for r in rows])
