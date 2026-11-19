import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),url=process.env.TDP_SHARED_URL;
const port=fs.readFileSync(process.env.TDP_1V1_QA_PROFILE+'/DevToolsActivePort','utf8').split('\n')[0];
const pages=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let seq=0;const pending=new Map(),errors=[];
ws.onmessage=({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(m.error);else p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const ev=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(expression,timeout=6000){const end=Date.now()+timeout;while(Date.now()<end){if(await ev(expression))return;await delay(35);}throw new Error('Timed out: '+expression);}
const post=async(endpoint,data)=>(await fetch(url+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
const checks={};
try{
 await send('Page.enable');await send('Runtime.enable');
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.state');
 let state=await post('/api/new',{seed:27,seconds:180,scenario:'random'});
 for(let i=0;i<100&&state.state.attacker.state!=='EVADE_DRIBBLE'&&!state.state.outcome;i++)state=await post('/api/step',{steps:1});
 assert.equal(state.state.attacker.state,'EVADE_DRIBBLE');assert.ok(state.state.attacker.ballTarget);
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.state&&sharedView.state.attacker.state==="EVADE_DRIBBLE"');
 assert.equal(await ev('document.getElementById("attackerState").textContent'),'Carry around defender');checks.english_evasion_label=true;
 await ev('document.getElementById("language").click()');assert.equal(await ev('document.getElementById("attackerState").textContent'),'绕行带球');assert.match(await ev('document.getElementById("status").textContent'),/侧路/);checks.chinese_evasion_label=true;
 assert.ok(await ev('Number.isFinite(sharedView.state.attacker.ballTarget.x)&&Number.isFinite(sharedView.state.attacker.ballTarget.y)'));checks.intended_ball_lane_in_snapshot=true;
 const img=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(here+'/evasion-zh.png',Buffer.from(img.data,'base64'));
 for(let i=0;i<5&&!state.state.outcome;i++)state=await post('/api/step',{steps:2000});assert.ok(state.state.outcome);assert.equal(state.state.attacker.ballTarget,null);assert.equal(state.state.attacker.state,'FINISHED');checks.terminal_clears_ball_lane=true;
 const before=JSON.stringify(state.state);state=await post('/api/step',{steps:100});assert.equal(JSON.stringify(state.state),before);checks.finished_scene_idempotent=true;
 checks.runtime_errors=errors;assert.equal(errors.length,0);fs.writeFileSync(here+'/attacking-browser-check.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks,null,2));
}finally{ws.close();}
