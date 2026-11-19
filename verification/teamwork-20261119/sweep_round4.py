from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
settings={
 'yield-small':{'support':'unchanged','yield_enter':.65,'yield_exit':.95},
 'yield-medium':{'support':'unchanged','yield_enter':.8,'yield_exit':1.1},
 'yield-wide':{'support':'unchanged','yield_enter':.85,'yield_exit':1.3},
 'yield-generic':{'support':'unchanged','navigation':'unchanged'},
 'yield-pass':{'support':'unchanged','passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05},
 'short-all':{'support':'unchanged','yield_enabled':False,'passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05},
 'close-all':{'support':'close','support_radius':.75,'yield_enabled':False,'passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05},
 'yield-safe':{'support':'safe','support_radius':1.1,'yield_enter':.8,'yield_exit':1.1},
}
rows=[]
for name,tuning in settings.items():
 out=H/('r4-'+name+'.json')
 with (H/('r4-'+name+'.log')).open('w') as f:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/'round4-app'),'--seed','210000','--count','8','--mode','reference' if name=='reference' else 'candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads(out.read_text());s=d['summary'];rows.append({'name':name,**s});print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
(H/'round4-summary.json').write_text(json.dumps(rows,indent=2))
