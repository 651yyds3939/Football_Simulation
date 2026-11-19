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
const checks={};
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.state');
 const post=async(endpoint,data)=>(await fetch(url+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json();
 let state=await post('/api/new',{seed:50000,seconds:180,scenario:'random'});
 for(let i=0;i<900&&state.state.attacker.state!=='COUNTERPRESS'&&!state.state.outcome;i++)state=await post('/api/step',{steps:5});
 assert.equal(state.state.attacker.state,'COUNTERPRESS');
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.meta&&sharedView.state&&sharedView.meta.seed===50000&&sharedView.state.t>0');
 assert.equal(await ev('document.getElementById("attackerState").textContent'),'Win back the ball');
 assert.match(await ev('document.getElementById("attackerReason").textContent'),/PRESS|ball/);
 checks.counterpress_visible_in_english=true;
 await ev('document.getElementById("language").click()');
 assert.equal(await ev('document.getElementById("attackerState").textContent'),'丢球反抢');
 assert.match(await ev('document.getElementById("status").textContent'),/红方丢球/);
 checks.counterpress_visible_in_chinese=true;
 const image=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(here+'/counterpress-zh.png',Buffer.from(image.data,'base64'));
 for(let i=0;i<5&&!state.state.outcome;i++)state=await post('/api/step',{steps:2000});
 assert.ok(state.state.outcome);
 await send('Page.navigate',{url});await until('window.sharedView&&sharedView.state&&!!sharedView.state.outcome');
 // A reload starts in English; switch to Chinese for the final-state label.
 await ev('document.getElementById("language").click()');
 assert.equal(await ev('sharedView.state.attacker.state'),'FINISHED');
 assert.equal(await ev('sharedView.state.defender.state'),'FINISHED');
 assert.equal(await ev('document.getElementById("attackerState").textContent'),'本次结束');
 assert.equal(await ev('sharedView.state.attacker.action'),'stand');
 const before=JSON.stringify(state.state);
 state=await post('/api/step',{steps:100});
 assert.equal(JSON.stringify(state.state),before);
 checks.terminal_stops_without_formation=true;checks.terminal_repeated_steps_are_idempotent=true;
 checks.runtime_errors=errors;assert.equal(errors.length,0);
 fs.writeFileSync(here+'/policy-browser-check.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks,null,2));
}finally{ws.close();}
