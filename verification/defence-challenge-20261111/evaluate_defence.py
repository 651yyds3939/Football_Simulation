"""Compare observed close contests, active-foot recovery and sustained stalls.

Instrumentation observes _contact calls; it does not choose actions or alter state.
"""
from pathlib import Path
from collections import Counter
import argparse
import importlib.util
import inspect
import hashlib
import json
import math
import sys
import time
import types
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--bundled', action='store_true')
p.add_argument('--baseline-bundle', type=Path, help='Load backend from a preserved old ZIP without changing the current package')
p.add_argument('--count', type=int, default=100)
p.add_argument('--seed', type=int, default=47)
p.add_argument('--fixtures', action='store_true')
p.add_argument('--previous-policy', action='store_true', help='Ablation: current 2D model with pre-change policy/navigation')
a = p.parse_args()
if a.output.exists():
    p.error('Use a fresh output directory')
a.output.mkdir(parents=True)
saved_backend = None
if a.baseline_bundle:
    if a.bundled or a.previous_policy:
        p.error('--baseline-bundle is separate from --bundled and --previous-policy')
    baseline_temp = tempfile.TemporaryDirectory(prefix='defence-baseline-')
    with zipfile.ZipFile(a.baseline_bundle) as archive:
        archive.extractall(baseline_temp.name)
    saved_backend = next(Path(baseline_temp.name).rglob('backend/tools/soccer2d.py')).parents[1]
    sys.path.insert(0, str(saved_backend/'tools'))
    importlib.import_module('soccer2d')  # Keep this backend cached when importing the display adapter.
spec = importlib.util.spec_from_file_location('defence_metrics', ROOT/'2D_Shared_Policy_2026-11-11/server.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if saved_backend:
    m.REPOSITORY = saved_backend
    m.SOURCE_FILES = [name for name in m.SOURCE_FILES if (saved_backend/name).exists()]
    m.source_info.cache_clear()
if a.previous_policy:
    if a.bundled:
        p.error('Use --previous-policy with the current model, without --bundled')
    old = {}
    for name in ('TeamPolicy', 'Navigation'):
        old_spec = importlib.util.spec_from_file_location('before_challenge_'+name, HERE/'before'/(name+'.py'))
        old[name] = importlib.util.module_from_spec(old_spec)
        sys.modules[old_spec.name] = old[name]
        old_spec.loader.exec_module(old[name])
    base_scene = m.SharedScene
    class PreviousPolicyScene(base_scene):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for name in self.names:
                self.policies[name] = old['TeamPolicy'].TeamPolicy(name, goal_depth=.30 if self.profile.locomotion=='guarded' else 0,
                    finishing_nearest=self.profile.finishing_aim=='nearest', support_mode=self.profile.support_mode)
                self.navigators[name] = old['Navigation'].Navigator()
    m.SharedScene = PreviousPolicyScene
    labelled_source = json.loads(json.dumps(m.source_info()))
    labelled_source['kind'] = 'current model with explicit pre-change policy/navigation snapshot'
    for name in ('TeamPolicy', 'Navigation'):
        labelled_source['sha256']['Wenao/controllers/Utils/'+name+'.py'] = hashlib.sha256((HERE/'before'/(name+'.py')).read_bytes()).hexdigest()
    m.source_info = lambda: labelled_source


def instrument(scene):
    original = scene._contact
    contacts = []
    def record(self, name, *args, **kwargs):
        source = kwargs.get('source', args[0] if args else None)
        if source is None:
            source = {'step':'push', '_finish_kick':'kick'}.get(inspect.currentframe().f_back.f_code.co_name, 'body')
        if source != 'body':
            contacts.append((self.time, name, source, self.ball[:2]))
        return original(name, *args, **kwargs)
    scene._contact = types.MethodType(record, scene)
    return contacts


def run(scene, direction, label, save=False):
    contacts = instrument(scene)
    seen = 0
    last_foot = anchor = None
    close_seconds = max_stall = 0.
    stalled_since = stalled_ball = None
    encountered = regained = breakthrough = False
    first_regain = None
    while scene.step():
        for contact in contacts[seen:]:
            if last_foot != contact[1]:
                last_foot, anchor = contact[1], contact
        seen = len(contacts)
        red = scene.players['RedForwardA']['position']
        blue = scene.players['BlueDefender']['position']
        ball = scene.ball
        close = math.dist(red[:2], blue[:2]) < .40 and max(math.dist(p[:2], ball[:2]) for p in (red, blue)) < .50
        encountered |= close
        if close:
            close_seconds += scene.model.dt
            if stalled_since is None or math.dist(stalled_ball, ball[:2]) > .06:
                stalled_since, stalled_ball = scene.time, ball[:2]
            max_stall = max(max_stall, scene.time-stalled_since)
        else:
            stalled_since = stalled_ball = None
        if (anchor and last_foot == 'BlueDefender' and direction*(ball[0]-anchor[3][0]) < -.25
                and math.dist(blue[:2], ball[:2]) < .50):
            regained = True
            if first_regain is None:
                first_regain = scene.time
        if (encountered and last_foot == 'RedForwardA' and direction*(ball[0]-blue[0]) > .20
                and math.dist(red[:2], ball[:2]) < .40):
            breakthrough = True
    row = {**scene.summary(), 'case':label, 'direction':direction, 'close_encounter':encountered,
           'controlled_left_progress':regained, 'first_controlled_left_progress':first_regain,
           'attacker_broke_through_after_contact':breakthrough,
           'close_seconds':close_seconds, 'longest_close_stall':max_stall,
           'exclusive_blue_foot_calls':sum(c[1]=='BlueDefender' for c in contacts)}
    if save:
        # Remove observer closure before deepcopy used by replay export.
        del scene._contact
        (a.output/(label+'.json')).write_text(json.dumps(scene.report(),indent=2)+'\n',encoding='utf-8')
        (a.output/(label+'.html')).write_text(m.replay_html(scene),encoding='utf-8')
    return row


started = time.perf_counter()
rows = []
if a.fixtures:
    for name, blue in [('frontal',[1.8,0]),('shoulder',[1.8,.15]),('other_shoulder',[1.8,-.15]),
                       ('wide',[1.6,1.2]),('beaten',[.75,.38])]:
        for direction in (1,-1):
            scene = m.SharedScene(seed=27,seconds=180)
            scene.engine.red_direction = direction
            scene.ball, scene.velocity = [direction*1.2,0,.07],[0,0,0]
            scene.players['RedForwardA'].update(position=[direction*.95,-direction*.05,.334],yaw=0 if direction==1 else math.pi)
            scene.players['BlueDefender'].update(position=[direction*blue[0],direction*blue[1],.334],yaw=math.pi if direction==1 else 0)
            scene.initial_setup={'ball':scene.ball[:],'robots':json.loads(json.dumps(scene.players))}
            scene.frames=[]
            scene._record()
            rows.append(run(scene,direction,name+('-normal' if direction==1 else '-mirrored'),save=True))
else:
    for seed in range(a.seed,a.seed+a.count):
        scene=m.SharedScene(seed=seed,seconds=180)
        rows.append(run(scene,1,str(seed)))
summary={'runs':len(rows),'outcomes':dict(Counter(r['outcome'] for r in rows)),
         'close_encounters':sum(r['close_encounter'] for r in rows),
         'controlled_left_progress_runs':sum(r['controlled_left_progress'] for r in rows),
         'breakthrough_after_contact_runs':sum(r['attacker_broke_through_after_contact'] for r in rows),
         'close_stalls_over_10s':sum(r['longest_close_stall']>10 for r in rows),
         'close_stalls_over_20s':sum(r['longest_close_stall']>20 for r in rows),
         'mean_close_seconds':sum(r['close_seconds'] for r in rows)/len(rows),
         'wall_seconds':time.perf_counter()-started}
result={'summary':summary,'runs':rows,'source':m.source_info(),
        'definitions':{'close':'players <0.40m apart and both <0.50m from ball',
                       'controlled_left_progress':'last exclusive active-foot toucher is defender, ball moved >=0.25m toward its attacking end in that episode, defender still within 0.50m',
                       'stall':'close encounter with ball staying within 0.06m of its local anchor',
                       'limits':'Approximate 2D observations, not validated possession, referee results or physical tackles. Recovery and breakthrough can both occur in one run.'}}
(a.output/'metrics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
if a.fixtures:
    for r in rows:print(r['case'],r['outcome'],round(r['seconds'],2),'recovery',r['controlled_left_progress'],'stall',round(r['longest_close_stall'],2))
