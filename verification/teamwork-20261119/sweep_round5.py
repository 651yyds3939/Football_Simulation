from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
settings={
 'relief-small':{'support':'unchanged','yield_enter':.65,'yield_exit':.95},
 'relief-early':{'support':'unchanged','relief_after':5.,'relief_distance':.9,'relief_lease':10.},
 'relief-near':{'support':'unchanged','relief_distance':.60,'assist_after':3.},
 'relief-far':{'support':'unchanged','relief_distance':1.2,'relief_lease':15.},
 'assist-only':{'support':'unchanged','relief_after':1000.,'assist_after':3.},
 'relief-no-assist':{'support':'unchanged','assist_after':1000.},
 'relief-no-yield':{'support':'unchanged','yield_enabled':False},
 'relief-close':{'support':'close','support_radius':.80,'relief_distance':.9},
}
rows=[]
for name,tuning in settings.items():
 out=H/('r5-'+name+'.json')
 with (H/('r5-'+name+'.log')).open('w') as f:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/'round5-app'),'--seed','210000','--count','8','--mode','reference' if name=='reference' else 'candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads(out.read_text());s=d['summary'];rows.append({'name':name,**s});print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
(H/'round5-summary.json').write_text(json.dumps(rows,indent=2))
