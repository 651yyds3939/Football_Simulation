"""Observe first attacking contests separately from whole-round outcomes.

No decisions, rates or contacts are changed by the observer. A lost contest is
exclusive forward-foot occupation by Blue, not an arbitrary body last-touch.
"""
from pathlib import Path
from collections import Counter
import argparse,importlib.util,json,math,time
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,default=H/'baseline-app');p.add_argument('--seed',type=int,default=80000);p.add_argument('--count',type=int,default=120);p.add_argument('--layouts',type=Path,required=True);p.add_argument('--tuning',type=json.loads,default={});p.add_argument('--output',type=Path,required=True);p.add_argument('--trace',type=int,nargs='*',default=[]);a=p.parse_args()
assert not a.output.exists(),'Use a fresh output path'
spec=importlib.util.spec_from_file_location('duel_app',a.app/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from Utils.DefensivePlan import SETTINGS
SETTINGS.update(a.tuning)
if not a.trace:m.SharedScene._record=lambda self:None
layouts=json.loads(a.layouts.read_text());rows=[];start=time.perf_counter()
def length(a,b):return math.dist(a[:2],b[:2])
def foot(s,n):
 q=s.players[n];dx,dy=s.ball[0]-q['position'][0],s.ball[1]-q['position'][1];c,z=math.cos(q['yaw']),math.sin(q['yaw']);f=dx*c+dy*z;l=-dx*z+dy*c
 return .08<f<.30 and abs(l)<.12
for seed in range(a.seed,a.seed+a.count):
 s=m.SharedScene(seed=seed,seconds=180);initial=layouts[str(seed)];s.ball=list(initial['ball'])
 for n,point in initial['robots'].items():s.players[n].update(json.loads(json.dumps(point)),standing=True)
 s.velocity=list(initial.get('velocity',[0,0,0]));s.touch=s.engine.last_touch=initial.get('touch');s.initial_setup=initial;s.frames=[]
 if a.trace:s._record()
 entry=None;entry_ball=None;contact=None;contact_before_loss=False;loss=None;breakthrough=None;contact_first_result=None;red_control=False;exclusive_blue=0.;exclusive_red=0.;minsep=99;seen=0;post_loss_foot=False;productive=False;regain_anchor=None;blue_owner=False;states=Counter();stages=Counter();maxstall=stall=0.;anchor=None;steps=0;first_result=None;outcomes=[]
 while s.step():
  dt=s.model.dt;steps+=1;red=s.players['RedForwardA']['position'];blue=s.players['BlueDefender']['position'];b=s.ball;sep=length(red,blue);minsep=min(minsep,sep)
  rf,bf=foot(s,'RedForwardA'),foot(s,'BlueDefender')
  red_active=s.previous_foot_contact=='RedForwardA';blue_active=s.previous_foot_contact=='BlueDefender'
  red_control |= rf and not bf and red_active
  exclusive_blue=exclusive_blue+dt if bf and not rf and blue_active else 0.
  exclusive_red=exclusive_red+dt if rf and not bf and red_active else 0.
  if entry is None and loss is None and red_control and sep<.65 and max(length(x,b) for x in (red,blue))<.60:
   entry=s.time;entry_ball=tuple(b[:2])
  if sep<=2*s.model.robot_radius+1e-5:
   if contact is None:contact=s.time;contact_before_loss=loss is None
  if loss is None and exclusive_blue>=.24:
   loss=s.time
   if entry is not None and first_result is None:first_result='LOST';outcomes.append(('LOST',s.time))
  # A breakthrough requires Red foot control beyond Blue, not a ball-only ricochet.
  if breakthrough is None and exclusive_red>=.24 and red[0]>blue[0]+.25 and b[0]>blue[0]+.35:
   breakthrough=s.time
   if entry is not None and first_result is None:first_result='BROKE_THROUGH';outcomes.append(('BROKE_THROUGH',s.time))
  if contact is not None and contact_first_result is None:
   if exclusive_blue>=.24:contact_first_result='LOST'
   elif exclusive_red>=.24 and red[0]>blue[0]+.25 and b[0]>blue[0]+.35:contact_first_result='BROKE_THROUGH'
  for e in s.events[seen:]:
   if e['event']=='foot_control_change':
    if e['robot']=='BlueDefender':blue_owner=True;regain_anchor=None
    elif e['robot']=='RedForwardA' and blue_owner:post_loss_foot=True;regain_anchor=tuple(b[:2]);blue_owner=False
  if regain_anchor and b[0]>regain_anchor[0]+.3 and s.touch=='RedForwardA':productive=True;regain_anchor=None
  seen=len(s.events);d=s.current_decisions.get('RedForwardA');states[d.behaviour if d else 'WAIT']+=dt;stages[s.navigation_stages.get('RedForwardA','WAIT')]+=dt
  close=sep<.42 and max(length(x,b) for x in (red,blue))<.5
  if close and anchor and length(b,anchor)<.06:stall+=dt;maxstall=max(stall,maxstall)
  else:stall=0.;anchor=tuple(b[:2]) if close else None
 assert abs(sum(states.values())-(s.time-s.model.dt))<1e-6
 if entry is not None and first_result is None:first_result='GOAL_WITHOUT_MEASURED_BREAK' if s.outcome=='GOAL' else 'UNRESOLVED'
 if contact is not None and contact_first_result is None:contact_first_result='GOAL_WITHOUT_MEASURED_BREAK' if s.outcome=='GOAL' else 'UNRESOLVED'
 row={'seed':seed,'outcome':s.outcome,'seconds':s.time,'first_contest_at':entry,'first_contest_result':first_result,'first_body_contact_at':contact,'body_contact_before_first_loss':contact_before_loss,'first_contact_result':contact_first_result,'first_exclusive_blue_foot_at':loss,'first_breakthrough_at':breakthrough,'minimum_body_distance':minsep,'attacker_regain':post_loss_foot,'productive_regain':productive,'longest_stall_seconds':maxstall,'attacker_states_seconds':dict(states),'attacker_stages_seconds':dict(stages),'terminal_touch':s.touch}
 rows.append(row)
 if seed in a.trace:(a.output.parent/(a.output.stem+'-'+str(seed)+'-trace.json')).write_text(json.dumps(s.report(),separators=(',',':')))
 if len(rows)%40==0:print('PROGRESS',len(rows),dict(Counter(x['outcome'] for x in rows)),flush=True)
contests=[x for x in rows if x['first_contest_at'] is not None];contacts=[x for x in rows if x['first_body_contact_at'] is not None];before=[x for x in contacts if x['body_contact_before_first_loss']]
summary={'runs':len(rows),'outcomes':dict(Counter(x['outcome'] for x in rows)),'first_attacking_contests':len(contests),'first_contest_results':dict(Counter(x['first_contest_result'] for x in contests)),'body_contact_runs':len(contacts),'body_contact_before_first_loss_runs':len(before),'contact_before_loss_results':dict(Counter(x['first_contact_result'] for x in before)),'goals_after_body_contact':sum(x['outcome']=='GOAL' for x in contacts),'exclusive_blue_control_runs':sum(x['first_exclusive_blue_foot_at'] is not None for x in rows),'breakthrough_runs':sum(x['first_breakthrough_at'] is not None for x in rows),'attacker_regain_runs':sum(x['attacker_regain'] for x in rows),'productive_regain_runs':sum(x['productive_regain'] for x in rows),'stalls_over_20s':sum(x['longest_stall_seconds']>20 for x in rows),'mean_seconds':sum(x['seconds'] for x in rows)/len(rows),'wall_seconds':time.perf_counter()-start}
a.output.write_text(json.dumps({'summary':summary,'runs':rows,'observer_schema':2,'source':m.source_info(),'tuning':a.tuning,'definitions':{'contest_entry':'Before first loss, Red has held exclusive foot geometry; body separation <0.65m and both within 0.60m of ball.','loss':'Blue has most recent active foot contact and exclusively occupies forward foot window for >=0.24s.','breakthrough':'Red has most recent active foot contact and exclusive foot window >=0.24s; Red x > Blue x+0.25m and ball x > Blue x+0.35m.','contact':'Body separation <=2*robot_radius+1e-5 after collision resolution.','warning':'Conditional cohorts change with policy; compare full fixed-layout counts too. Body contact need not be frontal, and later goals do not imply first-contest success.'}},indent=2));print(json.dumps(summary),flush=True)
