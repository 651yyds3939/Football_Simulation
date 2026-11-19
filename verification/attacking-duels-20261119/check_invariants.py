from pathlib import Path
import ast,hashlib,importlib.util,json,math
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'2D_Shared_Policy_2026-11-11';BASE=H/'baseline-app'
def function(path,name):
 tree=ast.parse(path.read_text());return next(ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
checks={'physics_file_byte_identical':(APP/'backend/tools/soccer2d.py').read_bytes()==(BASE/'backend/tools/soccer2d.py').read_bytes()}
for name in ['route','interception','recovery_action']:
 p='backend/Wenao/controllers/Utils/DefensivePlan.py';checks[name+'_unchanged']=function(APP/p,name)==function(BASE/p,name)
p='backend/Wenao/controllers/Utils/TeamPolicy.py';checks['defensive_recovery_unchanged']=function(APP/p,'defensive_recovery')==function(BASE/p,'defensive_recovery')
selected=json.loads((H/'selected-before-holdout.json').read_text());checks['delivered_source_frozen_before_holdout']=all(hashlib.sha256((APP/n).read_bytes()).hexdigest()==digest for n,digest in selected['sha256'].items())
assert all(checks.values())
spec=importlib.util.spec_from_file_location('order_invariant',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.SharedScene._record=lambda self:None
layouts=json.loads((H/'train-layouts.json').read_text());step_count=0
for seed in range(80000,80020):
 scenes=[m.SharedScene(seed),m.SharedScene(seed)];initial=layouts[str(seed)]
 for s in scenes:
  s.ball=list(initial['ball'])
  for n,p in initial['robots'].items():s.players[n].update(json.loads(json.dumps(p)),standing=True)
 rev=scenes[1];rev.names=tuple(reversed(rev.names));rev.players=dict(reversed(list(rev.players.items())));rev.policies=dict(reversed(list(rev.policies.items())));rev.navigators=dict(reversed(list(rev.navigators.items())))
 while True:
  results=[s.step() for s in scenes];assert results[0]==results[1]
  one,two=scenes
  assert one.outcome==two.outcome
  for x,y in zip(one.ball+one.velocity,two.ball+two.velocity):assert abs(x-y)<1e-10,(seed,one.time,x,y)
  for name in one.names:
   a,b=one.players[name],two.players[name]
   for x,y in zip(a['position']+[a['yaw']],b['position']+[b['yaw']]):assert abs(x-y)<1e-10,(seed,one.time,name,x,y)
  step_count+=1
  if not results[0]:break
checks.update(reverse_player_update_order_cases=20,reverse_order_equal_steps=step_count)
(H/'invariants.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
