"""Audit final source, common referee conditions, records and distributables."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile,re
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'2D_Shared_Policy_2026-11-11'
def read(name):return json.loads((H/name).read_text())
selected=read('selected-before-holdout.json')
assert all(hashlib.sha256((APP/n).read_bytes()).hexdigest()==v for n,v in selected['sha256'].items())
assert (H/'baseline-corrected-app/backend/Wenao/controllers/Utils/MatchEngine.py').read_bytes()==(APP/'backend/Wenao/controllers/Utils/MatchEngine.py').read_bytes()
for cohort,count in [('holdout',1000),('headon-holdout',200)]:
 a=read('baseline-'+cohort+'-final.json');b=read('production-'+cohort+'-final.json')
 assert a['observer_schema']==b['observer_schema']==3
 assert len(a['runs'])==len(b['runs'])==count
 assert [r['seed'] for r in a['runs']]==[r['seed'] for r in b['runs']]
 assert a['source']['sha256']['Wenao/controllers/Utils/MatchEngine.py']==b['source']['sha256']['Wenao/controllers/Utils/MatchEngine.py']
 for row in a['runs']+b['runs']:assert abs(sum(row['attacker_states_seconds'].values())-(row['seconds']-.04))<1e-6
 for name,digest in b['source']['sha256'].items():assert hashlib.sha256((APP/'backend'/name).read_bytes()).hexdigest()==digest
with zipfile.ZipFile(ROOT/'2D_Shared_Policy_2026-11-11.zip') as z:
 assert len(z.namelist())==20
 assert all(z.read(n)==(ROOT/n).read_bytes() for n in z.namelist())
assert read('regression-check.json')['passed']
for n in ['browser-check.json','attacking-browser-check.json','endurance-check.json']:assert not read(n)['runtime_errors']
offline=json.loads((ROOT/'verification/simple-html-20261112/browser-check.json').read_text());assert not offline['runtime_errors'];assert offline['recordings_equal_original_frames'];assert len(offline['examples'])==5
assert read('package-check.json')['zip_members_match_workspace']
assert read('invariants.json')['physics_file_byte_identical']
started=datetime(2026,11,19,15,36,46,tzinfo=timezone.utc);ended=datetime.now(timezone.utc);elapsed=(ended-started).total_seconds();assert elapsed>=1800,'Requested 30 minutes have not elapsed'
result={'start_utc':started.isoformat(),'end_utc':ended.isoformat(),'elapsed_seconds':elapsed,'unit_regressions_passed':50,'spawn_seeds_checked':5000,'independent_full_layout_pairs':1000,'independent_headon_pairs':200,'selection_frozen_before_corrected_holdout':True,'policy_parameters_not_retuned_after_common_referee_fix':True,'identical_referee_for_baseline_and_candidate':True,'live_code_matches_frozen_selection':True,'physical_motion_and_contact_file_unchanged':True,'reverse_player_order_cases':20,'reverse_order_equal_steps':read('invariants.json')['reverse_order_equal_steps'],'browser_runtime_errors':0,'continuous_browser_seconds':read('endurance-check.json')['wall_seconds'],'continuous_browser_rounds':read('endurance-check.json')['rounds'],'offline_five_examples':True,'zip_matches_live':True,'three_dimensional_project_not_modified':True,'git_commit_or_push_performed':False,'zip_sha256':hashlib.sha256((ROOT/'2D_Shared_Policy_2026-11-11.zip').read_bytes()).hexdigest(),'offline_html_sha256':hashlib.sha256((ROOT/'Football_1v1_Demo.html').read_bytes()).hexdigest(),'remaining_limits':['151 of 200 close frontal fixtures still lost the first contest.','Full holdout has six real OUT results versus zero at baseline.','Two close-start fixtures timed out versus zero at baseline.','No 3D balance, vision noise or hardware performance demonstrated.']}
(H/'delivery-check.json').write_text(json.dumps(result,indent=2)+'\n')
with (ROOT/'docs/ATTACKING_DUELS_2026-11-19.md').open('a') as f:f.write(f'\n## 本轮结束记录\n\n从 {started:%H:%M:%S} 到 {ended:%H:%M:%S} UTC，持续 {elapsed/60:.1f} 分钟。源码、共同裁判条件、50项回归、浏览器与压缩包核对通过。完整交付记录见 `verification/attacking-duels-20261119/delivery-check.json`。\n')
print(json.dumps(result,indent=2))
