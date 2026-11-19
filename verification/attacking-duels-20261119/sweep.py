from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
 'hold-eight':{'striker_duel_seconds':8.},
 'hold-twelve':{'striker_duel_seconds':12.},
 'evade-early':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65},
 'evade-wide':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.9},
 'evade-late':{'evade_enabled':True,'evade_distance':1.1,'evade_width':.55},
 'evade-hold':{'evade_enabled':True,'evade_distance':1.8,'evade_width':.65,'striker_duel_seconds':8.},
}
def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'experiment-app'),'--seed','80000','--count','160','--layouts',str(H/'train-layouts.json'),'--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
results={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,result=future.result();results[name]=result;print(name,json.dumps(result),flush=True);(H/'sweep-summary.json').write_text(json.dumps(results,indent=2))
