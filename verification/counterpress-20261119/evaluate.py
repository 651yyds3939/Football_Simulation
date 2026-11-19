"""Matched-seed 1v1 measurements; the observer does not change decisions."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
p = argparse.ArgumentParser()
p.add_argument('--app', type=Path, default=ROOT/'2D_Shared_Policy_2026-11-11')
p.add_argument('--seed', type=int, default=347)
p.add_argument('--count', type=int, default=100)
p.add_argument('--seconds', type=float, default=180)
p.add_argument('--layouts', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--trace', type=int, nargs='*', default=[])
p.add_argument('--tuning', type=json.loads, default={})
p.add_argument('--no-frames', action='store_true')
p.add_argument('--freeze-name', choices=['RedForwardA','BlueDefender'])
p.add_argument('--baseline-navigation', type=Path)
a = p.parse_args()
if a.output.exists():
    p.error('Use a fresh result path')
a.output.parent.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('measured_app', a.app/'server.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source_at_start = m.source_info()
if a.no_frames and not a.trace:
    m.SharedScene._record = lambda self: None
if a.tuning:
    from Utils.DefensivePlan import SETTINGS
    SETTINGS.update(a.tuning)
frozen_navigation = None
if a.freeze_name:
    if a.baseline_navigation is None:
        p.error('--freeze-name requires --baseline-navigation')
    navspec=importlib.util.spec_from_file_location('frozen_navigation',a.baseline_navigation)
    frozen_navigation=importlib.util.module_from_spec(navspec);navspec.loader.exec_module(frozen_navigation)
layouts = json.loads(a.layouts.read_text()) if a.layouts else None
rows = []
started = time.perf_counter()
for seed in range(a.seed, a.seed+a.count):
    scene = m.SharedScene(seed=seed, seconds=a.seconds)
    if frozen_navigation:
        scene.navigators[a.freeze_name] = frozen_navigation.Navigator()
    if layouts:
        initial = layouts[str(seed)]
        scene.ball = list(initial['ball'])
        for name, point in initial['robots'].items():
            scene.players[name].update(json.loads(json.dumps(point)), standing=True)
        scene.velocity = list(initial.get('velocity', [0,0,0]))
        scene.touch = initial.get('touch')
        scene.engine.last_touch = scene.touch
        scene.initial_setup = initial
        scene.frames = []
        scene._record()
    action_seconds = Counter()
    state_seconds = Counter()
    behind_seconds = close_seconds = stalled = max_stall = 0.
    anchor = None
    first_blue_control = first_retreat = None
    contact_anchor = None
    seen = 0
    red_states = Counter()
    blue_had_foot = scene.touch == 'BlueDefender'
    if blue_had_foot:
        first_blue_control = 0.
    regained = False
    re_gain_count = 0
    loss_seconds = wrong_heading_seconds = alignment_under_loss = 0.
    press_seconds = 0.
    heading_error_integral = 0.
    productive_regain = False
    regain_anchor = None
    while scene.step():
        dt = scene.model.dt
        defender = scene.players['BlueDefender']['position']
        attacker = scene.players['RedForwardA']['position']
        ball = scene.ball
        action_seconds[scene.last_actions.get('BlueDefender', 'stand')] += dt
        decision = scene.current_decisions.get('BlueDefender')
        state_seconds[decision.behaviour if decision else 'WAIT'] += dt
        behind_seconds += dt*(defender[0] < ball[0]-.15)
        close = math.dist(attacker[:2], defender[:2]) < .42 and max(
            math.dist(x[:2], ball[:2]) for x in (attacker, defender)) < .5
        close_seconds += dt*close
        if close and anchor and math.dist(ball[:2], anchor) < .06:
            stalled += dt
            max_stall = max(max_stall, stalled)
        else:
            stalled = 0.
            anchor = tuple(ball[:2]) if close else None
        for event in scene.events[seen:]:
            if event['event'] == 'foot_control_change':
                contact_anchor = (event['robot'], event['point'])
                if event['robot'] == 'BlueDefender' and first_blue_control is None:
                    first_blue_control = scene.time
        for event in scene.events[seen:]:
            if event['event']=='foot_control_change':
                if event['robot']=='BlueDefender':
                    blue_had_foot = True
                    regain_anchor = None
                elif event['robot']=='RedForwardA' and blue_had_foot:
                    regained = True
                    regain_anchor = tuple(ball[:2])
                    re_gain_count += 1
                    blue_had_foot = False
        if regain_anchor and ball[0]>=regain_anchor[0]+.30 and scene.touch=='RedForwardA':
            productive_regain = True
            regain_anchor = None
        red = scene.current_decisions.get('RedForwardA')
        red_states[red.behaviour if red else 'WAIT'] += dt
        if red and red.behaviour in ('COUNTERPRESS','PRESS_CONTAIN','RECOVER_BALL'):
            press_seconds += dt
        if blue_had_foot and math.dist(attacker[:2],ball[:2])>.32:
            loss_seconds += dt
            yaw = scene.players['RedForwardA']['yaw']
            bearing = math.atan2(ball[1]-attacker[1],ball[0]-attacker[0])
            error = abs((bearing-yaw+math.pi)%(2*math.pi)-math.pi)
            wrong_heading_seconds += dt*(error>math.pi/2)
            heading_error_integral += dt*math.degrees(error)
            alignment_under_loss += dt*(scene.navigation_stages.get('RedForwardA') in ('FACE_KICK_DIRECTION','ALIGN_FOOT_LATERALLY'))
        seen = len(scene.events)
        if (contact_anchor and contact_anchor[0] == 'BlueDefender'
                and ball[0] < contact_anchor[1][0]-.5 and scene.touch != 'RedForwardA'
                and first_retreat is None):
            first_retreat = scene.time
    assert abs(sum(red_states.values())-(scene.time-scene.model.dt))<1e-6, 'Incomplete per-step attacker observer'
    row = {**scene.summary(), 'defender_actions_seconds': dict(action_seconds),
           'defender_states_seconds': dict(state_seconds), 'behind_ball_seconds': behind_seconds,
           'close_seconds': close_seconds, 'longest_stall_seconds': max_stall,
           'first_defender_foot_control': first_blue_control, 'first_controlled_retreat': first_retreat,
           'clearance_completed': scene.clearances_completed > 0,
           'defender_action_transitions': scene.stats['BLUE']['action_transitions'],
           'attacker_states_seconds':dict(red_states), 'attacker_regained_foot_after_loss':regained,
           'attacker_regain_count':re_gain_count,'attacker_loss_seconds':loss_seconds,
           'attacker_wrong_heading_seconds':wrong_heading_seconds,
           'attacker_alignment_while_lost_seconds':alignment_under_loss,
           'attacker_press_seconds':press_seconds,
           'attacker_heading_error_integral':heading_error_integral, 'terminal_touch':scene.touch, 'productive_regain':productive_regain}
    rows.append(row)
    if seed in a.trace:
        (a.output.parent/(a.output.stem+'-'+str(seed)+'-trace.json')).write_text(
            json.dumps(scene.report(), separators=(',', ':'))+'\n')
    if len(rows) % 20 == 0:
        print('PROGRESS',len(rows),dict(Counter(r['outcome'] for r in rows)),
              round(time.perf_counter()-started,2),flush=True)
n = len(rows)
result = {'summary': {'runs': n, 'outcomes': dict(Counter(r['outcome'] for r in rows)),
    'defender_foot_control_runs': sum(r['first_defender_foot_control'] is not None for r in rows),
    'controlled_retreat_runs': sum(r['first_controlled_retreat'] is not None for r in rows),
    'clearance_completed_runs': sum(r['clearance_completed'] for r in rows),
    'stalls_over_20s': sum(r['longest_stall_seconds'] > 20 for r in rows),
    'mean_turn_seconds': sum(sum(v for k,v in r['defender_actions_seconds'].items()
                                 if k.startswith(('left','right'))) for r in rows)/n,
    'mean_behind_ball_seconds': sum(r['behind_ball_seconds'] for r in rows)/n,
    'mean_duration_seconds': sum(r['seconds'] for r in rows)/n,
    'attacker_productive_regain_runs':sum(r['productive_regain'] for r in rows),
    'attacker_regain_runs':sum(r['attacker_regained_foot_after_loss'] for r in rows),
    'attacker_loss_runs':sum(r['first_defender_foot_control'] is not None for r in rows),
    'mean_attacker_wrong_heading_seconds':sum(r['attacker_wrong_heading_seconds'] for r in rows)/n,
    'mean_attacker_alignment_while_lost_seconds':sum(r['attacker_alignment_while_lost_seconds'] for r in rows)/n,
    'mean_attacker_press_seconds':sum(r['attacker_press_seconds'] for r in rows)/n,
    'loss_weighted_attacker_heading_error_degrees':sum(r['attacker_heading_error_integral'] for r in rows)/max(1e-9,sum(r['attacker_loss_seconds'] for r in rows)),
    'wall_seconds': time.perf_counter()-started}, 'runs': rows, 'observer_schema': 3, 'source': source_at_start, 'tuning': a.tuning,
    'frozen_navigation_for': a.freeze_name, 'frozen_navigation_sha256': hashlib.sha256(a.baseline_navigation.read_bytes()).hexdigest() if a.baseline_navigation else None, 'limits': 'Timeout and OUT are not automatically defensive wins. Controlled retreat requires exclusive active-foot evidence plus 0.5 m retreat; a later attacker goal can still occur.'}
a.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result['summary'], indent=2), flush=True)
