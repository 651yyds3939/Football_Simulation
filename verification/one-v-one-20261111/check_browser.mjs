import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const profile=process.env.TDP_1V1_QA_PROFILE;
const port=fs.readFileSync(profile+'/DevToolsActivePort','utf8').split('\n')[0];
const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let sequence=0;const pending=new Map(),errors=[],requests=[];
socket.onmessage=({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);if(m.id){const p=pending.get(m.id);pending.delete(m.id);if(m.error)p.reject(m.error);else p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
const ev=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const checks={};
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1120,deviceScaleFactor:1,mobile:false});
 const file=process.env.TDP_1V1_HTML||path.resolve(here,'../../2D_1v1_Demo_2026-11-11/index.html');
 await send('Page.navigate',{url:pathToFileURL(file).href});
 for(let i=0;i<100;i++){if(await ev('!!window.demo'))break;await wait(40);}
 assert.ok(await ev('!!window.demo'));
 assert.equal(await ev('demo.sim.t'),0);assert.equal(await ev('demo.running'),false);
 assert.equal(await ev('document.getElementById("speed").value'),'2');assert.equal(await ev('demo.sim.scenario'),'random');checks.default_playback='2×';
 const initial=await ev('({seed:demo.sim.seed,setup:demo.sim.initialSetup})');
 await ev('document.getElementById("newSetup").click()');
 const changed=await ev('({seed:demo.sim.seed,setup:demo.sim.initialSetup})');
 assert.notEqual(changed.seed,initial.seed);assert.notDeepEqual(changed.setup,initial.setup);checks.new_random_setup=true;
 await ev('document.getElementById("reset").click()');
 assert.deepEqual(await ev('demo.sim.initialSetup'),changed.setup);checks.repeat_seed_same_initial_positions=true;
 assert.equal(await ev('document.documentElement.lang'),'en');
 assert.equal(await ev('/[\\u4e00-\\u9fff]/.test(document.body.innerText.replace("中文",""))'),false);
 checks.initial_state='paused, English, two players and one ball';
 await ev('document.getElementById("step").click()');assert.ok(Math.abs(await ev('demo.sim.t')-.2)<1e-9);checks.single_step=true;
 await ev('document.getElementById("play").click()');await wait(350);await ev('document.getElementById("play").click()');
 assert.ok(await ev('demo.sim.t')>.2);checks.live_play_and_pause=true;
 await ev('document.getElementById("reset").click()');assert.equal(await ev('demo.sim.t'),0);checks.reset=true;
 await ev('document.getElementById("seed").value=42;document.getElementById("seed").dispatchEvent(new Event("change"))');assert.equal(await ev('demo.sim.seed'),42);
 await ev('document.getElementById("seed").value=27;document.getElementById("seed").dispatchEvent(new Event("change"))');checks.seed_control=true;
 await ev('document.getElementById("autoNext").checked=false;document.getElementById("autoNext").dispatchEvent(new Event("change"));document.getElementById("scenario").value="shot";document.getElementById("scenario").dispatchEvent(new Event("change"))');
 assert.equal(await ev('demo.sim.scenario'),'shot');
 await ev('document.getElementById("speed").value="16";document.getElementById("play").click()');
 for(let i=0;i<80;i++){if(await ev('!!demo.sim.outcome'))break;await wait(80);}
 assert.equal(await ev('demo.sim.outcome'),'GOAL');assert.equal(await ev('demo.running'),false);
 checks.live_goal={outcome:await ev('demo.sim.outcome'),seconds:await ev('demo.sim.t'),shot_contacts:await ev('demo.sim.stats.shotContacts')};
 await ev('document.getElementById("language").click()');assert.equal(await ev('document.documentElement.lang'),'zh-CN');assert.match(await ev('document.getElementById("status").textContent'),/进球/);checks.bilingual=true;
 await ev('document.getElementById("reset").click()');
 // Real pointer drag, not direct simulator mutation.
 const drag=await ev('(()=>{const r=document.getElementById("pitch").getBoundingClientRect(),b=demo.sim.ball;return {x:r.left+(b.x+5.5)/11*r.width,y:r.top+(4-b.y)/8*r.height,dx:r.width*.018,dy:r.height*.02};})()');
 await send('Input.dispatchMouseEvent',{type:'mousePressed',x:drag.x,y:drag.y,button:'left',clickCount:1});
 await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:drag.x-drag.dx,y:drag.y-drag.dy,button:'left',buttons:1});
 await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:drag.x-drag.dx,y:drag.y-drag.dy,button:'left',clickCount:1});
 assert.equal(await ev('demo.sim.customSetup'),true);checks.pointer_drag=true;
 const downloadDir=path.join(here,'downloads');fs.mkdirSync(downloadDir,{recursive:true});
 await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloadDir});
 await ev('document.getElementById("export").click()');
 for(let i=0;i<60;i++){if(fs.readdirSync(downloadDir).some(n=>n.endsWith('.json')))break;await wait(40);}
 const downloaded=fs.readdirSync(downloadDir).find(n=>n.endsWith('.json'));assert.ok(downloaded);
 const report=JSON.parse(fs.readFileSync(path.join(downloadDir,downloaded),'utf8'));assert.equal(report.customSetup,true);checks.download_json=true;
 await ev('document.getElementById("scenario").value="duel";document.getElementById("scenario").dispatchEvent(new Event("change"));document.getElementById("speed").value="16";document.getElementById("play").click()');
 for(let i=0;i<100;i++){if(await ev('demo.sim.t>=35'))break;await wait(50);}
 await ev('document.getElementById("play").click()');
 assert.equal(await ev('demo.sim.outcome'),null);assert.ok(await ev('demo.sim.stats.clearancesCompleted')>0);
 assert.ok(await ev('demo.session.clearances')>0);checks.continues_after_clearance=true;
 await ev('document.getElementById("autoNext").checked=true;document.getElementById("scenario").value="shot";document.getElementById("scenario").dispatchEvent(new Event("change"));document.getElementById("play").click()');
 const oldSeed=await ev('demo.sim.seed');
 for(let i=0;i<110;i++){if(await ev('demo.session.round===2'))break;await wait(50);}
 assert.equal(await ev('demo.session.round'),2);assert.equal(await ev('demo.sim.scenario'),'random');assert.notEqual(await ev('demo.sim.seed'),oldSeed);
 assert.equal(await ev('demo.session.goals'),1);assert.equal(await ev('demo.running'),true);checks.automatic_next_random_round=true;
 await ev('document.getElementById("play").click()');
 await ev('document.getElementById("scenario").value="lane";document.getElementById("scenario").dispatchEvent(new Event("change"));for(let i=0;i<600;i++)demo.sim.step();demo.update();demo.draw()');
 await ev('document.getElementById("language").click()');
 await wait(120);const screen=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(here,'desktop.png'),Buffer.from(screen.data,'base64'));
 await ev('document.getElementById("language").click()');await wait(50);const chinese=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(here,'desktop-zh.png'),Buffer.from(chinese.data,'base64'));
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(120);
 const widths=await ev('({scroll:document.documentElement.scrollWidth,viewport:innerWidth})');assert.ok(widths.scroll<=widths.viewport);checks.mobile_no_overflow=widths;
 const mobile=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(here,'mobile.png'),Buffer.from(mobile.data,'base64'));
 const network=requests.filter(u=>/^https?:/.test(u));assert.equal(network.length,0);checks.external_network_requests=network;
 assert.equal(errors.length,0);checks.javascript_errors=errors;
 fs.writeFileSync(path.join(here,'browser-check.json'),JSON.stringify(checks,null,2)+'\n');console.log(JSON.stringify(checks,null,2));
}finally{socket.close();}
