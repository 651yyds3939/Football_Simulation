from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
base={'cover_change':False,'support_change':False,'yield_enabled':False}
variants={'pass-guard':('round3-app',base),'assignment':('round3-app',{**base,'assignment':True,'heading_weight':0.,'switch_margin':.15}),'restart':('round4-app',base),'restart-assigned':('round4-app',{**base,'assignment':True,'heading_weight':0.,'switch_margin':.15}),'restart-cover':('round4-app',{'support_change':False,'cover_gap':1.2})}
def run(item):
 name,(app,tuning)=item;out=H/('validation-'+name+'.json')
 with out.with_suffix('.log').open('w') as f:subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/app),'--mode','candidate','--seed','112000','--count','16','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'app':app,'tuning':tuning,**json.loads(out.read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,v=f.result();r[name]=v;print(name,json.dumps(v),flush=True);(H/'validation-summary.json').write_text(json.dumps(r,indent=2))
