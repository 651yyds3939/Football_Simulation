"""Run explicitly named policy candidates on training layouts only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
variants = {
    'direct': {'prediction':'direct', 'face_weight':0., 'plan_seconds':.7},
    'pursuit-half': {'prediction':'pursuit', 'lead':.5, 'face_weight':.25, 'plan_seconds':.8},
    'pursuit-one': {'prediction':'pursuit', 'lead':1., 'face_weight':.25, 'plan_seconds':.8},
    'pursuit-long': {'prediction':'pursuit', 'lead':1.5, 'face_weight':.25, 'plan_seconds':.8},
    'lane': {'prediction':'lane', 'face_weight':.4, 'plan_seconds':1.2},
    'arrival-facing': {'prediction':'arrival', 'face_weight':1., 'plan_seconds':1.2},
    'arrival-body': {'prediction':'arrival', 'face_weight':0., 'plan_seconds':.6},
}

def run(item):
    name, tuning = item
    output = HERE/('sweep-'+name+'.json')
    log = HERE/('sweep-'+name+'.log')
    with log.open('w') as stream:
        subprocess.run([sys.executable,'-u',str(HERE/'evaluate.py'),'--seed','347','--count','150',
                        '--layouts',str(HERE/'rectangular-layouts-train.json'),
                        '--tuning',json.dumps(tuning),'--output',str(output)],
                       cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    result = json.loads(output.read_text())['summary']
    return name, {'tuning':tuning, **result}

results = {}
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [pool.submit(run,item) for item in variants.items()]
    for future in as_completed(futures):
        name, result = future.result()
        results[name] = result
        print(name,json.dumps(result),flush=True)
        (HERE/'sweep-summary.json').write_text(json.dumps(results,indent=2)+'\n')
