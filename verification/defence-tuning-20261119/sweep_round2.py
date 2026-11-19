"""Run explicitly named policy candidates on training layouts only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
variants = {'buffer-small': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.12}, 'buffer-large': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3}, 'buffer-wait': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.38}, 'plan-reactive': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.2, 'buffer': 0.22}, 'plan-stable': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 1.6, 'buffer': 0.22}, 'pressure-early': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'tackle': 'kick', 'tackle_wait': 0.4}, 'pressure-one': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'tackle': 'kick', 'tackle_wait': 1.0}, 'pressure-late': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'tackle': 'kick', 'tackle_wait': 3.0}}

def run(item):
    name, tuning = item
    output = HERE/('round2-'+name+'.json')
    log = HERE/('round2-'+name+'.log')
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
        (HERE/'round2-summary.json').write_text(json.dumps(results,indent=2)+'\n')
