from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
settings={
 'follow-only':{'support':'unchanged','cover_mode':'follow','navigation':'unchanged'},
 'follow-route':{'support':'unchanged','cover_mode':'follow'},
 'follow-safe':{'support':'safe','support_radius':1.1},
 'follow-wide':{'support':'adaptive','support_ahead':.8,'support_width':1.3,'support_radius':1.3},
 'follow-close':{'support':'close','support_radius':.70,'passing':'opportunistic','handoff_distance':1.1,'pass_distance':1.0},
 'follow-gap2':{'support':'safe','support_radius':1.1,'cover_gap':2.0},
 'follow-limited':{'support':'safe','support_radius':1.1,'cover_ceiling':.5},
 'follow-short':{'support':'unchanged','cover_mode':'follow','passing':'opportunistic','handoff_distance':1.1,'pass_distance':1.0},
}
rows=[]
for name,tuning in settings.items():
 out=H/('r3-'+name+'.json')
 with (H/('r3-'+name+'.log')).open('w') as f:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/'round3-app'),'--seed','210000','--count','8','--mode','reference' if name=='reference' else 'candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads(out.read_text());s=d['summary'];rows.append({'name':name,**s});print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
(H/'round3-summary.json').write_text(json.dumps(rows,indent=2))
