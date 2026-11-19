from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
base={'cover_change':False,'support_change':False,'yield_enabled':False}
variants={'restart-only':{**base,'short_pass_only':False},'restart-pass':base,'restart-assigned':{**base,'assignment':True,'heading_weight':0.,'switch_margin':.15},'restart-defensive-support':{'cover_change':False,'support_defensive_only':True},'restart-deep-cover':{'support_change':False,'cover_gap':1.2},'restart-wide-cover':{'support_width':1.4,'cover_gap':1.2,'support_defensive_only':True}}
def run(item):
 name,tuning=item;out=H/(name+'.json')
 with out.with_suffix('.log').open('w') as f:subprocess.run([sys.executable,'-u',str(H/'evaluate.py'),'--app',str(H/'round4-app'),'--mode','candidate','--count','8','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 return name,{'tuning':tuning,**json.loads(out.read_text())['summary']}
r={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,x) for x in variants.items()]):
  name,v=f.result();r[name]=v;print(name,json.dumps(v),flush=True);(H/'round4-summary.json').write_text(json.dumps(r,indent=2))
