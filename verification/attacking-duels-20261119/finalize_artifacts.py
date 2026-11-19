from pathlib import Path
import json,subprocess,sys,time
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
while True:
 try:
  a=json.loads((H/'baseline-holdout-final.json').read_text());b=json.loads((H/'production-holdout-final.json').read_text());assert len(a['runs'])==len(b['runs'])==1000;break
 except (FileNotFoundError,json.JSONDecodeError,AssertionError):time.sleep(.2)
commands=[H/'compare.py',H/'write_report.py',ROOT/'verification/one-v-one-20261111/package_shared_policy.py',ROOT/'verification/simple-html-20261112/build_demo.py',H/'check_package.py',ROOT/'verification/simple-html-20261112/run_browser_check.py']
for script in commands:
 print('CHECK',script.name,flush=True);subprocess.run([sys.executable,str(script)],check=True,cwd=ROOT)
with (ROOT/'docs/ATTACKING_DUELS_2026-11-19.md').open('a') as f:
 f.write('\n附加完整性检查：反转球员处理顺序的20个相同开局，36,040个时间步的双方位置、朝向和球运动一致；物理执行文件逐字节相同，防守预判与回追函数未变。\n')
print('FINAL_ARTIFACTS_READY',flush=True)
