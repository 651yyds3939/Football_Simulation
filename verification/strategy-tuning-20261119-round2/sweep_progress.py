from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
'progress-one':{'blocked_escape':True,'blocked_seconds':1.,'escape_metres':.10},
'progress-three':{'blocked_escape':True,'blocked_seconds':3.,'escape_metres':.10},
'progress-six':{'blocked_escape':True,'blocked_seconds':6.,'escape_metres':.10},
'progress-tight':{'blocked_escape':True,'blocked_seconds':3.,'escape_metres':.10,'turn_stop':5.},
}

def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as stream:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'progress-app'),'--seed','10000','--count','180','--layouts',str(H/'train-layouts.json'),'--no-frames','--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=stream,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=2) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  k,v=f.result();r[k]=v;print(k,json.dumps(v),flush=True);(H/'progress-summary.json').write_text(json.dumps(r,indent=2))
