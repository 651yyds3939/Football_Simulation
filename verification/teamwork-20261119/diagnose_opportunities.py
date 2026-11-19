from pathlib import Path
import sys,json,math,collections
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'candidate-app/backend/tools'))
from soccer2d import Simulation
from Utils.PreviousTactics import TacticalPolicy
from Utils.TeamPolicy import distance,lane_clear
counts=collections.Counter();examples=[]
for seed in range(210000,210008):
 s=Simulation(seed,candidate='baseline');s.policies={n:TacticalPolicy(n,goal_depth=.3) for n in s.names}
 def observe(sim):
  if sim.engine.phase!='PLAYING' or not sim.engine.released:return
  for team in ['RED','BLUE']:
   own=[n for n in sim.names if sim.policies[n].team==team];enemy=[sim.players[n]['position'] for n in sim.names if sim.policies[n].team!=team];ball=sim.ball;carrier=min(own,key=lambda n:distance(sim.players[n]['position'],ball));p=sim.players[carrier]
   if distance(p['position'],ball)>.35:continue
   counts['carrier_near_seconds']+=sim.model.dt;counts[sim.policies[carrier].role+'_near_seconds']+=sim.model.dt
   for n in own:
    if n==carrier or 'Goalkeeper' in n:continue
    q=sim.players[n]['position'];gap=distance(q,ball)
    if gap>1.0:continue
    counts['mate_within_1m_player_seconds']+=sim.model.dt
    if not lane_clear(ball,q,enemy,.30):continue
    counts['clear_near_mate_seconds']+=sim.model.dt
    if sim.engine.direction(team)*(q[0]-ball[0])>.1:
     counts['forward_near_mate_seconds']+=sim.model.dt
     if len(examples)<8:examples.append({'seed':seed,'time':sim.time,'carrier':carrier,'mate':n,'gap':gap,'decision':vars(sim.current_decisions[carrier])})
 s.run(observer=observe)
(H/'pass-opportunities.json').write_text(json.dumps({'counts':dict(counts),'examples':examples},indent=2));print(json.dumps(counts,indent=2))
