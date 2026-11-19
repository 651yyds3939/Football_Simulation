from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
 'accurate-early':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65},
 'accurate-hold':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.},
 'accurate-twelve':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':12.},
 'far-hold':{'evade_enabled':True,'evade_distance':2.2,'evade_width':.8,'striker_duel_seconds':8.},
 'soft-angle-hold':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.,'evade_angle':18.,'evade_enter_angle':8.},
 'ballside-three':{'duel_mode':'ball_side','duel_step':.08},
 'smallstep-eight':{'striker_duel_seconds':8.,'duel_step':.05},
 'ballside-eight':{'striker_duel_seconds':8.,'duel_mode':'ball_side','duel_step':.08},
}
def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'round2-app'),'--seed','80000','--count','160','--layouts',str(H/'train-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();r[name]=result;print(name,json.dumps(result),flush=True);(H/'round2-summary.json').write_text(json.dumps(r,indent=2))
