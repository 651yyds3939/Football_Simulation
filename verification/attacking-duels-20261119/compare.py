from pathlib import Path
from collections import Counter
import json
H=Path(__file__).resolve().parent
def load(name):return json.loads((H/name).read_text())
def comparison(a,b):
 assert a['observer_schema']==b['observer_schema']==3
 assert [r['seed'] for r in a['runs']]==[r['seed'] for r in b['runs']]
 pairs=list(zip(a['runs'],b['runs']))
 both=[(x,y) for x,y in pairs if x['frontal_contact_at'] is not None and y['frontal_contact_at'] is not None]
 baseline_contact=[(x,y) for x,y in pairs if x['frontal_contact_at'] is not None]
 return {'baseline':a['summary'],'candidate':b['summary'],'outcome_transitions':dict(Counter(x['outcome']+' -> '+y['outcome'] for x,y in pairs)),
 'paired_frontal_contact_in_both':{'runs':len(both),'baseline_results':dict(Counter(x['frontal_contact_result'] for x,y in both)),'candidate_results':dict(Counter(y['frontal_contact_result'] for x,y in both))},
 'fixed_baseline_frontal_cohort':{'runs':len(baseline_contact),'baseline_outcomes':dict(Counter(x['outcome'] for x,y in baseline_contact)),'candidate_outcomes':dict(Counter(y['outcome'] for x,y in baseline_contact))}}
results={}
for name,a,b in [('validation','baseline-validation-v3.json','production-validation-v3.json'),('headon','headon-baseline-v3.json','production-headon-v3.json'),('holdout','baseline-holdout-final.json','production-holdout-final.json'),('headon_holdout','baseline-headon-holdout-final.json','production-headon-holdout-final.json')]:
 if (H/a).exists() and (H/b).exists():results[name]=comparison(load(a),load(b))
(H/'comparison-v3.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
