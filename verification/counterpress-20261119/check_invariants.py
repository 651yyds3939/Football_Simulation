"""Verify that terminal scheduling is the only simulator change."""
from pathlib import Path
import ast,hashlib,json
H=Path(__file__).resolve().parent
old=ast.parse((H/'baseline-app/backend/tools/soccer2d.py').read_text());new=ast.parse((H/'production-app/backend/tools/soccer2d.py').read_text())
def named(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name)
def dump(n):return ast.dump(n,include_attributes=False)
checks={name:dump(named(old,name))==dump(named(new,name)) for name in ['Model','_finish_kick','_ball_body_penetration','_body_clear_of_ball','_limit_body_motion_at_ball','_roll_ball']}
a=named(old,'step');b=named(new,'step');b.body=[n for n in b.body if not(isinstance(n,ast.If) and isinstance(n.test,ast.Call) and isinstance(n.test.func,ast.Attribute) and n.test.func.attr=='_stop_after_referee')]
checks['step_identical_except_terminal_hook']=dump(a)==dump(b)
checks['attack_decision_function_unchanged']=dump(named(ast.parse((H/'baseline-app/backend/Wenao/controllers/Utils/TeamPolicy.py').read_text()),'attack'))==dump(named(ast.parse((H/'production-app/backend/Wenao/controllers/Utils/TeamPolicy.py').read_text()),'attack'))
assert all(checks.values()),checks
(H/'invariants.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
