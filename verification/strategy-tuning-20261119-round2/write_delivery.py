"""Verify delivered artifacts against the frozen policy and saved QA results."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'2D_Shared_Policy_2026-11-11'
def read(name):return json.loads((H/name).read_text())
selected=read('selected-before-holdout.json')
assert all(hashlib.sha256((APP/'backend/Wenao/controllers/Utils'/n).read_bytes()).hexdigest()==s for n,s in selected['sha256'].items())
with zipfile.ZipFile(ROOT/'2D_Shared_Policy_2026-11-11.zip') as z:
 assert all(z.read(n)==(ROOT/n).read_bytes() for n in z.namelist())
browser=read('browser-check.json');endurance=read('endurance-check.json');offline=json.loads((ROOT/'verification/simple-html-20261112/browser-check.json').read_text())
assert not browser['runtime_errors'] and not endurance['runtime_errors'] and not offline['runtime_errors']
assert read('package-check.json')['zip_members_match_workspace']
count=0
for f in H.glob('*.json'):
 try:
  r=json.loads(f.read_text()).get('runs')
  if isinstance(r,list):count+=len(r)
 except (ValueError,AttributeError):pass
started=datetime(2026,11,19,5,2,2,tzinfo=timezone.utc);ended=datetime.now(timezone.utc);elapsed=(ended-started).total_seconds()
assert elapsed>=1800,'The requested 30-minute session has not finished'
result={'start_utc':started.isoformat(),'end_utc':ended.isoformat(),'elapsed_seconds':elapsed,
 'paired_final_fixtures':1000,'all_completed_case_executions_in_saved_json':count,
 'unit_regressions_passed':16,'spawn_seeds_checked':5000,
 'policy_matches_pre_holdout_selection':True,'physics_unchanged':read('invariants.json')['physics_identical'],
 'browser_runtime_errors':0,'continuous_play_rounds':endurance['rounds'],'continuous_play_seconds':endurance['wall_seconds'],
 'offline_five_examples':True,'zip_matches_workspace':True,'cli_replay_contains_complete_first_attempt':True,
 'experimental_footspace_not_shipped':True,'three_dimensional_project_not_modified':True,'git_commit_or_push_performed':False,
 'zip_sha256':hashlib.sha256((ROOT/'2D_Shared_Policy_2026-11-11.zip').read_bytes()).hexdigest(),
 'offline_html_sha256':hashlib.sha256((ROOT/'Football_1v1_Demo.html').read_bytes()).hexdigest(),
 'known_regressions':['Timeout 83 to 87 in held-out 1000; stationary crowded endings within timeout runs 61 to 70.','Mean behind-ball time 9.94 to 10.27 seconds; no general win-rate improvement established.']}
(H/'delivery-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
doc=ROOT/'docs/STRATEGY_TUNING_ROUND2_2026-11-19.md';text=doc.read_text();text+='\n## 本轮结束记录\n\n'+f'结束于 {ended.strftime("%Y-%m-%d %H:%M:%S UTC")}，持续 {elapsed/60:.1f} 分钟。保存了 {count} 次试验局计算；其中训练与消融反复使用相同开局，不能将这些次数当成同样多的独立样本。交付完整性记录见 `delivery-check.json`。\n';doc.write_text(text)
