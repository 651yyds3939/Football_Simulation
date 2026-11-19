"""Live/batch 1v1 exercise using the local Python policy modules."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import copy
import hashlib
from functools import lru_cache
import json
import math
import os
import random
import secrets
import sys
import threading
import time
import webbrowser

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE/'backend'
sys.path.insert(0, str(REPOSITORY/'tools'))
from soccer2d import Model, Simulation
from Utils.PolicyProfile import PolicyProfile
from Utils.CourseSpecs import BALL_RADIUS
from Utils.MatchEngine import MatchEngine, MatchConfig
from Utils.SpawnZones import SpawnZones

NAMES = ('RedForwardA', 'BlueDefender')
SOURCE_FILES = ['tools/soccer2d.py', 'Wenao/controllers/Utils/PolicyProfile.py',
                'Wenao/controllers/Utils/TeamPolicy.py', 'Wenao/controllers/Utils/Navigation.py',
                'Wenao/controllers/Utils/CourseSpecs.py', 'Wenao/controllers/Utils/MatchEngine.py',
                'Wenao/controllers/Utils/DefensivePlan.py', 'Wenao/controllers/Utils/SpawnZones.py']


@lru_cache(maxsize=1)
def source_info():
    return {'kind': 'local snapshot',
            'modules': ['Utils.TeamPolicy.TeamPolicy.decide', 'Utils.Navigation.Navigator.choose'],
            'sha256': {name: hashlib.sha256((REPOSITORY/name).read_bytes()).hexdigest() for name in SOURCE_FILES}}


def starting_layout(seed, scenario, spawn_zones=None):
    if scenario == 'random':
        return SpawnZones.parse(spawn_zones).sample(seed, BALL_RADIUS)
    fixtures = {
        'duel': ([-1.8, -.25, .334], [-1.5, -.2, BALL_RADIUS], [.05, -.15, .334]),
        'lane': ([1.1, -.95, .334], [1.42, -.9, BALL_RADIUS], [2.3, 1.1, .334]),
        'shot': ([3.65, -.50, .334], [3.94, -.45, BALL_RADIUS], [4.3, -.10, .334]),
        'breakaway': ([.95, -.05, .334], [1.2, 0, BALL_RADIUS], [2.1, .65, .334]),
        'block': ([.95, -.05, .334], [1.2, 0, BALL_RADIUS], [1.8, 0, .334]),
    }
    if scenario not in fixtures:
        raise ValueError('Unknown starting scenario')
    own, ball, other = fixtures[scenario]
    return {'ball': ball, 'robots': {NAMES[0]: {'position': own, 'yaw': 0},
                                   NAMES[1]: {'position': other, 'yaw': math.atan2(ball[1]-other[1], ball[0]-other[0])}}}


class SharedScene(Simulation):
    def __init__(self, seed=27, scenario='random', seconds=180, locomotion='guarded', finishing_aim='centre', spawn_zones=None):
        self.profile = PolicyProfile(locomotion, finishing_aim, active_names=NAMES)
        super().__init__(seed=seed, candidate='baseline', model=Model(dt=.04, half_seconds=seconds+10, ready_seconds=1),
                         active_names=NAMES, policy_profile=self.profile)
        self.scenario, self.seconds, self.outcome = scenario, seconds, None
        self.custom_setup = False
        self.engine = MatchEngine(MatchConfig(half_seconds=seconds+10, startup_seconds=0,
                                             ready_seconds=1, set_seconds=1, stuck_seconds=seconds+1, seed=seed))
        self.engine.red_direction = 1
        self.engine.phase, self.engine.half_started = 'PLAYING', 0
        self.engine.restart_team, self.engine.released = 'RED', True
        self.engine.kickoff_restriction = False
        self.engine.initial_kickoff = 'RED'
        self.spawn_zones = SpawnZones.parse(spawn_zones)
        self.initial_setup = starting_layout(seed, scenario, self.spawn_zones)
        self.ball = list(self.initial_setup['ball'])
        for name, point in self.initial_setup['robots'].items():
            self.players[name].update(copy.deepcopy(point), standing=True)
        self.frames = []
        self.clearance = None
        self.clearances_completed = 0
        self._record()

    def _stop_after_referee(self, events):
        ended = any(e['event']=='goal' or (e['event']=='restart' and e['kind']!='KICKOFF') for e in events)
        if ended:
            self.engine.phase = 'FINISHED'
            self.kicking.clear()
        return ended

    def _finish_kick(self, name, decision):
        before = self.stats[self.policies[name].team]['kick_contacts']
        super()._finish_kick(name, decision)
        if name == NAMES[1] and self.stats['BLUE']['kick_contacts'] > before:
            self.clearance = self.ball[0]

    def step(self):
        if self.outcome:
            return False
        old_events = len(self.events)
        super().step()
        new_events = self.events[old_events:]
        if any(e['event'] == 'goal' for e in new_events):
            self.outcome = 'GOAL' if self.engine.score[0] else 'CLEARED_GOAL'
        elif any(e['event'] == 'restart' and e['kind'] != 'KICKOFF' for e in new_events):
            self.outcome = 'OUT'
        if self.clearance is not None:
            if self.touch == NAMES[0]:
                self.clearance = None
            elif self.ball[0] < self.clearance-.18 and self.touch == NAMES[1]:
                self.clearances_completed += 1
                self._event('clearance_completed', robot=NAMES[1])
                self.clearance = None
        if self.time+1e-9 >= self.seconds and not self.outcome:
            self.outcome = 'TIMEOUT'
        if self.outcome:
            self.engine.phase = 'FINISHED'
            self.kicking.clear()
        if round(self.time/self.model.dt) % 5 == 0 or self.outcome:
            self._record()
        return self.outcome is None

    def snapshot(self):
        players = {}
        for name, role in zip(NAMES, ('attacker', 'defender')):
            p = self.players[name]
            decision = self.current_decisions.get(name)
            kick = self.kicking.get(name)
            players[role] = {'name': name, 'role': role, 'x': p['position'][0], 'y': p['position'][1], 'yaw': p['yaw'],
                             'state': decision.behaviour if decision else 'INITIAL',
                             'target': dict(zip(('x', 'y'), decision.target if decision else p['position'][:2])),
                             'action': self.last_actions.get(name, 'stand'),
                             'stage': self.navigation_stages.get(name, ''),
                             'kick': {'end': kick[0], 'duration': self.model.shot_seconds if kick[1].kick == 'shoot'
                                      else self.model.pass_seconds} if kick else None}
        if self.outcome:
            for player in players.values():
                player.update(state='FINISHED', action='stand', stage='ATTEMPT_FINISHED', kick=None,
                              target={'x':player['x'], 'y':player['y']})
        return {'t': self.time, **players, 'ball': dict(zip(('x', 'y', 'vx', 'vy'), self.ball[:2]+self.velocity[:2])),
                'outcome': self.outcome, 'lastTouch': 'attacker' if self.touch == NAMES[0] else 'defender' if self.touch else None,
                'stats': {'shotAttempts': self.stats['RED']['shot_attempts'],
                          'shotContacts': self.stats['RED']['kick_contacts'],
                          'clearAttempts': self.stats['BLUE']['pass_attempts'],
                          'clearContacts': self.stats['BLUE']['kick_contacts'],
                          'clearancesCompleted': self.clearances_completed}}

    def _record(self):
        self.frames.append(self.snapshot())

    def move(self, role, x, y):
        if self.outcome:
            raise ValueError('Reset before editing a finished scene')
        x, y = max(-4.25, min(4.25, x)), max(-2.7, min(2.7, y))
        if role == 'ball':
            point, names = [x, y], NAMES
            if any(math.dist(point, self.players[n]['position'][:2]) < .23 for n in names):
                raise ValueError('Place the ball outside a player disc')
            self.ball = [x, y, BALL_RADIUS]
        elif role in ('attacker', 'defender'):
            name = NAMES[0 if role == 'attacker' else 1]
            other = NAMES[1 if name == NAMES[0] else 0]
            if math.dist([x, y], self.players[other]['position'][:2]) < .31:
                raise ValueError('Player discs must not overlap')
            if math.dist([x, y], self.ball[:2]) < .23:
                raise ValueError('Place the player outside the ball')
            self.players[name]['position'] = [x, y, .334]
        else:
            raise ValueError('Unknown object')
        self.kicking.clear()
        self.velocity = [0, 0, 0]
        self.engine.previous = None
        self.touch = self.previous_contact = None
        self.previous_foot_contact = None
        self.clearance = None
        self.custom_setup = True
        self._event('manual_setup', object=role, x=x, y=y)
        for name in NAMES:
            self.policies[name], self.navigators[name] = self.profile.create(name)
        self._record()

    def summary(self):
        return {'seed': self.seed, 'scenario': self.scenario, 'seconds': self.time,
                'outcome': self.outcome, 'score': list(self.engine.score),
                'stats': self.snapshot()['stats'], 'profile': self.profile.dictionary(),
                'spawn_zones': self.spawn_zones.dictionary()}

    def report(self):
        return {**self.summary(), 'initial_setup': self.initial_setup, 'custom_setup': self.custom_setup,
                'source': source_info(), 'model': asdict(self.model), 'frames': self.frames, 'events': self.events,
                'limits': ['Independent Python policy/navigation revision for the planar exercise.',
                           'Different execution: 2D average-rate discs versus 3D joint motions and safety gates.',
                           'Exact positions and uncalibrated contact/rolling assumptions; no falls or cameras.']}


def run_batch(count, seed, scenario, seconds, locomotion, finishing_aim, spawn_zones=None):
    start = time.perf_counter()
    rows = []
    for offset in range(count):
        scene = SharedScene((seed+offset) % 2**32, scenario, seconds, locomotion, finishing_aim, spawn_zones)
        while scene.step():
            pass
        rows.append(scene.summary())
    elapsed = time.perf_counter()-start
    return {'runs': rows, 'wall_seconds': elapsed, 'simulated_seconds': sum(r['seconds'] for r in rows),
            'outcomes': dict(Counter(r['outcome'] for r in rows)), 'source': source_info(),
            'note': 'Fast policy screening, not physical or hardware success validation.'}


def envelope(scene):
    return {'state': scene.snapshot(), 'parameters': {**asdict(scene.model), 'ball_radius': BALL_RADIUS},
            'seed': scene.seed, 'scenario': scene.scenario, 'seconds': scene.seconds,
            'profile': scene.profile.dictionary(), 'source': source_info(),
            'spawn_zones': scene.spawn_zones.dictionary()}


def replay_html(scene):
    recording = copy.deepcopy(scene)
    while recording.step():
        pass
    data = {**envelope(recording), 'frames': recording.frames, 'report': recording.report()}
    embedded = json.dumps(data, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    return (HERE/'viewer.html').read_text(encoding='utf-8').replace('/*__REPLAY_DATA__*/', 'window.PYTHON_REPLAY='+embedded+';')


def serve(port, open_browser, initial):
    lock = threading.RLock()
    state = [initial]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[0]).find('/api/step') >= 0:
                return
            super().log_message(fmt, *args)

        def send(self, status, data, content_type='application/json; charset=utf-8', filename=None):
            body = json.dumps(data, allow_nan=False).encode() if content_type.startswith('application/json') else data.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if filename:
                self.send_header('Content-Disposition', 'attachment; filename="'+filename+'"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/':
                self.send(200, (HERE/'viewer.html').read_text(encoding='utf-8'), 'text/html; charset=utf-8')
            elif self.path == '/api/state':
                with lock:
                    self.send(200, envelope(state[0]))
            elif self.path == '/api/report':
                with lock:
                    self.send(200, state[0].report(), filename='shared-python-1v1.json')
            elif self.path == '/api/replay':
                with lock:
                    copy_scene = copy.deepcopy(state[0])
                self.send(200, replay_html(copy_scene), 'text/html; charset=utf-8', 'shared-python-1v1-replay.html')
            else:
                self.send(404, {'error': 'Not found'})

        def do_POST(self):
            # Same-origin, local interface only; no execution or arbitrary file endpoints.
            host = self.headers.get('Host', '')
            if host not in ('127.0.0.1:'+str(self.server.server_port), 'localhost:'+str(self.server.server_port)):
                return self.send(403, {'error': 'Invalid local host'})
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://'+host,):
                return self.send(403, {'error': 'Use the local viewer page'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or not self.headers.get('Content-Type', '').startswith('application/json'):
                    raise ValueError('Expected a small JSON request')
                data = json.loads(self.rfile.read(length))
                if self.path == '/api/new':
                    seed = int(data.get('seed', secrets.randbits(32)))
                    seconds = float(data.get('seconds', 180))
                    if not 0 <= seed < 2**32 or not math.isfinite(seconds) or not 5 <= seconds <= 1800:
                        raise ValueError('Invalid seed or duration')
                    with lock:
                        current_zones = state[0].spawn_zones
                    new_scene = SharedScene(seed, data.get('scenario', 'random'), seconds,
                                            data.get('locomotion', 'guarded'), data.get('finishing_aim', 'centre'),
                                            data.get('spawn_zones', current_zones))
                    with lock:
                        state[0] = new_scene
                        result = envelope(new_scene)
                elif self.path == '/api/step':
                    steps = int(data.get('steps', 1))
                    if not 1 <= steps <= 2000:
                        raise ValueError('Step count must be 1–2000')
                    with lock:
                        for _ in range(steps):
                            if not state[0].step():
                                break
                        result = envelope(state[0])
                elif self.path == '/api/move':
                    x, y = float(data['x']), float(data['y'])
                    if not math.isfinite(x) or not math.isfinite(y):
                        raise ValueError('Coordinates must be finite')
                    with lock:
                        state[0].move(data['object'], x, y)
                        result = envelope(state[0])
                elif self.path == '/api/batch':
                    count = int(data.get('count', 20))
                    if not 1 <= count <= 100:
                        raise ValueError('Batch count must be 1–100')
                    with lock:
                        scene = state[0]
                        args = (count, scene.seed, scene.scenario, scene.seconds,
                                scene.profile.locomotion, scene.profile.finishing_aim, scene.spawn_zones)
                    result = run_batch(*args)
                else:
                    return self.send(404, {'error': 'Not found'})
                self.send(200, result)
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                self.send(400, {'error': str(error)})

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        url = 'http://127.0.0.1:'+str(server.server_port)+'/'
        print('SHARED_POLICY_VIEWER '+url, flush=True)
        print('Python decision source: '+str(REPOSITORY), flush=True)
        print('Stop with Ctrl+C. No Webots is required for 2D.', flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nViewer stopped.', flush=True)


def main():
    source_info()  # Record the source version loaded by this process; restart after edits.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundled', action='store_true', help='Compatibility flag; this standalone project always uses its local backend')
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--scenario', choices=('random', 'duel', 'lane', 'shot', 'breakaway', 'block'), default='random')
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--locomotion', choices=('legacy', 'guarded'), default='guarded')
    parser.add_argument('--finishing-aim', choices=('centre', 'nearest'), default='centre')
    parser.add_argument('--spawn-zones', type=Path, help='Optional JSON file with attacker/defender rectangles')
    parser.add_argument('--batch', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else secrets.randbits(32)
    try:
        zone_file = args.spawn_zones or HERE/'spawn_zones.json'
        zones = SpawnZones.parse(json.loads(zone_file.read_text())
                                 if args.spawn_zones or zone_file.exists() else None)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if not 0 <= seed < 2**32 or not math.isfinite(args.seconds) or not 5 <= args.seconds <= 1800:
        parser.error('Invalid seed or duration')
    if args.batch:
        if not 1 <= args.batch <= 1000 or not args.output:
            parser.error('--batch requires 1–1000 runs and a fresh --output directory')
        if args.output.exists():
            parser.error('Use a fresh output directory to preserve previous tests')
        args.output.mkdir(parents=True)
        result = run_batch(args.batch, seed, args.scenario, args.seconds, args.locomotion, args.finishing_aim, zones)
        (args.output/'metrics.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        first = SharedScene(seed, args.scenario, args.seconds, args.locomotion, args.finishing_aim, zones)
        while first.step():
            pass
        (args.output/'replay.html').write_text(replay_html(first), encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('runs', 'source')}, indent=2))
        print('Replay: '+str((args.output/'replay.html').resolve()))
    else:
        serve(args.port, args.open, SharedScene(seed, args.scenario, args.seconds, args.locomotion, args.finishing_aim, zones))


if __name__ == '__main__':
    main()
