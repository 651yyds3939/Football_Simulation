from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
configs={
 'search-fast':{'support':'unchanged','search_eta_weight':.15,'support_hold':4.},
 'search-near':{'support':'unchanged','search_ring':1.1,'support_hold':4.},
 'search-no-route':{'support':'unchanged','navigation':'unchanged','support_hold':4.},
}
for name,tuning in configs.items():
 out=H/('validation-'+name+'.json')
 with (H/('validation-'+name+'.log')).open('w') as log:
  subprocess.run([sys.executable,str(H/'evaluate_final.py'),'--app',str(H/'round6-app'),'--seed','212000','--count','16','--mode','candidate','--tuning',json.dumps(tuning),'--output',str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
 s=json.loads(out.read_text())['summary'];print(name,s['wins'],s['losses'],s['draws'],s['goals_for'],s['goals_against'],s['mean_crowded_seconds'],s['team_totals']['candidate'].get('completed_passes',0),flush=True)
