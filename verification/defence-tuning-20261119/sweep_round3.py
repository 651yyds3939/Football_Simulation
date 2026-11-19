"""Run explicitly named policy candidates on training layouts only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
variants = {'slot-six': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3, 'lane_width': 0.06}, 'slot-ten': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3, 'lane_width': 0.1}, 'slot-fourteen': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3, 'lane_width': 0.14}, 'slot-close': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.22, 'lane_width': 0.08}, 'front-axis': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3, 'axis_priority': 'time'}, 'front-slot': {'prediction': 'arrival', 'face_weight': 0.0, 'plan_seconds': 0.6, 'buffer': 0.3, 'lane_width': 0.08, 'axis_priority': 'time'}}

def run(item):
    name, tuning = item
    output = HERE/('round3-'+name+'.json')
    log = HERE/('round3-'+name+'.log')
    with log.open('w') as stream:
        subprocess.run([sys.executable,'-u',str(HERE/'evaluate.py'),'--app',str(HERE/'experiment-app'),'--seed','347','--count','150',
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
        (HERE/'round3-summary.json').write_text(json.dumps(results,indent=2)+'\n')
