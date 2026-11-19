"""Record selected 3:3:1 cases from the unchanged current 1v1 policy."""
from pathlib import Path
import importlib.util,json,math,hashlib
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'2D_Shared_Policy_2026-11-11'
spec=importlib.util.spec_from_file_location('case_source',APP/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CASES=[('contact_breakthrough',466),('contact_breakthrough',456),('contact_breakthrough',364),('tackle_counter_goal',440),('tackle_counter_goal',414),('tackle_counter_goal',457),('failed_recovery',431)]
records=[];summaries=[]
def foot(s,n):
 p=s.players[n];dx,dy=s.ball[0]-p['position'][0],s.ball[1]-p['position'][1];front=dx*math.cos(p['yaw'])+dy*math.sin(p['yaw']);side=-dx*math.sin(p['yaw'])+dy*math.cos(p['yaw']);return .08<front<.30 and abs(side)<.12
for kind,seed in CASES:
 s=m.SharedScene(seed=seed,scenario='random',seconds=180);frontal=None;first_result=None;breakthrough=None;loss=None;exclusive_red=exclusive_blue=0.;red_control=False;minimum=99.;contact=None;critical={};recovery=[]
 while s.step():
  a=s.players['RedForwardA'];b=s.players['BlueDefender'];ball=s.ball;sep=math.dist(a['position'][:2],b['position'][:2]);minimum=min(minimum,sep);rf,bf=foot(s,'RedForwardA'),foot(s,'BlueDefender');ra=s.previous_foot_contact=='RedForwardA';ba=s.previous_foot_contact=='BlueDefender';red_control|=rf and not bf and ra
  exclusive_red=exclusive_red+s.model.dt if rf and not bf and ra else 0.;exclusive_blue=exclusive_blue+s.model.dt if bf and not rf and ba else 0.
  if contact is None and sep<=2*s.model.robot_radius+1e-5:contact=s.time;critical[s.time]=s.snapshot()
  if frontal is None and loss is None and breakthrough is None and red_control and sep<=2*s.model.robot_radius+1e-5:
   bearing=math.atan2(b['position'][1]-a['position'][1],b['position'][0]-a['position'][0]);opposite=math.atan2(a['position'][1]-b['position'][1],a['position'][0]-b['position'][0])
   if max(math.dist(p['position'][:2],ball[:2]) for p in [a,b])<.4 and math.cos(a['yaw']-bearing)>.5 and math.cos(b['yaw']-opposite)>.5 and a['position'][0]<b['position'][0]+.05:frontal=s.time;critical[s.time]=s.snapshot()
  if exclusive_blue>=.24 and loss is None:
   loss=s.time;critical[s.time]=s.snapshot()
   if frontal is not None and first_result is None:first_result='LOST'
  if exclusive_red>=.24 and a['position'][0]>b['position'][0]+.25 and ball[0]>b['position'][0]+.35 and breakthrough is None:
   breakthrough=s.time;critical[s.time]=s.snapshot()
   if frontal is not None and first_result is None:first_result='BROKE_THROUGH'
  if ball[0]>b['position'][0]+.35 and ra:
   recovery.append({'t':s.time,'attacker_ahead':a['position'][0]-b['position'][0],'ball_ahead':ball[0]-b['position'][0],'defender_action':s.last_actions.get('BlueDefender'),'defender_state':s.last_decisions.get('BlueDefender')})
 assert s.outcome==('CLEARED_GOAL' if kind=='tackle_counter_goal' else 'GOAL'),(seed,s.outcome)
 if kind=='contact_breakthrough':assert frontal is not None and first_result=='BROKE_THROUGH' and breakthrough>frontal,(seed,frontal,first_result)
 elif kind=='tackle_counter_goal':assert red_control and loss is not None and contact is not None and s.touch=='BlueDefender',seed
 else:assert contact is None and recovery and max(r['ball_ahead'] for r in recovery)>.8,seed
 # Retain sampled frames and insert the exact 0.04s contact/control moments.
 frames={f['t']:f for f in s.frames};frames.update(critical);frames[s.time]=s.snapshot();frames=[frames[t] for t in sorted(frames)]
 data={**m.envelope(s),'frames':frames,'kind':kind,'events':s.events};(H/(str(seed)+'.json')).write_text(json.dumps(data,separators=(',',':'),allow_nan=False))
 summary={**s.summary(),'kind':kind,'frames':len(frames),'first_contact_at':contact,'frontal_contact_at':frontal,'first_frontal_result':first_result,'breakthrough_at':breakthrough,'exclusive_blue_foot_at':loss,'minimum_body_separation':minimum,'max_ball_ahead_of_defender':max((r['ball_ahead'] for r in recovery),default=0),'foot_control_events':[e for e in s.events if e['event']=='foot_control_change']};summaries.append(summary)
 records.append({k:data[k] for k in ['kind','seed','frames','parameters','source','profile','spawn_zones']});print(kind,seed,s.outcome,round(s.time,2),flush=True)
(H/'summary.json').write_text(json.dumps({'ratio':'3:3:1 by case count, not duration or population success rate','cases':summaries,'simulated_seconds_total':sum(r['seconds'] for r in summaries),'source_sha256':m.source_info(),'limits':['Kinematic-disc contact, not real humanoid collision.','Selected examples, not a measured success distribution.','Same recorded data used by HTML and video.']},indent=2))
(H/'records.json').write_text(json.dumps(records,separators=(',',':'),ensure_ascii=False,allow_nan=False))
