from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import subprocess,json,sys
H=Path(__file__).resolve().parent
jobs=[]
for label,app in [('baseline','baseline-corrected-app'),('production','production-app')]:
 for group,seed,count,layouts in [('holdout',90000,1000,'holdout-layouts.json'),('headon-holdout',96000,200,'headon-holdout-layouts.json')]:jobs.append((label,app,group,seed,count,layouts))
def run(job):
 label,app,group,seed,count,layouts=job;out=H/(label+'-'+group+'-final.json')
 with out.with_suffix('.log').open('w') as f:
  subprocess.run([sys.executable,'-u',str(H/'evaluate_v3.py'),'--app',str(H/app),'--seed',str(seed),'--count',str(count),'--layouts',str(H/layouts),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 print(out.name,json.dumps(json.loads(out.read_text())['summary']),flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,x) for x in jobs]):future.result()
