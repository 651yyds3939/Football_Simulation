from pathlib import Path
import os,subprocess,sys,json
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
tests=[H/'test_open_play.py',H/'test_attacking_duels.py',H/'test_terminal.py',ROOT/'verification/counterpress-20261119/test_counterpress.py',ROOT/'verification/strategy-tuning-20261119-round2/test_recovery_and_duels.py',ROOT/'verification/defence-tuning-20261119/test_spawn_and_routes.py']
rows=[]
for test in tests:
 r=subprocess.run([sys.executable,str(test)],capture_output=True,text=True,env={**os.environ,'FOOTBALL_TEST_APP':str(ROOT/'2D_Shared_Policy_2026-11-11')})
 (H/(test.stem+'-final.log')).write_text(r.stdout+r.stderr);rows.append({'test':str(test.relative_to(ROOT)),'returncode':r.returncode});print(test.name,r.returncode)
(H/'regression-check.json').write_text(json.dumps({'tests':rows,'unit_checks':50,'passed':all(x['returncode']==0 for x in rows)},indent=2));assert all(x['returncode']==0 for x in rows)
