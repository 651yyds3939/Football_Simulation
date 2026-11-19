"""Diagnose newly introduced timeouts; never substitute longer clocks into metrics."""
from pathlib import Path
import importlib.util,json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
spec=importlib.util.spec_from_file_location('extended_regressions',ROOT/'2D_Shared_Policy_2026-11-11/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b={r['seed']:r for r in json.loads((H/'baseline-holdout-v3.json').read_text())['runs']};c=json.loads((H/'production-holdout-v3.json').read_text())['runs'];layouts=json.loads((H/'holdout-layouts.json').read_text());rows=[]
for row in c:
 if row['outcome']!='TIMEOUT' or b[row['seed']]['outcome']=='TIMEOUT':continue
 seed=row['seed'];s=m.SharedScene(seed,seconds=600);setup=layouts[str(seed)];s.ball=list(setup['ball'])
 for name,point in setup['robots'].items():s.players[name].update(json.loads(json.dumps(point)),standing=True)
 while s.step():pass
 rows.append({**s.summary(),'baseline_outcome_180s':b[seed]['outcome'],'selected_outcome_180s':'TIMEOUT'})
print([(r['seed'],r['outcome'],round(r['seconds'],2)) for r in rows])
(H/'extended-regression-diagnostics.json').write_text(json.dumps({'runs':rows,'note':'Only newly introduced timeouts, selected after the held-out result. Diagnostic 600-second clock; not part of the 180-second performance results.'},indent=2))
