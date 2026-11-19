from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
variants={'recover-assignment':{},'recover-nearest':{'heading_weight':0.},'forward-chasers':{'forward_chase_only':True,'heading_weight':0.},'quick-nearest':{'heading_weight':0.,'switch_margin':.12},'zone-wide':{'heading_weight':0.,'support_width':1.4,'cover_gap':1.2},'no-defensive-intercept':{'heading_weight':0.,'defender_intercept':False}}
def run(item):
 name,tuning=item;out=H/(name+'.json')
 with out.with_suffix('.log').open('w') as f:subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'round2-app'),'--mode','candidate','--count','8','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads(out.read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,v=f.result();r[name]=v;print(name,json.dumps(v),flush=True);(H/'round2-summary.json').write_text(json.dumps(r,indent=2))
