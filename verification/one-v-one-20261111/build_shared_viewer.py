"""Reuse the drawing/UI shell; deliberately omit every JavaScript decision rule."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'2D_1v1_Demo_2026-11-11/index.html').read_text(encoding='utf-8')
translation = source[source.index('const translations='):source.index('function translate()')]
drawing = source[source.index("const canvas=$('pitch')"):source.index('function frame(stamp)')]
html = re.sub(r'<script id="config".*?</script>', '', source, flags=re.S)
html = re.sub(r'<script id="simulation-core">.*?</script>', '', html, flags=re.S)
html = html.replace('<title>Football Lab · 1 vs 1</title>', '<title>Football Lab · Shared Python policy</title>')
html = html.replace('</style>', '.setting .check input{width:auto}</style>')
html = html.replace('<option value="shot" data-i="shotScene">', '<option value="breakaway" data-i="breakaway">Breakaway response check (fixed)</option><option value="shot" data-i="shotScene">')
html = html.replace('<option value="breakaway"', '<option value="block" data-i="blockScene">Frontal challenge (fixed)</option><option value="breakaway"')
html = html.replace('<option value="16">16×</option>', '<option value="16">16×</option><option value="32">32×</option><option value="64">64×</option>')
html = html.replace('<option value="2" selected>', '<option value="2">').replace('<option value="8">', '<option value="8" selected>')
html = html.replace('<button id="step"', '<button id="batch" data-i="batch">Fast test ×20</button><button id="replay" data-i="replay">Export HTML replay</button><button id="step"')
html = html.replace('<div class="setting"><label data-i="display">',
    '<div class="setting"><label for="profile" data-i="profileLabel">Webots execution profile</label><select id="profile"><option value="guarded">guarded</option><option value="legacy">legacy</option></select></div><div class="setting"><label for="seconds" data-i="duration">Round duration (s)</label><input id="seconds" type="number" min="5" max="1800" value="180"></div><div class="setting"><label data-i="display">')
html = html.replace('<footer class="footer">', '<div id="sharedSource" class="notice"></div><footer class="footer">')
html = html.replace('</main>', '<dialog id="batchDialog"><h2 data-i="batchResults">Batch results</h2><pre id="batchResult" style="white-space:pre-wrap;max-width:80vw"></pre><button id="saveBatch" data-i="saveBatch">Save JSON</button> <button id="closeBatch" data-i="close">Close</button></dialog></main>')

script = r"""
/*__REPLAY_DATA__*/
(() => {
const $=id=>document.getElementById(id),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
let sim=null,p=null,meta=null,trail=[],running=false,lang='en',accumulator=0,lastReal=null,dragging=null;
let session={round:1,goals:0,clearances:0},observedClears=0,countedGoal=false,pendingNextAt=null;
let inflight=false,busy=false,lastBatch=null,replayIndex=0,replayTime=0;
const offline=!!window.PYTHON_REPLAY;
__TRANSLATIONS__
Object.assign(translations.en,{INITIAL:'Ready',WAIT:'Wait',profileLabel:'Webots execution profile'});
Object.assign(translations.zh,{INITIAL:'就绪',WAIT:'等待',profileLabel:'Webots 执行配置'});
Object.assign(translations.en,{DUEL_ESCAPE:'Create space',DUEL_STEP_ASIDE:'Step aside to break the close duel',DUEL_SPACE_CREATED:'Space created',duelNotice:'Crowded ball: briefly stepping aside before retrying.'});
Object.assign(translations.zh,{DUEL_ESCAPE:'遇堵让位',DUEL_STEP_ASIDE:'短暂侧移，尝试解除贴身僵持',DUEL_SPACE_CREATED:'已让出空间',duelNotice:'足球被双方夹住：正在短暂侧移，再重新争球。'});
Object.assign(translations.en,{RECOVER_DEFENCE:'Recover goal-side',RECOVERY_BACKTRACK:'Backtrack without a half-turn',RECOVERY_ADVANCE:'Move to the goal-side interception point',RECOVERY_CHANGE_HEADING:'Align the nearer forward/backward axis',recoveryNotice:'Defender beaten: recovering goal-side before attempting a clearance.',breakaway:'Breakaway response check (fixed)'});
Object.assign(translations.zh,{RECOVER_DEFENCE:'回防球门侧',RECOVERY_BACKTRACK:'直接倒退回撤，避免先转半圈',RECOVERY_ADVANCE:'移动到球门侧拦截点',RECOVERY_CHANGE_HEADING:'调整到较近的前进或后退方向',recoveryNotice:'防守球员已被突破：先回到球门侧，再尝试解围。',breakaway:'斜向来球拦截（固定）'});
Object.assign(translations.en,{breakaway:'Diagonal interception (fixed)',shotScene:'Near-goal defended attack (fixed)',DEFENSIVE_INTERCEPT:'Predictive interception',INTERCEPT_MOVE_EARLY:'Move early to the predicted ball lane',INTERCEPT_FACE_INCOMING:'Face the incoming ball',INTERCEPT_HOLD_LANE:'Cover the predicted lane',interceptNotice:'Predicting the ball lane and positioning before the attacker arrives.'});
Object.assign(translations.zh,{shotScene:'门前攻防（固定）',DEFENSIVE_INTERCEPT:'预判拦截',INTERCEPT_MOVE_EARLY:'提前移动到预测球路',INTERCEPT_FACE_INCOMING:'面向来球方向',INTERCEPT_HOLD_LANE:'覆盖预测球路',interceptNotice:'根据球路和动作耗时，提前选择拦截位置。'});
Object.assign(translations.en,{CHALLENGE:'Challenge the ball',CHALLENGE_POKE_BALL:'Ball within foot reach: attempt a poke',CHALLENGE_SHADOW_LANE:'Slide to cover the ball lane',CHALLENGE_CLOSE_LANE:'Close the blocking distance',CHALLENGE_FACE_BALL:'Approach facing the ball',CHALLENGE_EXPOSED_BALL:'Approach the exposed ball',CHALLENGE_CREATE_SPACE:'Restore room at the foot',challengeNotice:'Defender covering the lane and challenging the ball.',blockScene:'Frontal challenge (fixed)'});
Object.assign(translations.zh,{CHALLENGE:'封堵与断球',CHALLENGE_POKE_BALL:'足球已在脚前：尝试捅球',CHALLENGE_SHADOW_LANE:'侧移覆盖球路',CHALLENGE_CLOSE_LANE:'缩短封堵距离',CHALLENGE_FACE_BALL:'面向足球接近',CHALLENGE_EXPOSED_BALL:'接近暴露的足球',CHALLENGE_CREATE_SPACE:'恢复脚前空间',challengeNotice:'防守球员正在覆盖球路，寻找断球机会。',blockScene:'正面封堵与断球（固定）'});
Object.assign(translations.en,{local:'SHARED PYTHON POLICY · 2D',title:'One policy. Two test environments.',intro:'Webots and this 2D model call the same Python decision and navigation modules.',batch:'Fast test ×20',replay:'Export HTML replay',duration:'Round duration (s)',batchResults:'Batch test results',saveBatch:'Save JSON',close:'Close',source:'Decision source',workspace:'original workspace',snapshot:'packaged snapshot',offline:'OFFLINE REPLAY · calculated by the Python policy',live:'Shared Python policy running',setupNote:'Live decisions run in Python. Playback changes simulation steps per real second; motion parameters stay unchanged.',calculating:'Calculating 20 runs with the shared Python policy…',error:'Request failed',CLEARED_GOAL:'Blue cleared into the left goal.',body:'Behaviour / motion',replayNotice:'Offline replay: use the Python server to change initial conditions or policies.'});
Object.assign(translations.zh,{local:'共用 PYTHON 决策 · 二维模型',title:'同一套决策，两种测试环境。',intro:'Webots 与当前二维模型调用相同的 Python 决策和导航模块。',batch:'快速测试 20 次',replay:'导出 HTML 回放',duration:'每轮仿真时长（秒）',batchResults:'批量测试结果',saveBatch:'保存 JSON',close:'关闭',source:'决策代码来源',workspace:'原工作区',snapshot:'打包快照',offline:'离线回放 · 由共用 Python 决策计算',live:'共用 Python 决策运行中',setupNote:'实时决策由 Python 计算。倍速改变每秒计算的仿真步数，不改变运动参数。',calculating:'正在用共用 Python 决策快速计算 20 次…',error:'请求失败',CLEARED_GOAL:'蓝方将球解围至左侧球门。',body:'行为 / 动作',replayNotice:'当前是离线回放；修改初始条件或策略需要启动 Python 服务。'});
function translate(){document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-i]').forEach(el=>el.textContent=tr(el.dataset.i));$('language').textContent=lang==='en'?'中文':'English';update();}
async function api(path,data){const response=await fetch(path,data===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const value=await response.json();if(!response.ok)throw new Error(value.error||response.status);return value;}
function failure(error){running=false;pendingNextAt=null;inflight=false;busy=false;$('notice').textContent=tr('error')+': '+error.message;update();}
function account(){session.clearances+=Math.max(0,sim.stats.clearancesCompleted-observedClears);observedClears=sim.stats.clearancesCompleted;if(sim.outcome==='GOAL'&&!countedGoal){session.goals++;countedGoal=true;}}
function adopt(envelope,clearTrail=false){meta=envelope;p=envelope.parameters;sim={...envelope.state};if(clearTrail)trail=[];trail.push({x:sim.ball.x,y:sim.ball.y});if(trail.length>2000)trail.shift();sim.trail=trail;account();update();draw();}
async function reset(keepSession=false){
 if(inflight||busy)return;
 running=false;pendingNextAt=null;accumulator=0;observedClears=0;countedGoal=false;
 if(!keepSession)session={round:1,goals:0,clearances:0};
 if(offline){replayIndex=0;replayTime=0;adopt({...meta,state:window.PYTHON_REPLAY.frames[0]},true);return;}
 inflight=true;try{const value=await api('/api/new',{seed:Number($('seed').value),scenario:$('scenario').value,seconds:Number($('seconds').value),locomotion:$('profile').value,finishing_aim:'centre'});adopt(value,true);}finally{inflight=false;update();}
}
async function newSetup(resume=false){if(offline||inflight||busy)return;session.round++;$('scenario').value='random';$('seed').value=crypto.getRandomValues(new Uint32Array(1))[0];await reset(true);running=resume;update();}
function update(){
 if(!sim)return;const total=Math.round(sim.t*10)/10;
 $('clock').textContent=String(Math.floor(total/60)).padStart(2,'0')+':'+(total%60).toFixed(1).padStart(4,'0');
 $('phase').textContent=(offline?'REPLAY · ':'')+tr(sim.outcome?'FINISHED':running?'RUNNING':'PAUSED')+' · '+tr('round')+' '+session.round;
 $('play').textContent=tr(running?'pause':'play');$('play').disabled=busy||(!offline&&!!sim.outcome);$('step').disabled=running||busy||!!sim.outcome;
 for(const role of ['attacker','defender']){const player=sim[role];$(role+'State').textContent=tr(player.state);$(role+'Reason').textContent=player.action+' · '+tr(player.stage);$(role+'Progress').style.width=player.kick?clamp((1-(player.kick.end-sim.t)/player.kick.duration)*100,0,100)+'%':'0';}
 $('ballPosition').textContent=sim.ball.x.toFixed(2)+', '+sim.ball.y.toFixed(2);$('ballSpeed').textContent=Math.hypot(sim.ball.vx,sim.ball.vy).toFixed(3)+' m/s';$('touch').textContent=sim.lastTouch?tr(sim.lastTouch+'Short'):'—';$('contacts').textContent=sim.stats.shotContacts+' / '+sim.stats.clearContacts;$('sessionTotals').textContent=session.goals+' / '+session.clearances;
 $('status').textContent=tr(sim.outcome||(!sim.t?'READY':sim.stats.clearancesCompleted?'clearLive':'live'));
 const escaping=!sim.outcome&&[sim.attacker,sim.defender].some(player=>player.state==='DUEL_ESCAPE');
 const recovering=!sim.outcome&&sim.defender.state==='RECOVER_DEFENCE';
 const challenging=!sim.outcome&&sim.defender.state==='CHALLENGE';
 if(escaping)$('status').textContent=tr('duelNotice');
 else if(recovering)$('status').textContent=tr('recoveryNotice');
 else if(challenging)$('status').textContent=tr('challengeNotice');
 else if(!sim.outcome&&sim.defender.state==='DEFENSIVE_INTERCEPT')$('status').textContent=tr('interceptNotice');
 $('result').style.background=escaping||recovering?'#fff3d6':'';
 if(pendingNextAt!==null)$('status').textContent+=' '+tr('nextRound')+' '+Math.max(1,Math.ceil((pendingNextAt-performance.now())/1000))+' s';
 const hash=meta.source.sha256['Wenao/controllers/Utils/TeamPolicy.py'].slice(0,12);
 $('sharedSource').textContent=(offline?tr('offline')+' · ':'')+tr('source')+': '+tr(meta.source.kind==='workspace'?'workspace':'snapshot')+' · TeamPolicy.py '+hash+' · Navigation.py · '+meta.profile.locomotion+' / '+meta.profile.finishing_aim;
 if(offline)$('notice').textContent=tr('replayNotice');
 $('newSetup').disabled=offline||inflight||busy;$('batch').disabled=offline||busy||inflight;$('replay').disabled=offline||busy||inflight;
}
__DRAWING__
async function advance(steps){if(inflight||busy||!sim||sim.outcome)return;inflight=true;try{adopt(await api('/api/step',{steps}));if(sim.outcome){running=false;if($('autoNext').checked)pendingNextAt=performance.now()+3000;}}catch(error){failure(error);}finally{inflight=false;update();}}
function offlineSeek(index){const frames=window.PYTHON_REPLAY.frames;replayIndex=clamp(index,0,frames.length-1);adopt({...meta,state:frames[replayIndex]},replayIndex===0);}
function frame(stamp){
 if(lastReal===null)lastReal=stamp;const elapsed=Math.min(.10,(stamp-lastReal)/1000);lastReal=stamp;
 if(running&&!document.hidden&&!busy){
  if(offline){replayTime+=elapsed*Number($('speed').value);const frames=window.PYTHON_REPLAY.frames;let index=replayIndex;while(index+1<frames.length&&frames[index+1].t<=replayTime)index++;if(index!==replayIndex)offlineSeek(index);if(index===frames.length-1)running=false;}
  else if(!inflight){accumulator+=elapsed*Number($('speed').value);const steps=Math.min(2000,Math.floor(accumulator/p.dt));if(steps){accumulator-=steps*p.dt;advance(steps);}}
 }
 if(pendingNextAt!==null&&!inflight&&performance.now()>=pendingNextAt&&!document.hidden){pendingNextAt=null;newSetup(true).catch(failure);}
 update();requestAnimationFrame(frame);
}
function download(data,name,type='application/json'){const blob=new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('play').onclick=()=>{if(offline&&replayIndex===window.PYTHON_REPLAY.frames.length-1){offlineSeek(0);replayTime=0;}running=!running;lastReal=null;update();};
$('reset').onclick=()=>reset().catch(failure);$('newSetup').onclick=()=>newSetup(running||pendingNextAt!==null).catch(failure);
$('step').onclick=()=>{if(offline){offlineSeek(replayIndex+1);replayTime=sim.t;}else advance(5);};
for(const id of ['scenario','seed','seconds','profile'])$(id).onchange=()=>reset().catch(failure);
$('autoNext').onchange=()=>{if(!$('autoNext').checked)pendingNextAt=null;};
$('language').onclick=()=>{lang=lang==='en'?'zh':'en';translate();draw();};
$('export').onclick=async()=>{try{download(offline?window.PYTHON_REPLAY.report:await api('/api/report'),'shared-python-1v1.json');}catch(error){failure(error);}};
$('replay').onclick=async()=>{running=false;busy=true;update();try{const response=await fetch('/api/replay');if(!response.ok)throw new Error('Replay export failed');download(await response.text(),'shared-python-1v1-replay.html','text/html');}catch(error){failure(error);}finally{busy=false;update();}};
$('batch').onclick=async()=>{running=false;busy=true;update();$('notice').textContent=tr('calculating');try{lastBatch=await api('/api/batch',{count:20});$('batchResult').textContent=JSON.stringify({outcomes:lastBatch.outcomes,simulated_seconds:lastBatch.simulated_seconds,wall_seconds:lastBatch.wall_seconds,simulation_speedup:lastBatch.simulated_seconds/lastBatch.wall_seconds,runs:lastBatch.runs.map(r=>({seed:r.seed,result:r.outcome,seconds:r.seconds,shot_contacts:r.stats.shotContacts,clear_contacts:r.stats.clearContacts}))},null,2);$('batchDialog').showModal();$('notice').textContent=tr('setupNote');}catch(error){failure(error);}finally{busy=false;update();}};
$('saveBatch').onclick=()=>download(lastBatch,'shared-policy-batch.json');$('closeBatch').onclick=()=>$('batchDialog').close();
function world(event){const r=canvas.getBoundingClientRect();return {x:(event.clientX-r.left)/r.width*11-5.5,y:4-(event.clientY-r.top)/r.height*8};}
canvas.addEventListener('pointerdown',event=>{if(offline||running||inflight||sim.outcome)return;const w=world(event);let closest=.35;for(const name of ['ball','attacker','defender']){const object=sim[name],d=Math.hypot(w.x-object.x,w.y-object.y);if(d<closest){closest=d;dragging=name;}}if(dragging)canvas.setPointerCapture(event.pointerId);});
canvas.addEventListener('pointerup',event=>{if(!dragging)return;const role=dragging;dragging=null;const w=world(event);if(!running&&!inflight){inflight=true;api('/api/move',{object:role,x:w.x,y:w.y}).then(data=>{adopt(data);$('notice').textContent=tr('setupNote');}).catch(error=>{$('notice').textContent=error.message;}).finally(()=>{inflight=false;update();});}});
canvas.addEventListener('pointercancel',()=>{dragging=null;});
document.addEventListener('visibilitychange',()=>{if(document.hidden){running=false;pendingNextAt=null;accumulator=0;}});
window.sharedView={get state(){return sim;},get meta(){return meta;},get running(){return running;},get session(){return session;},get lastBatch(){return lastBatch;},reset,newSetup};
(async()=>{try{const data=offline?window.PYTHON_REPLAY:await api('/api/state');$('seed').value=data.seed;$('scenario').value=data.scenario;$('seconds').value=data.seconds;$('profile').value=data.profile.locomotion;if(offline){for(const id of ['scenario','seed','seconds','profile','autoNext'])$(id).disabled=true;$('autoNext').checked=false;data.state=data.frames[0];}adopt(data,true);translate();requestAnimationFrame(frame);}catch(error){failure(error);}})();
})();
"""
script = script.replace('__TRANSLATIONS__', translation).replace('__DRAWING__', drawing)
html = re.sub(r'<script id="viewer">.*?</script>', lambda _: '<script id="shared-viewer">'+script+'</script>', html, flags=re.S)
assert 'simulation-core' not in html
assert 'class Simulation' not in html
(ROOT/'2D_Shared_Policy_2026-11-11/viewer.html').write_text(html, encoding='utf-8')
print('Built display-only viewer; no JavaScript policy or physics.')
