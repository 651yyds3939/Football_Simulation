"""Fixed-state breakaway diagnostics; no change to motion or ball parameters."""
from pathlib import Path
import argparse
import importlib.util
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
if args.output.exists():
    parser.error('Use a fresh output directory')
args.output.mkdir(parents=True)
spec = importlib.util.spec_from_file_location('recovery_scene', ROOT/'2D_Shared_Policy_2026-11-11/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rows = []
for case, point in [('beaten', [.75, .38]), ('just_beaten', [1., .35]),
                    ('wide_beaten', [.7, 1.]), ('goal_side', [1.8, .15])]:
    for direction in (1, -1):
        scene = module.SharedScene(seed=27, seconds=100)
        scene.engine.red_direction = direction
        scene.ball = [direction*1.2, 0., .07]
        scene.velocity = [0., 0., 0.]
        scene.players['RedForwardA'].update(position=[direction*.95, -direction*.05, .334], yaw=0 if direction==1 else math.pi)
        scene.players['BlueDefender'].update(position=[direction*point[0], direction*point[1], .334], yaw=math.pi if direction==1 else 0)
        scene.initial_setup = {'ball': list(scene.ball), 'robots': scene.observation()['robots']}
        scene.frames = []
        scene._record()
        initial = scene.players['BlueDefender']['position'][:2]
        first = at_three = None
        first_motion_time = None
        recover_steps = 0
        while scene.step():
            state = scene.snapshot()
            if first is None:
                first = state['defender']
            own = scene.players['BlueDefender']['position']
            if first_motion_time is None and math.dist(initial, own[:2]) > .01:
                first_motion_time = scene.time
            if at_three is None and scene.time>=3-1e-9:
                at_three = {'state': state['defender'], 'displacement': math.dist(initial, own[:2]),
                            'goalward_metres': direction*(own[0]-initial[0])}
            recover_steps += scene.current_decisions['BlueDefender'].behaviour == 'RECOVER_DEFENCE'
        report = scene.report()
        stem = case+('-normal' if direction==1 else '-mirrored')
        (args.output/(stem+'.json')).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        (args.output/(stem+'.html')).write_text(module.replay_html(scene), encoding='utf-8')
        row = {'case': case, 'direction': direction, 'first': first, 'at_three_seconds': at_three,
               'first_translation_over_1cm_seconds': first_motion_time,
               'recovery_requested_seconds': recover_steps*scene.model.dt, **scene.summary()}
        rows.append(row)
        print(stem, 'first', first['action'], first['stage'], '3s', round(at_three['displacement'],4),
              'first1cm', first_motion_time, 'end', scene.outcome, round(scene.time,2))
(args.output/'results.json').write_text(json.dumps({'runs': rows, 'source': module.source_info(),
    'model': module.envelope(scene)['parameters']}, indent=2)+'\n', encoding='utf-8')
