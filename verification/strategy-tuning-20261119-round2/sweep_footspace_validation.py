from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={
'footspace-validation-both':{'space_first':.20,'challenge_space':True},
'footspace-validation-defender-only':{'space_first':.20,'challenge_space':True},
'footspace-validation-attacker-only':{'space_first':.20,'challenge_space':True},
}

def run(item):
 name,tuning=item
 frozen=[]
 if name.endswith('defender-only'): frozen=['--freeze-name','RedForwardA','--baseline-navigation',str(H/'production-app/backend/Wenao/controllers/Utils/Navigation.py')]
 elif name.endswith('attacker-only'): frozen=['--freeze-name','BlueDefender','--baseline-navigation',str(H/'production-app/backend/Wenao/controllers/Utils/Navigation.py')]
 with (H/(name+'.log')).open('w') as stream:
  subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'footspace-app'),'--seed','13000','--count','300','--layouts',str(H/'validation-layouts.json'),'--no-frames','--tuning',json.dumps(tuning),'--output',str(H/(name+'.json'))]+frozen,stdout=stream,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads((H/(name+'.json')).read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  k,v=f.result();r[k]=v;print(k,json.dumps(v),flush=True);(H/'footspace-validation-summary.json').write_text(json.dumps(r,indent=2))
