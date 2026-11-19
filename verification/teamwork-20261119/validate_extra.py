from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
configs={
 'reference':('round4-app',{},'reference'),
 'yield-safe':('round4-app',{'support':'safe','support_radius':1.1,'yield_enter':.8,'yield_exit':1.1},'candidate'),
 'relief-no-yield':('round5-app',{'support':'unchanged','yield_enabled':False},'candidate'),
 'relief-small':('round5-app',{'support':'unchanged','yield_enter':.65,'yield_exit':.95},'candidate'),
}
for name,(app,tuning,mode) in configs.items():
 out=H/('validation-'+name+'.json')
 with (H/('validation-'+name+'.log')).open('w') as log:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/app),'--seed','212000','--count','16','--mode',mode,'--tuning',json.dumps(tuning),'--output',str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
 s=json.loads(out.read_text())['summary'];print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
