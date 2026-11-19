"""Evaluate full, two-half 4v4 matches without rendering or frame sampling."""
from pathlib import Path
from collections import Counter
import argparse,importlib.util,sys,json,time,math,hashlib
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,default=H/'baseline-app');p.add_argument('--seed',type=int,default=110000);p.add_argument('--count',type=int,default=10);p.add_argument('--half-seconds',type=float,default=300);p.add_argument('--dt',type=float,default=.2);p.add_argument('--mode',default='baseline');p.add_argument('--tuning',type=json.loads,default={});p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
sys.path.insert(0,str(a.app/'backend/tools'));from soccer2d import Simulation,Model
if a.mode!='baseline':
 from Utils.TeamTactics import TacticalPolicy,SETTINGS
 SETTINGS.update(a.tuning)
rows=[];started=time.perf_counter()
for seed in range(a.seed,a.seed+a.count):
 for candidate in ('RED','BLUE'):
  s=Simulation(seed,candidate,'baseline',Model(dt=a.dt,half_seconds=a.half_seconds,ready_seconds=10))
  if a.mode!='baseline':
   for n in s.names:
    if s.policies[n].team==candidate or a.mode=='self':s.policies[n]=TacticalPolicy(n,goal_depth=.3)
  playing=0.;crowded=0.;last_contact=None;ball_anchor=None;ball_static=0.;max_static=0.;chaser_changes=Counter();prior_chaser={};keeper_chase=Counter();forward_progress=Counter();states={t:Counter() for t in ('RED','BLUE')};nearest=Counter();alone_ball=0.;shotblock=0.;seen=0;blue_turn=0
  def observe(sim):
   global playing,crowded,last_contact,ball_anchor,ball_static,max_static,alone_ball,seen
   if sim.engine.phase!='PLAYING':return
   dt=sim.model.dt;playing+=dt;b=sim.ball
   close=[n for n,p in sim.players.items() if math.dist(p['position'][:2],b[:2])<.65]
   crowded+=dt*(len(close)>=3)
   if ball_anchor is None or math.dist(b[:2],ball_anchor)>.10:ball_anchor=tuple(b[:2]);ball_static=0.
   else:ball_static+=dt;max_static=max(max_static,ball_static)
   for team in ('RED','BLUE'):
    own=[n for n in sim.names if sim.policies[n].team==team]
    for n in own:
     d=sim.current_decisions.get(n);states[team][d.behaviour if d else 'WAIT']+=dt
     if 'Goalkeeper' in n and math.dist(sim.players[n]['position'][:2],(-sim.engine.direction(team)*4.12,0))>1.5:keeper_chase[team]+=dt
    chasers=[n for n in own if sim.current_decisions.get(n) and sim.current_decisions[n].behaviour in ('DRIBBLE','EVADE_DRIBBLE','SHOOT','PASS','CLEAR','INTERCEPT','COUNTERPRESS','CHALLENGE','DEFENSIVE_INTERCEPT')]
    key=tuple(chasers)
    if team in prior_chaser and prior_chaser[team]!=key:chaser_changes[team]+=1
    prior_chaser[team]=key
   if not close:alone_ball+=dt
  result=s.run(observer=observe)
  team=candidate;op='BLUE' if team=='RED' else 'RED';rows.append({**result,'candidate_team':candidate,'playing_seconds':playing,'crowded_seconds':crowded,'longest_stationary_ball_seconds':max_static,'ball_unattended_seconds':alone_ball,'keeper_out_seconds':dict(keeper_chase),'role_changes':dict(chaser_changes),'states':{t:dict(v) for t,v in states.items()},'event_counts':dict(Counter(e['event'] for e in s.events))})
  print(seed,candidate,result['score_red_blue'],round(crowded,1),flush=True)
n=len(rows);summary={'games':n,'independent_seeds':a.count,'wins':sum(r['candidate_goal_difference']>0 for r in rows),'losses':sum(r['candidate_goal_difference']<0 for r in rows),'draws':sum(r['candidate_goal_difference']==0 for r in rows),'goals_for':sum(r['score_red_blue'][0 if r['candidate_team']=='RED' else 1] for r in rows),'goals_against':sum(r['score_red_blue'][1 if r['candidate_team']=='RED' else 0] for r in rows),'mean_crowded_seconds':sum(r['crowded_seconds'] for r in rows)/n,'mean_playing_seconds':sum(r['playing_seconds'] for r in rows)/n,'mean_longest_stationary_ball_seconds':sum(r['longest_stationary_ball_seconds'] for r in rows)/n,'mean_unattended_seconds':sum(r['ball_unattended_seconds'] for r in rows)/n,'wall_seconds':time.perf_counter()-started,'team_totals':{}}
for label in ['candidate','opponent']:
 totals=Counter()
 for r in rows:
  team=r['candidate_team'] if label=='candidate' else ('BLUE' if r['candidate_team']=='RED' else 'RED');totals.update(r['team_stats'][team]);totals['keeper_out_seconds']+=r['keeper_out_seconds'].get(team,0);totals['role_changes']+=r['role_changes'].get(team,0)
 summary['team_totals'][label]=dict(totals)
source={str(f.relative_to(a.app/'backend')):hashlib.sha256(f.read_bytes()).hexdigest() for f in (a.app/'backend').rglob('*.py') if '__pycache__' not in str(f)}
a.output.write_text(json.dumps({'summary':summary,'runs':rows,'source':source,'mode':a.mode,'tuning':a.tuning,'observer_schema':1,'limits':'Swapped candidate colours within a seed are paired correlated games. Contacts, passes and possession are simplified 2D proxies.'},indent=2));print('SUMMARY',json.dumps(summary),flush=True)
