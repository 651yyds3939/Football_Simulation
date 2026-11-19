"""Declared two-teammate fixture, not a match-performance measurement."""
from pathlib import Path
import argparse,sys,json,math
p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--tuning',type=json.loads,default={});a=p.parse_args()
sys.path.insert(0,str(a.app/'backend/tools'))
from soccer2d import Simulation,Model
from Utils.TeamTactics import TacticalPolicy,SETTINGS
from Utils.TeamPolicy import Decision
SETTINGS.update(a.tuning)
class Still:
 def __init__(self,name):self.team='BLUE' if name.startswith('Blue') else 'RED'
 def decide(self,w):return Decision('WAIT',tuple(w['robots']['BlueDefender']['position'][:2]),tuple(w['ball']['position'][:2]))
rows=[]
for seed in range(20):
 s=Simulation(seed,candidate='baseline',model=Model(dt=.04),active_names=('RedForwardA','RedForwardB','BlueDefender'))
 s.engine.phase='PLAYING';s.engine.half_started=0;s.engine.released=True;s.engine.red_direction=1;s.engine.restart_goal_guard=False;s.engine.kickoff_restriction=False;s.engine.restart_touch='RedForwardA';s.engine.restart_team='RED';s.engine.restart='DROP_BALL'
 s.ball=[0.,0.,.07];s.velocity=[0.,0.,0.]
 s.players['RedForwardA'].update(position=[-.17,-.05,.334],yaw=0.)
 s.players['RedForwardB'].update(position=[.45,.40,.334],yaw=math.pi)
 s.players['BlueDefender'].update(position=[.80,.0,.334],yaw=math.pi)
 s.policies={n:Still(n) if n=='BlueDefender' else TacticalPolicy(n,goal_depth=.3) for n in s.names}
 for _ in range(1500):s.step()
 rows.append({'seed':seed,'stats':{t:dict(x) for t,x in s.stats.items()},'passes':[e for e in s.events if e['event'] in ('kick_start','kick_contact','pass_result','foot_control_change')],'final_ball':s.ball})
a.output.write_text(json.dumps(rows,indent=2));print('completed',sum(r['stats']['RED'].get('completed_passes',0) for r in rows),'targeted attempts',sum(bool(e.get('receiver')) for r in rows for e in r['passes'] if e['event']=='kick_start'))
