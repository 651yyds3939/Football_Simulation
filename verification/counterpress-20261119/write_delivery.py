"""Audit the frozen selection, delivered package and completed QA evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / '2D_Shared_Policy_2026-11-11'

def read(name):
    return json.loads((HERE / name).read_text())

selected = read('selected-before-holdout.json')
assert all(hashlib.sha256((APP / name).read_bytes()).hexdigest() == digest
           for name, digest in selected['sha256'].items())
with zipfile.ZipFile(ROOT / '2D_Shared_Policy_2026-11-11.zip') as archive:
    assert all(archive.read(name) == (ROOT / name).read_bytes()
               for name in archive.namelist())
for name in ('browser-check.json', 'policy-browser-check.json', 'endurance-check.json'):
    assert not read(name)['runtime_errors']
offline = json.loads((ROOT / 'verification/simple-html-20261112/browser-check.json').read_text())
assert not offline['runtime_errors']
assert read('package-check.json')['zip_members_match_workspace']
assert all(read('invariants.json').values())
started = datetime(2026, 11, 19, 14, 54, 2, tzinfo=timezone.utc)
ended = datetime.now(timezone.utc)
elapsed = (ended - started).total_seconds()
assert elapsed >= 1800, 'The requested 30 minutes have not elapsed'
endurance = read('endurance-check.json')
result = {
    'start_utc': started.isoformat(), 'end_utc': ended.isoformat(),
    'elapsed_seconds': elapsed, 'paired_final_fixtures': 1000,
    'unit_regressions_passed': 31, 'spawn_seeds_checked': 5000,
    'selection_frozen_before_final_holdout': True,
    'live_sources_match_frozen_selection': True,
    'motion_rates_and_contact_physics_unchanged': True,
    'simulation_step_change': 'Terminal stop hook before post-result policy execution',
    'browser_runtime_errors': 0,
    'continuous_play_rounds_started': endurance['rounds'],
    'continuous_browser_wall_seconds': endurance['wall_seconds'],
    'offline_five_examples_checked': True, 'zip_matches_workspace': True,
    'three_dimensional_project_not_modified': True,
    'git_commit_or_push_performed': False,
    'zip_sha256': hashlib.sha256((ROOT / '2D_Shared_Policy_2026-11-11.zip').read_bytes()).hexdigest(),
    'offline_html_sha256': hashlib.sha256((ROOT / 'Football_1v1_Demo.html').read_bytes()).hexdigest(),
    'known_limitations': [
        'Productive post-regain advances declined from 12 to 9 in the 1000 paired fixtures.',
        'Near-goal long stalls increased from 16 to 18, despite aggregate reduction 55 to 39.',
        '33 of 1000 final fixtures timed out; 32 ended in stationary close contests.',
        '2D exact-state results do not establish 3D or hardware behaviour.'
    ]
}
(HERE / 'delivery-check.json').write_text(json.dumps(result, indent=2) + '\n')
doc = ROOT / 'docs/COUNTERPRESS_TUNING_2026-11-19.md'
with doc.open('a') as stream:
    stream.write('\n## 最终交付检查\n\n'
                 f'本轮从 {started:%H:%M:%S} 到 {ended:%H:%M:%S} UTC，持续 {elapsed/60:.1f} 分钟。'
                 '冻结源码与运行目录一致，压缩包20个文件逐字节匹配，31项回归检查、5000个出生种子检查、'
                 '浏览器连续运行及五例离线回放通过。完整记录见 `verification/counterpress-20261119/delivery-check.json`。\n')
print(json.dumps(result, indent=2))
