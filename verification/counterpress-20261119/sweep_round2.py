from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
'loss-margin-eight':{},
'loss-margin-sixteen':{'press_loss_margin':.16},
'loss-escape-only':{'press_loss_margin':0.},
'regain-hold-two':{'regain_hold':2.},
'regain-hold-five':{'regain_hold':5.},
'press-route':{'press_navigation':'route','press_mode':'arrival'},
'press-space-safe':{'defender_space':True},
}

def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as stream:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'round2-app'),'--seed','50000','--count','240','--layouts',str(H/'train-layouts.json'),'--no-frames','--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=stream,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  k,v=f.result();r[k]=v;print(k,json.dumps(v),flush=True);(H/'round2-summary.json').write_text(json.dumps(r,indent=2))
