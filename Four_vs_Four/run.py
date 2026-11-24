"""Compute a full planar 4v4 match as fast as possible, then view its replay."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
from collections import Counter
import argparse,hashlib,json,sys,time,webbrowser
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'backend/tools'))
from soccer2d import Simulation,Model
from pass_report import PassReport
from Utils.TeamTactics import TacticalPolicy
from Utils.Passing import PassingPolicy
from Utils.PreviousTactics import TacticalPolicy as PreviousPolicy
from Utils.TeamNavigation import TeamSimulation
Simulation=TeamSimulation
from Utils.ProcessSupervisor import ROBOT_NAMES
from Utils import CourseSpecs as specs

def source_hashes():
 return {str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.rglob('*.py') if '__pycache__' not in str(p) and 'runs' not in p.relative_to(HERE).parts}

POLICIES = ("baseline", "previous", "reference", "passing", "relay", "coordinated", "flow")


def create_match(seed, red="flow", blue="flow", model=None):
    s = Simulation(seed, "RED", "baseline", model or Model())
    s.flow.enabled = {team for team, policy in (("Red", red), ("Blue", blue)) if policy == "flow"}
    s.reset_on_goal = s.clip_body_contacts = bool(s.flow.enabled)
    for name in s.names:
        selected = red if name.startswith("Red") else blue
        if selected in ("flow", "coordinated", "relay", "passing"):
            s.policies[name] = PassingPolicy(name, goal_depth=0.3, model=s.model)
            if selected in ("coordinated", "relay"):
                s.contest_players.add(name)
            if selected == "coordinated" and name.endswith("Goalkeeper"):
                s.goal_cover.defend.add(name)
        elif selected == "reference":
            s.policies[name] = TacticalPolicy(name, goal_depth=0.3)
        elif selected == "previous":
            s.policies[name] = PreviousPolicy(name, goal_depth=0.3)
    s.install_team_navigators()
    return s


def play(seed,red,blue,model,record=False):
 s=create_match(seed,red,blue,model);frames=[]
 report=PassReport()
 def observe(sim):
  report.observe(sim)
  if not record:
   return
  w=sim.observation();players=[]
  for n in ROBOT_NAMES:
   p=sim.players[n];held=sim.kicking.get(n)
   players.append([round(p['position'][0],6),round(p['position'][1],6),round(p['yaw'],6),sim.last_decisions.get(n,''),sim.last_actions.get(n,''),held[1].kick if held else '',round(max(0,held[0]-sim.time),3) if held else 0,list(sim.current_decisions[n].target) if n in sim.current_decisions else None,list(sim.current_decisions[n].face) if n in sim.current_decisions else None])
  frames.append({'t':round(sim.time,6),'match':w['match'],'ball':[round(v,6) for v in sim.ball[:2]],'velocity':[round(v,6) for v in sim.velocity[:2]],'players':players,'touch':sim.touch,'pass':dict(w['pass_intent']) if 'pass_intent' in w else None})
 result=s.run(observer=observe);result['policies']={'RED':red,'BLUE':blue}
 result['directed_passes']=report.summary()
 geometry={name:getattr(specs,name) for name in ('PITCH_LENGTH','PITCH_WIDTH','GOAL_WIDTH','GOAL_HEIGHT','GOAL_DEPTH','GOAL_AREA_LENGTH','GOAL_AREA_WIDTH','PENALTY_AREA_LENGTH','PENALTY_AREA_WIDTH','PENALTY_MARK_DISTANCE','CENTRE_CIRCLE_DIAMETER','BORDER_WIDTH','LINE_WIDTH','BALL_RADIUS')}
 candidate = 'flow' if 'flow' in (red, blue) else 'baseline' if red == blue == 'baseline' else 'coordinated'
 candidate_team = 'BOTH' if red == blue else 'RED' if red == candidate else 'BLUE'
 scene={'schema':2,'seed':seed,'candidate':candidate,'candidateTeam':candidate_team,'policies':result['policies'],'names':list(ROBOT_NAMES),'geometry':geometry,'model':asdict(model),'frames':frames,'events':s.events,'result':result,'source_sha256':source_hashes()}
 return result,scene

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seed',type=int,default=27);p.add_argument('--red-policy',choices=POLICIES,default='flow');p.add_argument('--blue-policy',choices=POLICIES,default='flow');p.add_argument('--half-seconds',type=float,default=300);p.add_argument('--ready-seconds',type=float,default=10);p.add_argument('--dt',type=float,default=.2);p.add_argument('--batch',type=int,default=1);p.add_argument('--language',choices=['en','zh'],default='en');p.add_argument('--no-replay',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--open',action='store_true');a=p.parse_args()
 if a.batch<1:p.error('--batch must be positive')
 try:model=Model(dt=a.dt,half_seconds=a.half_seconds,ready_seconds=a.ready_seconds)
 except ValueError as e:p.error(str(e))
 output=a.output or HERE/'runs'/datetime.now().strftime('match_%Y%m%d_%H%M%S_%f')
 if output.exists():p.error('Use a fresh output directory to preserve previous results')
 output.mkdir(parents=True);rows=[];start=time.perf_counter()
 for i in range(a.batch):
  result,scene=play(a.seed+i,a.red_policy,a.blue_policy,model,record=i==0 and not a.no_replay);rows.append(result)
  if i==0 and not a.no_replay:
   template=(HERE/'backend/tools'/('soccer2d_viewer_en.html' if a.language=='en' else 'soccer2d_viewer.html')).read_text()
   data=json.dumps(scene,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026');(output/'replay.html').write_text(template.replace('__SCENE_DATA__',data),encoding='utf-8');(output/'scene.json').write_text(json.dumps(scene,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
  print('4V4_RESULT',a.seed+i,result['score_red_blue'],flush=True)
 elapsed=time.perf_counter()-start
 summary={'games':len(rows),'policies':{'RED':a.red_policy,'BLUE':a.blue_policy},'goals_red':sum(r['score_red_blue'][0] for r in rows),'goals_blue':sum(r['score_red_blue'][1] for r in rows),'simulated_seconds':sum(r['simulated_seconds'] for r in rows),'wall_seconds':elapsed,'computation_speedup':sum(r['simulated_seconds'] for r in rows)/max(elapsed,1e-9),'runs':rows,'source_sha256':source_hashes(),'limits':['2D exact-state kinematic discs; no balance, falls or cameras.','Playback speed does not change model rates.','Both improved teams playing each other is not evidence against the baseline.']}
 summary['directed_pass_totals']={
  team: {key:sum(row['directed_passes'][team][key] for row in rows)
         for key in ('attempts','intended_body_contacts','intended_foot_contacts','advanced_025m')}
  for team in ('RED','BLUE')
 }
 (output/'metrics.json').write_text(json.dumps(summary,indent=2)+'\n');print('4V4_READY',output.resolve(),flush=True);print('COMPUTATION_SPEEDUP',round(summary['computation_speedup'],1),flush=True)
 if a.open and not a.no_replay:webbrowser.open((output/'replay.html').resolve().as_uri())
if __name__=='__main__':main()
