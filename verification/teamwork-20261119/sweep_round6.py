from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
settings={
 'search-near':{'support':'unchanged','search_ring':1.1,'support_hold':4.},
 'search-fast':{'support':'unchanged','search_eta_weight':.15,'support_hold':4.},
 'search-lane':{'support':'unchanged','search_lane_weight':2.,'support_hold':4.},
 'search-short':{'support':'unchanged','search_ring':.85,'search_radius_min':.65,'passing':'opportunistic','all_field_pass':True,'handoff_distance':1.2,'pass_distance':1.1,'pass_progress':-.05,'yield_enabled':False},
 'search-both':{'support':'unchanged','search_attack_only':False,'support_hold':5.},
 'search-no-route':{'support':'unchanged','navigation':'unchanged','support_hold':4.},
 'search-static':{'support':'unchanged','search_predict':0.,'support_hold':8.},
 'search-wide':{'support':'unchanged','search_ring':1.5,'support_hold':6.},
}
rows=[]
for name,tuning in settings.items():
 out=H/('r6-'+name+'.json')
 with (H/('r6-'+name+'.log')).open('w') as f:
  subprocess.run([sys.executable,str(H/'evaluate_round2.py'),'--app',str(H/'round6-app'),'--seed','210000','--count','8','--mode','reference' if name=='reference' else 'candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=f,stderr=subprocess.STDOUT,check=True)
 d=json.loads(out.read_text());s=d['summary'];rows.append({'name':name,**s});print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
(H/'round6-summary.json').write_text(json.dumps(rows,indent=2))
