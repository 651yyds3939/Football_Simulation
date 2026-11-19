"""Inspect remaining held-out timeouts, without changing the selected policy."""
from pathlib import Path
from collections import Counter
import importlib.util,json,math
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=H/'baseline-app'
spec=importlib.util.spec_from_file_location('timeout_app',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base={r['seed']:r for r in json.loads((H/'baseline-holdout.json').read_text())['runs']};rows=json.loads((H/'baseline-holdout.json').read_text())['runs'];layouts=json.loads((H/'holdout-layouts.json').read_text());results=[]
for row in rows:
 if row['outcome']!='TIMEOUT':continue
 seed=row['seed'];s=m.SharedScene(seed,seconds=180);setup=layouts[str(seed)];s.ball=list(setup['ball'])
 for name,point in setup['robots'].items():s.players[name].update(json.loads(json.dumps(point)),standing=True)
 s.frames=[];s._record()
 while s.step():pass
 tail=[f for f in s.frames if f['t']>=150];ball=tail[-1]['ball'];movement=max(math.hypot(f['ball']['x']-ball['x'],f['ball']['y']-ball['y']) for f in tail)
 end=s.frames[-1];near=[math.hypot(end[k]['x']-ball['x'],end[k]['y']-ball['y']) for k in ('attacker','defender')]
 kind='still progressing' if movement>=.10 else 'stationary crowded ball' if max(near)<.65 else 'stationary separated alignment'
 results.append({'seed':seed,'baseline_outcome':base[seed]['outcome'],'kind':kind,'last_30s_ball_extent':movement,'distances':near,'final':end})
assert len(results)==83
(H/'baseline-timeout-diagnostics.json').write_text(json.dumps({'counts':dict(Counter(r['kind'] for r in results)),'rows':results,'note':'A posteriori diagnosis only; no policy selection or source edits based on this held-out data.'},indent=2))
print(Counter(r['kind'] for r in results),flush=True)
