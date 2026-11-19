import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import {pathToFileURL,fileURLToPath} from 'node:url';import {spawn} from 'node:child_process';import {once} from 'node:events';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../..'),port=fs.readFileSync(process.env.DEMO_BROWSER_PROFILE+'/DevToolsActivePort','utf8').split('\n')[0];const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json(),ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((a,b)=>{ws.onopen=a;ws.onerror=b});let id=0;const pending=new Map(),errors=[],requests=[];ws.onmessage=({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params);if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}};const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))});async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}const delay=ms=>new Promise(r=>setTimeout(r,ms));async function until(expression){for(let i=0;i<120;i++){if(await ev(expression))return;await delay(30)}throw Error('Timeout '+expression)}
let encoder=null;
try{
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1160,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:pathToFileURL(root+'/Football_1v1_Cases_3-3-1.html').href});await until('window.simpleReplay&&simpleReplay.state.t>.1');
 await ev('document.getElementById("play").click()');const records=await ev('simpleReplay.records');assert.equal(records.length,7);assert.deepEqual(records.map(r=>r.kind),['contact_breakthrough','contact_breakthrough','contact_breakthrough','tackle_counter_goal','tackle_counter_goal','tackle_counter_goal','failed_recovery']);assert.equal(await ev('document.getElementById("scene").options.length'),7);
 for(let n=0;n<7;n++){
  const original=JSON.parse(fs.readFileSync(here+'/'+records[n].seed+'.json','utf8'));assert.deepEqual(records[n].frames,JSON.parse(JSON.stringify(original.frames)));
  await ev(`caseVideo.renderAt(${n},${records[n].frames.at(-1).t})`);assert.equal(await ev('simpleReplay.state.outcome'),n>=3&&n<=5?'CLEARED_GOAL':'GOAL');await ev('document.getElementById("moment").click()');assert.ok(Math.abs(await ev('simpleReplay.state.t')-records[n].keyMoment)<1e-6);
 }
 // Check every automatic chapter transition using real browser time; seeking
 // near the end skips viewing, never changes recorded data.
 await ev('document.getElementById("speed").value="32"');
 for(let n=0;n<6;n++){
  await ev(`caseVideo.renderAt(${n},${records[n].frames.at(-1).t-.08});document.getElementById('play').click()`);await until(`simpleReplay.selected===${n+1}`);assert.equal(await ev('simpleReplay.running'),true);
 }
 await ev(`caseVideo.renderAt(6,${records[6].frames.at(-1).t-.08});document.getElementById('play').click()`);await until('simpleReplay.state.outcome!==null');await delay(2100);assert.equal(await ev('simpleReplay.selected'),6);assert.equal(await ev('simpleReplay.running'),false);
 await ev('document.getElementById("language").click()');assert.equal(await ev('document.documentElement.lang'),'zh-CN');assert.ok(await ev('document.getElementById("caseTitle").textContent.includes("回追")'));await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await delay(100);assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth'));
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1160,deviceScaleFactor:1,mobile:false});await ev('document.getElementById("language").click();document.getElementById("autoNext").checked=false');
 const fps=20,speed=8;let count=0;const stderr=fs.createWriteStream(here+'/ffmpeg.log');encoder=spawn('ffmpeg',['-y','-hide_banner','-loglevel','warning','-f','image2pipe','-vcodec','mjpeg','-framerate',String(fps),'-i','pipe:0','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',root+'/Football_1v1_Cases_3-3-1.mp4'],{stdio:['pipe','ignore','pipe']});encoder.stderr.pipe(stderr);
 async function put(buffer,repeat=1){for(let i=0;i<repeat;i++){if(!encoder.stdin.write(buffer))await once(encoder.stdin,'drain');count++}}
 async function capture(n,t,key=false){await ev(`caseVideo.renderAt(${n},${t},${key})`);const shot=await send('Page.captureScreenshot',{format:'jpeg',quality:80});return Buffer.from(shot.data,'base64')}
 const chapters=[];
 for(let n=0;n<7;n++){
  const end=records[n].frames.at(-1).t,key=records[n].keyMoment;let held=false;const first=count;
  for(let step=0;step<Math.ceil(end/speed*fps);step++){
   const t=step/fps*speed;
   if(!held&&t>=key){await put(await capture(n,key,true),fps);held=true}
   await put(await capture(n,t));
  }
  const final=await capture(n,end);await put(final,fps*2);chapters.push({case:n+1,kind:records[n].kind,seed:records[n].seed,start_seconds:first/fps,end_seconds:count/fps,simulated_seconds:end,key_moment:key});console.log('ENCODED_CASE',n+1,'frames',count);
 }
 encoder.stdin.end();const [code]=await once(encoder,'close');assert.equal(code,0);assert.equal(errors.length,0);assert.equal(requests.filter(u=>/^https?:/.test(u)).length,0);fs.writeFileSync(here+'/browser-video-check.json',JSON.stringify({cases:7,ratio:'3:3:1',all_original_frames_preserved:true,all_six_automatic_transitions:true,final_chapter_stops:true,seven_key_moments:true,bilingual:true,mobile_no_overflow:true,no_external_requests:true,errors,video:{fps,playback_speed:speed,frames:count,seconds:count/fps,chapters}},null,2));
}finally{if(encoder&&encoder.exitCode===null)encoder.kill();ws.close()}
