from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
base={'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.,'evade_clear_only':True,'duel_geometry_gate':True,'evade_min_distance':.65}
variants={'invalid-ballside':{**base,'duel_mode':'ball_side','duel_ballside_min':.12},'near-ballside':{**base,'duel_mode':'ball_side','duel_ballside_min':.08},'safe-width':{**base,'evade_width':.55},'safe-wide':{**base,'evade_width':.8}}
def run(item):
 name,tuning=item;out=H/(name+'-v3.json')
 with out.with_suffix('.log').open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_v3.py'),'--app',str(H/'round6-app'),'--seed','83000','--count','240','--layouts',str(H/'validation-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 out2=H/('headon-'+name+'-v3.json')
 with out2.with_suffix('.log').open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_v3.py'),'--app',str(H/'round6-app'),'--seed','86000','--count','120','--layouts',str(H/'head-on-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(out2)],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,'validation':json.loads(out.read_text())['summary'],'headon':json.loads(out2.read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();r[name]=result;print(name,json.dumps(result),flush=True);(H/'round6-summary-v3.json').write_text(json.dumps(r,indent=2))
