from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
configs={
 'yield-small':('round4-app',{'support':'unchanged','yield_enter':.65,'yield_exit':.95}),
 'yield-generic':('round4-app',{'support':'unchanged','navigation':'unchanged'}),
 'short-all':('round4-app',{'support':'unchanged','yield_enabled':False,'passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05}),
 'close-all':('round4-app',{'support':'close','support_radius':.75,'yield_enabled':False,'passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05}),
}
for name,(app,tuning) in configs.items():
 out=H/('validation-'+name+'.json')
 with (H/('validation-'+name+'.log')).open('w') as log:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/app),'--seed','212000','--count','16','--mode','candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
 s=json.loads(out.read_text())['summary'];print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
