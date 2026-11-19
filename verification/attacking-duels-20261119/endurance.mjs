import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),url=process.env.TDP_SHARED_URL;
const port=fs.readFileSync(process.env.TDP_1V1_QA_PROFILE+'/DevToolsActivePort','utf8').split('\n')[0];
const pages=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let seq=0;const pending=new Map(),errors=[],requests=[],networkFailures=[];
ws.onmessage=({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);if(m.method==='Network.loadingFailed')networkFailures.push(m.params);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(m.error);else p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const ev=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(expression,timeout=6000){const end=Date.now()+timeout;while(Date.now()<end){if(await ev(expression))return;await delay(35);}throw new Error('Timed out: '+expression+'; '+await ev('document.getElementById("notice").textContent'));}
const samples=[],seen=new Set();
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.state');
 await send('Page.bringToFront');await ev('document.getElementById("play").click()');
 const began=Date.now();let changedLanguage=false,lastPrint=0;
 while(Date.now()-began<120000){
  await delay(1000);await send('Page.bringToFront');
  if(await ev('!sharedView.running&&!sharedView.state.outcome'))await ev('document.getElementById("play").click()');
  const sample=await ev('({wall:performance.now(),seed:sharedView.meta.seed,t:sharedView.state.t,round:sharedView.session.round,running:sharedView.running,outcome:sharedView.state.outcome,goals:sharedView.session.goals,clearances:sharedView.session.clearances})');
  if(!seen.has(sample.seed)){
   const report=await(await fetch(url+'/api/report')).json();
   const q=report.initial_setup,d=q.robots.BlueDefender.position,a=q.robots.RedForwardA.position,b=q.ball;
   const goal=p=>Math.hypot(4.5-p[0],p[1]);
   assert.ok(goal(d)+.25<=Math.min(goal(a),goal(b)));
   seen.add(sample.seed);
  }
  samples.push(sample);
  if(Date.now()-began>60000&&!changedLanguage){await ev('document.getElementById("language").click()');changedLanguage=true;}
  if(Date.now()-began-lastPrint>15000){lastPrint=Date.now()-began;console.log('ENDURANCE',Math.round(lastPrint/1000),JSON.stringify(sample));}
  assert.equal(errors.length,0);
 }
 const result={wall_seconds:(Date.now()-began)/1000,rounds:seen.size,latest:samples.at(-1),language_switch_during_play:changedLanguage,default_8x:await ev('document.getElementById("speed").value'),runtime_errors:errors,samples};
 assert.ok(seen.size>=5);
 fs.writeFileSync(here+'/endurance-check.json',JSON.stringify(result,null,2)+'\n');
 console.log('ENDURANCE_OK',JSON.stringify({rounds:seen.size,seconds:result.wall_seconds,errors:errors.length}));
}finally{ws.close();}
