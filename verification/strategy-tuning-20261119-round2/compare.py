"""Compare matched fixture results, keeping timeout/out separate from goals."""
from pathlib import Path
from collections import Counter
import argparse,json,math
p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--groups',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
b=json.loads(a.baseline.read_text());c=json.loads(a.candidate.read_text());groups=json.loads(a.groups.read_text())
left={r['seed']:r for r in b['runs']};right={r['seed']:r for r in c['runs']};assert left.keys()==right.keys()
def summary(rows):
 n=len(rows)
 return {'runs':n,'outcomes':dict(Counter(r['outcome'] for r in rows)),
         'stalls_over_20s':sum(r['longest_stall_seconds']>20 for r in rows),
         'mean_turn_seconds':sum(sum(v for k,v in r['defender_actions_seconds'].items() if k.startswith(('left','right'))) for r in rows)/n,
         'mean_behind_ball_seconds':sum(r['behind_ball_seconds'] for r in rows)/n,
         'mean_duration_seconds':sum(r['seconds'] for r in rows)/n,
         'controlled_retreat_runs':sum(r['first_controlled_retreat'] is not None for r in rows)}
result={'baseline':b['summary'],'candidate':c['summary'],'groups':{},'outcome_transitions':dict(Counter(x['outcome']+' -> '+right[s]['outcome'] for s,x in left.items()))}
for name in sorted(set(groups.values())):
 seeds=[s for s in left if groups[str(s)]==name];result['groups'][name]={'baseline':summary([left[s] for s in seeds]),'candidate':summary([right[s] for s in seeds])}
# Paired descriptive interval for a change in blue-left-goal proportion.
delta=[int(right[s]['outcome']=='CLEARED_GOAL')-int(left[s]['outcome']=='CLEARED_GOAL') for s in left]
mean=sum(delta)/len(delta);var=sum((x-mean)**2 for x in delta)/(len(delta)-1);width=1.96*math.sqrt(var/len(delta))
result['blue_left_goal_change']={'percentage_points':mean*100,'paired_normal_95_interval_pp':[(mean-width)*100,(mean+width)*100], 'note':'Descriptive seed-sample interval; not hardware performance or a guarantee for other spawn distributions.'}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
