from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
'face-ball':{'face_real_ball':True},
'loose-turn':{'turn_stop':18.},
'tight-turn':{'turn_stop':5.},
'challenge-near':{'challenge_range':.30},
'challenge-far':{'challenge_range':.60},
'challenge-wide':{'challenge_side':.16},
'recover-lead':{'recovery_mode':'lead'},
'recover-near':{'recovery_mode':'near'},
}
def run(item):
 name,tuning=item
 with (H/(name+'.log')).open('w') as stream:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'experiment-app'),'--seed','10000','--count','180','--layouts',str(H/'train-layouts.json'),'--no-frames','--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))],stdout=stream,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=2) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  k,v=f.result();r[k]=v;print(k,json.dumps(v),flush=True);(H/'sweep-summary.json').write_text(json.dumps(r,indent=2))
