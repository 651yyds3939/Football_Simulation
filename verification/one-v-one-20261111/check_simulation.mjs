import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const here=path.dirname(fileURLToPath(import.meta.url));
const html=fs.readFileSync(path.resolve(here,'../../2D_1v1_Demo_2026-11-11/index.html'),'utf8');
const config=JSON.parse(html.match(/<script id="config"[^>]*>([\s\S]*?)<\/script>/)[1]);
vm.runInThisContext(html.match(/<script id="simulation-core">([\s\S]*?)<\/script>/)[1]);
const {Simulation,distance}=Football1v1;
const checks={};

const continuing=new Simulation(config,'duel',27);
while(continuing.t<40)continuing.step();
assert.equal(continuing.outcome,null);
assert.ok(continuing.stats.clearancesCompleted>0);
assert.equal(continuing.events.filter(e=>e.kind==='clearance_completed').length,continuing.stats.clearancesCompleted);
checks.clearance_does_not_end_play={seconds:continuing.t,clearances:continuing.stats.clearancesCompleted};

const rolling=new Simulation(config);
rolling.ball={x:0,y:2,vx:.5,vy:0};
for(let i=0;i<50;i++)rolling.roll();
assert.ok(Math.abs(rolling.ball.x-.5**2/(2*config.rolling_deceleration))<1e-10);
assert.equal(rolling.ball.vx,0);checks.rolling_stopping_distance=rolling.ball.x;

const boundary=new Simulation(config);
boundary.ball={x:4.56,y:0,vx:0,vy:0};boundary.boundary({x:4.49,y:0});assert.equal(boundary.outcome,null);
boundary.ball.x=4.58;boundary.boundary({x:4.56,y:0});assert.equal(boundary.outcome,'GOAL');
const diagonal=new Simulation(config);
diagonal.ball={x:5,y:4,vx:0,vy:0};diagonal.boundary({x:4,y:2.8});assert.equal(diagonal.outcome,'OUT');
const post=new Simulation(config);
post.ball={x:4.58,y:1.25,vx:0,vy:0};post.boundary({x:4.55,y:1.25});assert.equal(post.outcome,'OUT');
checks.whole_ball_goal_and_first_boundary=true;

const miss=new Simulation(config,'shot');miss.beginKick(miss.attacker,'SHOOT');
miss.ball.x=2;miss.t=config.shot_seconds+.1;miss.completeKick(miss.attacker);
assert.equal(miss.stats.shotContacts,0);assert.ok(miss.events.some(e=>e.kind==='kick_missed'));
checks.no_remote_kick_when_ball_has_moved=true;

const overlap=new Simulation(config);
overlap.moveObject('defender',overlap.attacker.x,overlap.attacker.y);
assert.ok(distance(overlap.attacker,overlap.defender)>=2*config.robot_radius-1e-6);
assert.ok(overlap.customSetup);assert.ok(overlap.events.some(e=>e.kind==='manual_setup'));
checks.custom_setup_and_disc_separation=true;

const results=[];
for(const scene of ['duel','lane','shot','random'])for(const seed of scene==='random'?Array.from({length:64},(_,i)=>i):[0,1,7,27,42,99,123,2026]){
 const sim=new Simulation(config,scene,seed);
 while(!sim.outcome){
  sim.step();
  for(const obj of [sim.attacker,sim.defender,sim.ball])assert.ok(Number.isFinite(obj.x)&&Number.isFinite(obj.y));
  assert.ok(distance(sim.attacker,sim.defender)>=2*config.robot_radius-1e-4);
  assert.ok(sim.t<=config.round_seconds+config.dt+.00001);
 }
 assert.equal(sim.report().samples[0].t,0);
 if(sim.outcome==='GOAL'){assert.ok(sim.ball.x>config.pitch_length/2+config.ball_radius);assert.ok(Math.abs(sim.ball.y)+config.ball_radius<config.goal_width/2);}
 assert.notEqual(sim.outcome,'CLEARED');
 assert.equal(sim.events.filter(e=>e.kind==='clearance_completed').length,sim.stats.clearancesCompleted);
 results.push({scene,seed,outcome:sim.outcome,simulated_seconds:+sim.t.toFixed(2),...sim.stats});
 if(seed===27)fs.writeFileSync(path.join(here,scene+'-seed27.json'),JSON.stringify(sim.report(),null,2));
}
const one=new Simulation(config,'random',27),two=new Simulation(config,'random',27);
for(let i=0;i<1500;i++){one.step();two.step();}
assert.deepEqual(one.report(),two.report());checks.repeatable_seed=true;
const starts=new Set(Array.from({length:20},(_,seed)=>JSON.stringify(new Simulation(config,'random',seed).initialSetup)));
assert.equal(starts.size,20);checks.different_seeds_change_start_positions=starts.size;
const randomResults=results.filter(r=>r.scene==='random');
checks.random_outcomes=randomResults.reduce((counts,r)=>{counts[r.outcome]=(counts[r.outcome]||0)+1;return counts;},{});
assert.ok(Object.keys(checks.random_outcomes).length>1);
checks.fixtures=results;
checks.limitations='Checks cover this independent planar model; they do not establish hardware or 4v4 performance.';
fs.writeFileSync(path.join(here,'simulation-check.json'),JSON.stringify(checks,null,2)+'\n');
console.log(JSON.stringify(checks,null,2));
