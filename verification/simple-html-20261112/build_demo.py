"""Build five offline examples using the current shared Python policy."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT/'2D_Shared_Policy_2026-11-11'
spec = importlib.util.spec_from_file_location('five_example_source', DEMO/'server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = [('defence', 355, 'CLEARED_GOAL'), ('attack', 347, 'GOAL'),
         ('attack_b', 348, 'GOAL'), ('defence_b', 351, 'CLEARED_GOAL'),
         ('timeout', 366, 'TIMEOUT')]
recordings, summaries = [], []
evidence = Path(__file__).with_name('recordings')
evidence.mkdir(exist_ok=True)
for kind, seed, expected in cases:
    scene = module.SharedScene(seed=seed, scenario='random', seconds=180)
    while scene.step():
        pass
    assert scene.outcome == expected, (seed, scene.outcome, expected)
    data = {**module.envelope(scene), 'frames': scene.frames}
    (evidence/(str(seed)+'.json')).write_text(json.dumps(data, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    # Preserve the two previously shared examples exactly, including all frames.
    old_file = {'defence': 'defence_replay.html', 'attack': 'example_replay.html'}.get(kind)
    if old_file:
        original = (DEMO/old_file).read_text(encoding='utf-8')
        start = original.index('window.PYTHON_REPLAY=')+len('window.PYTHON_REPLAY=')
        old, _ = json.JSONDecoder().raw_decode(original[start:])
        assert data['frames'] == old['frames']
        assert data['source']['sha256'] == old['source']['sha256']
    recordings.append({'kind': kind, 'seed': seed, 'frames': data['frames'],
                       'parameters': data['parameters'], 'source': data['source'], 'profile': data['profile']})
    summaries.append({**scene.summary(), 'frames': len(scene.frames)})

viewer = (DEMO/'viewer.html').read_text(encoding='utf-8')
drawing = viewer[viewer.index("const canvas=$('pitch')"):viewer.index('async function advance(steps)')]
assert 'function draw()' in drawing and 'fetch(' not in drawing
template = (Path(__file__).with_name('template.html')).read_text(encoding='utf-8')
payload = json.dumps(recordings, separators=(',', ':'), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
output = template.replace('__RECORDINGS__', payload).replace('__DRAWING__', drawing)
assert 'fetch(' not in output and '__RECORDINGS__' not in output and '__DRAWING__' not in output
target = ROOT/'Football_1v1_Demo.html'
target.write_text(output, encoding='utf-8')
(evidence/'summary.json').write_text(json.dumps(summaries, indent=2)+'\n', encoding='utf-8')
print(str(target))
print('Bytes:', target.stat().st_size)
for row in summaries:
    print(row['seed'], row['outcome'], round(row['seconds'], 2))
