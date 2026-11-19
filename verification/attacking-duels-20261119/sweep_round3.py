from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
base={'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'duel_mode':'ball_side','duel_step':.08}
variants={
 'combo-three':base,
 'combo-eight':{**base,'striker_duel_seconds':8.},
 'combo-clear-lane':{**base,'evade_clear_only':True},
 'combo-before-box':{**base,'evade_goal_buffer':1.0},
 'combo-accurate-wide':{**base,'evade_distance':2.2,'evade_width':.8},
 'combo-footspace':{**base,'striker_space':True},
 'hold-footspace':{'striker_duel_seconds':8.,'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_space':True},
 'accurate-clear-lane':{'striker_duel_seconds':8.,'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'evade_clear_only':True},
}
def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_geometry_v1.py'),'--app',str(H/'round3-app'),'--seed','80000','--count','160','--layouts',str(H/'train-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();r[name]=result;print(name,json.dumps(result),flush=True);(H/'round3-summary.json').write_text(json.dumps(r,indent=2))
