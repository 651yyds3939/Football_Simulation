from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
settings={
 'reference':{'support':'unchanged'},
 'safe-radius':{'support':'safe','support_radius':1.0},
 'safe-wide':{'support':'safe','support_radius':1.3},
 'adaptive':{'support':'adaptive','support_radius':1.0},
 'adaptive-wide':{'support':'adaptive','support_ahead':.8,'support_width':1.3,'support_radius':1.3},
 'adaptive-back':{'support':'adaptive','support_ahead':-.3,'support_width':1.0,'support_radius':1.1},
 'close-pass':{'support':'close','support_radius':.65,'passing':'opportunistic','handoff_distance':1.1,'pass_distance':1.0},
 'close-reachable':{'support':'close','support_radius':.75,'passing':'reachable','handoff_distance':1.1},
}
rows=[]
for name,tuning in settings.items():
 out=H/(name+'.json')
 with (H/(name+'.log')).open('w') as f:
  subprocess.run([sys.executable,str(H/'evaluate.py'),'--app',str(H/'candidate-app'),'--seed','210000','--count','8','--mode','reference' if name=='reference' else 'candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads(out.read_text());s=d['summary'];rows.append({'name':name,**s});print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
(H/'sweep-summary.json').write_text(json.dumps(rows,indent=2))
