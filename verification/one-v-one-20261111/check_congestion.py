"""Compare fixed 1v1 seeds; preserve failures and model/source versions."""
from pathlib import Path
from collections import Counter
import importlib.util
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('congestion_check', ROOT/'2D_Shared_Policy_2026-11-11/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rows = []
for seed in (309071988, *range(27, 47)):
    scene = module.SharedScene(seed=seed, scenario='random', seconds=180)
    episodes, previous = 0, {}
    while scene.step():
        for name, decision in scene.current_decisions.items():
            if decision.behaviour == 'DUEL_ESCAPE' and previous.get(name) != decision.behaviour:
                episodes += 1
            previous[name] = decision.behaviour
    rows.append({**scene.summary(), 'escape_episodes': episodes})
    if seed in (309071988, 37):
        (HERE/f'blocked-final-seed-{seed}.json').write_text(json.dumps(scene.report(), indent=2)+'\n', encoding='utf-8')
        (HERE/f'blocked-final-seed-{seed}.html').write_text(module.replay_html(scene), encoding='utf-8')
(HERE/'blocked-final-21.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
baseline = json.loads((HERE/'blocked-baseline.json').read_text(encoding='utf-8'))
result = {
    'seeds': [27, 46], 'duration_cap': 180, 'scenario': 'random',
    'baseline_outcomes': dict(Counter(row['outcome'] for row in baseline[1:])),
    'final_outcomes': dict(Counter(row['outcome'] for row in rows[1:])),
    'live_capture_seed_before': {k: baseline[0][k] for k in ('seed', 'outcome', 'seconds')},
    'live_capture_seed_after': rows[0],
    'remaining_timeout_seeds': [row['seed'] for row in rows[1:] if row['outcome'] == 'TIMEOUT'],
    'source': module.source_info(),
    'limits': ['Both the 2D rebound calculation and shared recovery policy changed.',
               'Outcomes are for this approximate 2D model, not general performance or 3D success.',
               'The screenshot did not show its seed; a similar stationary duel was reproduced from the live server seed.']}
(HERE/'blocked-comparison.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('source', 'live_capture_seed_after')}, indent=2))
print('Live-seed final:', rows[0]['outcome'], rows[0]['seconds'])
