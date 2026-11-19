"""Embed current model values, document their provenance, and package the demo."""
from pathlib import Path
import hashlib
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / '2D_1v1_Demo_2026-11-11'
REPO = ROOT / '2D_Shared_Policy_2026-11-11/backend'
sys.path.insert(0, str(REPO / 'tools'))
from soccer2d import Model
from Utils import CourseSpecs as c

m = Model()
parameters = {name: getattr(m, name) for name in (
    'walk_speed', 'back_speed', 'left_speed', 'right_speed', 'left_turn', 'right_turn',
    'robot_radius', 'rolling_deceleration', 'shot_range', 'pass_range',
    'shot_seconds', 'pass_seconds', 'kick_noise_radians')}
parameters.update(pitch_length=c.PITCH_LENGTH, pitch_width=c.PITCH_WIDTH,
                  goal_width=c.GOAL_WIDTH, goal_height=c.GOAL_HEIGHT,
                  goal_depth=c.GOAL_DEPTH, ball_radius=c.BALL_RADIUS,
                  dt=.04, round_seconds=180)
sources = ['tools/soccer2d.py', 'Wenao/controllers/Utils/CourseSpecs.py',
           'verification/development/navigation/motion-result.json',
           'verification/development/navigation/skills-result.json',
           'Wenao/motions/Shoot.motion', 'Wenao/motions/LongPass.motion']
provenance = {
    'parameters': parameters,
    'purpose': 'Standalone continuous 1 attacker vs 1 defender vs 1 ball, with randomized reproducible starting states',
    'policy': 'Independent small 1v1 state policies; not a port of TeamPolicy or the existing 4v4 controller',
    'course_dimensions': 'Project specification p. 3: 9×6 m pitch; 2.6×1.2×0.6 m goal; approximately 0.14 m ball diameter',
    'measured_rates': 'Existing isolated Webots motion tests, not real NAO6 calibration',
    'kick_distance_warning': 'Single-fixture displacement parameters; pass fixture included receiver contact',
    'assumptions': ['Disc radius, constant rolling deceleration, kick direction noise and simplified contact response',
                    'Exact object positions, planar motion, a 180 s attempt and a 0.04 s numerical step',
                    'Dribbling through disc contact; kick contact gate and independent 1v1 policies',
                    'A clearance event requires defender kick contact and at least 0.18 m leftward ball displacement; play continues',
                    'Random setup samples ball position, attacking gap and heading, defensive offset and attacking lane; no outcome is drawn randomly'],
    'starting_scene': 'Random by default, fresh seed on opening; explicit fixed fixtures and repeat-seed control remain available',
    'continuous_play': 'Clearances continue; goals, exits and 180 s timeout end a round. Optional next random round after 3 real seconds.',
    'default_playback_multiplier': 2,
    'playback': '1×/2×/4×/8×/16× change wall-clock playback only; no change to simulated motion rates',
    'source_sha256': {name: hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in sources},
}
html = (DEMO/'index.html').read_text()
html, count = re.subn(r'(<script id="config" type="application/json">).*?(</script>)',
                     lambda match: match[1]+json.dumps(parameters, separators=(',', ':'))+match[2],
                     html, count=1, flags=re.S)
assert count == 1
(DEMO/'index.html').write_text(html)
(DEMO/'model_parameters.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False)+'\n')

members = ['index.html', 'README.md', 'MODEL_NOTES.md', 'model_parameters.json']
if all((DEMO/member).exists() for member in members):
    archive = ROOT / '2D_1v1_Demo_2026-11-11.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for member in members:
            bundle.write(DEMO/member, arcname=DEMO.name+'/'+member)
    print(archive)
print('Embedded source-derived parameter values; no existing controller changed.')
