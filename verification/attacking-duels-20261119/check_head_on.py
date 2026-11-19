from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent;base={'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.}
variants={'baseline':('baseline-app',{}),'clear-lane':('round4-app',{**base,'evade_clear_only':True}),'reach-clear':('round4-app',{**base,'evade_cost':'reachability','duel_mode':'ball_side','duel_step':.08,'evade_clear_only':True})}
def run(item):
 name,(app,tuning)=item;out=H/('headon-'+name+'-v2.json')
 with out.with_suffix('.log').open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_v2.py'),'--app',str(H/app),'--seed','86000','--count','120','--layouts',str(H/'head-on-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,json.loads(out.read_text())['summary']
r={}
with ThreadPoolExecutor(max_workers=2) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();r[name]=result;print(name,json.dumps(result),flush=True);(H/'headon-summary-v2.json').write_text(json.dumps(r,indent=2))
