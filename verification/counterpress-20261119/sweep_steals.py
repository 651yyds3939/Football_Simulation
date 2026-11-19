from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
'steal-press-safe':{'defender_space':True},
'steal-space-only':{'defender_space':True,'press_enabled':False},
}

def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as stream:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'finalist-app'),'--seed','70000','--count','80','--layouts',str(H/'steal-layouts.json'),'--no-frames','--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=stream,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  k,v=f.result();r[k]=v;print(k,json.dumps(v),flush=True);(H/'steal-summary.json').write_text(json.dumps(r,indent=2))
