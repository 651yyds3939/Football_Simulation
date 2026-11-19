import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..');
const port=fs.readFileSync(process.env.DEMO_BROWSER_PROFILE+'/DevToolsActivePort','utf8').split('\n')[0];
const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let id=0;const pending=new Map(),errors=[],requests=[];
ws.onmessage=({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(expression){for(let i=0;i<100;i++){if(await ev(expression))return;await delay(30);}throw Error('Timed out: '+expression);}
const results={};
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1120,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:pathToFileURL(root+'/Football_1v1_Demo.html').href});
 await until('window.simpleReplay&&simpleReplay.state&&simpleReplay.state.t>.1');
 assert.equal(await ev('document.getElementById("speed").value'),'8');
 assert.equal(await ev('simpleReplay.running'),true);results.offline_autoplay_at_8x=true;
 await ev('document.getElementById("play").click()');
 const paused=await ev('simpleReplay.state.t');await delay(180);assert.equal(await ev('simpleReplay.state.t'),paused);results.pause=true;
 const records=await ev('simpleReplay.records');
 assert.equal(records.length,5);assert.equal(new Set(records.map(r=>r.seed)).size,5);
 assert.equal(await ev('document.getElementById("scene").options.length'),5);
 const endings=['CLEARED_GOAL','GOAL','GOAL','CLEARED_GOAL','TIMEOUT'];
 for(let n=0;n<records.length;n++){
  // CDP serializes signed zero as zero, just as JSON.stringify does.
  const originalData=JSON.parse(fs.readFileSync(here+'/recordings/'+records[n].seed+'.json','utf8'));
  const original=JSON.parse(JSON.stringify(originalData));
  const hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
  assert.equal(hash(records[n].frames),hash(original.frames));
  await ev(`document.getElementById('scene').value='${n}';document.getElementById('scene').dispatchEvent(new Event('change'));document.getElementById('play').click()`);
  for(const index of [0,73,records[n].frames.length-1]){
   await ev(`document.getElementById('seek').value='${index}';document.getElementById('seek').dispatchEvent(new Event('input'))`);
   const f=await ev('simpleReplay.state');
   for(const key of ['ball','attacker','defender','outcome'])assert.deepEqual(f[key],original.frames[index][key]);
  }
  await ev(`document.getElementById('seek').value='${records[n].frames.length-8}';document.getElementById('seek').dispatchEvent(new Event('input'));document.getElementById('speed').value='32';document.getElementById('play').click()`);
  await until('!!simpleReplay.state.outcome');assert.equal(await ev('simpleReplay.running'),false);
  assert.equal(await ev('simpleReplay.state.outcome'),endings[n]);
 }
 results.examples=records.map((r,n)=>({seed:r.seed,outcome:endings[n]}));
 results.recordings_equal_original_frames=true;results.seeking_all_five_endings=true;
 await ev("document.getElementById('scene').value='0';document.getElementById('scene').dispatchEvent(new Event('change'));document.getElementById('seek').value='1';document.getElementById('seek').dispatchEvent(new Event('input'));document.getElementById('speed').value='8'");
 await delay(100);
 let screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(here+'/desktop.png',Buffer.from(screenshot.data,'base64'));
 await ev("document.getElementById('language').click()");assert.equal(await ev('document.documentElement.lang'),'zh-CN');results.bilingual=true;
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await delay(100);
 assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'));results.mobile_no_overflow=true;
 screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(here+'/mobile.png',Buffer.from(screenshot.data,'base64'));
 assert.equal(errors.length,0);assert.equal(requests.filter(u=>/^https?:/.test(u)).length,0);
 results.runtime_errors=errors;results.no_network_requests=true;
 fs.writeFileSync(here+'/browser-check.json',JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results,null,2));
}finally{ws.close();}
