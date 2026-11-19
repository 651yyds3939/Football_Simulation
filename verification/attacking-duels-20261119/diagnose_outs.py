from pathlib import Path
import importlib.util,json,collections,math
H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('out_app',H/'production-app/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.SharedScene._record=lambda self:None
rows=json.loads((H/'production-holdout-v3.json').read_text())['runs'];layouts=json.loads((H/'holdout-layouts.json').read_text());out=[]
for row in rows:
 if row['outcome']!='OUT':continue
 s=m.SharedScene(row['seed']);initial=layouts[str(row['seed'])];s.ball=list(initial['ball'])
 for n,p in initial['robots'].items():s.players[n].update(json.loads(json.dumps(p)),standing=True)
 states=collections.Counter()
 while True:
  previous=list(s.engine.previous) if s.engine.previous is not None else None
  before_ball=list(s.ball)
  guard={'restart_team':s.engine.restart_team,'restart_touch':s.engine.restart_touch,'last_touch':s.engine.last_touch,'indirect':s.engine.indirect,'kickoff_restriction':s.engine.kickoff_restriction}
  if not s.step():break
  states[s.current_decisions['RedForwardA'].behaviour]+=s.model.dt
 assert s.outcome=='OUT'
 from Utils.CourseSpecs import goal_crossing
 geometric=goal_crossing(previous,before_ball) if previous else None
 boundary='restart_guard_disallowed_goal' if geometric else 'touchline' if abs(s.ball[1])>3 else 'goal_line_outside_mouth'
 out.append({'geometric_goal':geometric,'last_restart_guard':guard,'seed':s.seed,'final_ball':s.ball,'terminal_touch':s.touch,'states':dict(states),'boundary':boundary})
result={'summary':dict(collections.Counter(x['boundary'] for x in out)),'runs':out}
(H/'out-diagnostics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
