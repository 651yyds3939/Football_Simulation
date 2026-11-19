from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
base={'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.}
variants={
 'reachability':{**base,'evade_cost':'reachability'},
 'reachability-heavy':{**base,'evade_cost':'reachability','evade_risk_weight':.4},
 'reachability-ballside':{**base,'evade_cost':'reachability','duel_mode':'ball_side','duel_step':.08},
 'geometry-hold':{**base,'duel_geometry_gate':True},
 'geometry-twelve':{**base,'duel_geometry_gate':True,'striker_duel_seconds':12.},
 'geometry-ballside':{**base,'duel_geometry_gate':True,'duel_mode':'ball_side','duel_step':.08},
}
def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_geometry_v1.py'),'--app',str(H/'round4-app'),'--seed','80000','--count','160','--layouts',str(H/'train-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();r[name]=result;print(name,json.dumps(result),flush=True);(H/'round4-summary.json').write_text(json.dumps(r,indent=2))
