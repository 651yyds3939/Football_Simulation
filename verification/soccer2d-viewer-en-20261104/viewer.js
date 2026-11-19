
'use strict';
(()=>{
 const data=JSON.parse(document.getElementById('scene-data').textContent);
 const frames=data.frames, names=data.names, g=data.geometry;
 if(!frames.length)throw new Error('The scene contains no frames');
 const el=id=>document.getElementById(id), canvas=el('pitch'),ctx=canvas.getContext('2d');
 let index=0,time=frames[0].t,playing=false,selected=names.indexOf('RedForwardA'),lastWall=null;
 let scale=1,ox=0,oy=0,cssW=1120,cssH=820;
 const role=n=>n.endsWith('Goalkeeper')?'G':n.endsWith('Defender')?'D':n.endsWith('ForwardA')?'A':'B';
 const short=n=>(n.startsWith('Red')?'R-':'B-')+role(n);
 const colour=n=>n.startsWith('Red')?'#e2545c':'#4689dc';
 const roles={G:'Goalkeeper',D:'Defender',A:'Forward A',B:'Forward B'};
 const behaviours={FORMATION:'Formation',INTERCEPT:'Intercept',DEFEND:'Defend',CLEAR:'Clear',RESTART:'Restart',SUPPORT:'Support',DRIBBLE:'Dribble',GUARD:'Guard',SHOOT:'Shoot',PASS:'Pass',WAIT:'Wait',PENALIZED:'Penalised',RECEIVE:'Receive'};
 const actions={walk:'Walk',stand:'Stand',back:'Backwards',step_left:'Step left',step_right:'Step right',shoot:'Shoot',pass:'Pass'};
 const phases={INITIAL:'Initial',READY:'Ready',SET:'Set',PLAYING:'Playing',STOPPED:'Stopped',PREPARE:'Restart setup',HALFTIME:'Halftime',FINISHED:'Finished'};
 function clock(s){s=Math.max(0,s);return String(Math.floor(s/60)).padStart(2,'0')+':'+(s%60).toFixed(1).padStart(4,'0');}
 function actionText(p){return p[5]?(actions[p[5]]||p[5])+' wind-up '+p[6].toFixed(1)+'s':(actions[p[4]]||p[4]||'Waiting');}
 function at(t){let lo=0,hi=frames.length;while(lo<hi){const mid=(lo+hi)>>1;if(frames[mid].t<=t)lo=mid+1;else hi=mid;}return Math.max(0,lo-1);}
 function xy(x,y){return [ox+x*scale,oy-y*scale];}
 function line(x1,y1,x2,y2){const a=xy(x1,y1),b=xy(x2,y2);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
 function rect(x,y,w,h){const p=xy(x,y+h);ctx.strokeRect(p[0],p[1],w*scale,h*scale);}
 function circle(x,y,r,fill,stroke){const p=xy(x,y);ctx.beginPath();ctx.arc(p[0],p[1],r*scale,0,Math.PI*2);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.stroke();}}
 function draw(){
  const f=frames[index],w=cssW,h=cssH;ctx.clearRect(0,0,w,h);scale=Math.min(w/(g.PITCH_LENGTH+2*g.BORDER_WIDTH+.2),h/(g.PITCH_WIDTH+2*g.BORDER_WIDTH+.2));ox=w/2;oy=h/2;
  const grad=ctx.createLinearGradient(0,0,w,h);grad.addColorStop(0,'#174c3e');grad.addColorStop(1,'#10392f');ctx.fillStyle=grad;ctx.fillRect(0,0,w,h);
  const tl=xy(-g.PITCH_LENGTH/2,g.PITCH_WIDTH/2);ctx.fillStyle='#277153';ctx.fillRect(tl[0],tl[1],g.PITCH_LENGTH*scale,g.PITCH_WIDTH*scale);
  for(let j=0;j<12;j++){if(j%2){ctx.fillStyle='rgba(255,255,255,.032)';ctx.fillRect(tl[0]+j*g.PITCH_LENGTH*scale/12,tl[1],g.PITCH_LENGTH*scale/12,g.PITCH_WIDTH*scale);}}
  ctx.lineWidth=g.LINE_WIDTH*scale;ctx.strokeStyle='rgba(234,248,232,.83)';rect(-g.PITCH_LENGTH/2,-g.PITCH_WIDTH/2,g.PITCH_LENGTH,g.PITCH_WIDTH);line(0,-g.PITCH_WIDTH/2,0,g.PITCH_WIDTH/2);circle(0,0,g.CENTRE_CIRCLE_DIAMETER/2,null,'rgba(234,248,232,.83)');circle(0,0,.035,'#ebf4dc');
  for(const sign of [-1,1]){
   const goalLine=sign*g.PITCH_LENGTH/2;ctx.strokeStyle='rgba(234,248,232,.83)';
   rect(sign<0?goalLine:goalLine-g.PENALTY_AREA_LENGTH,-g.PENALTY_AREA_WIDTH/2,g.PENALTY_AREA_LENGTH,g.PENALTY_AREA_WIDTH);
   rect(sign<0?goalLine:goalLine-g.GOAL_AREA_LENGTH,-g.GOAL_AREA_WIDTH/2,g.GOAL_AREA_LENGTH,g.GOAL_AREA_WIDTH);
   circle(goalLine-sign*g.PENALTY_MARK_DISTANCE,0,.035,'#ebf4dc');
   const gx=sign<0?goalLine-g.GOAL_DEPTH:goalLine,net=xy(gx,g.GOAL_WIDTH/2);
   ctx.fillStyle='rgba(221,240,230,.09)';ctx.fillRect(net[0],net[1],g.GOAL_DEPTH*scale,g.GOAL_WIDTH*scale);ctx.lineWidth=Math.max(1,.012*scale);ctx.strokeStyle='rgba(224,242,231,.27)';
   for(let u=.1;u<g.GOAL_DEPTH;u+=.1)line(gx+u,-g.GOAL_WIDTH/2,gx+u,g.GOAL_WIDTH/2);
   for(let v=-g.GOAL_WIDTH/2+.13;v<g.GOAL_WIDTH/2;v+=.13)line(gx,v,gx+g.GOAL_DEPTH,v);
   ctx.lineWidth=.035*scale;ctx.strokeStyle='#daebe1';rect(gx,-g.GOAL_WIDTH/2,g.GOAL_DEPTH,g.GOAL_WIDTH);
  }
  ctx.font='600 '+Math.max(9,scale*.12)+'px system-ui';ctx.fillStyle='rgba(220,239,225,.5)';ctx.textAlign='center';ctx.fillText('9 m',ox,tl[1]-.35*scale);ctx.save();ctx.translate(tl[0]-.42*scale,oy);ctx.rotate(-Math.PI/2);ctx.fillText('6 m',0,0);ctx.restore();
  if(el('trails').checked){ctx.lineWidth=Math.max(1.5,.025*scale);ctx.strokeStyle='rgba(243,202,102,.7)';ctx.beginPath();let connected=false;for(let j=Math.max(0,index-50);j<=index;j++){const a=frames[j],previous=frames[j-1];const reset=!previous||a.match.half!==previous.match.half||a.match.phase!=='PLAYING'||previous.match.phase!=='PLAYING'||data.events.some(e=>['place_ball','fixture_formation'].includes(e.event)&&e.time>previous.t&&e.time<=a.t);const p=xy(...a.ball);if(!connected||reset)ctx.moveTo(...p);else ctx.lineTo(...p);connected=true;}ctx.stroke();}
  if(f.pass){const from=names.indexOf(f.pass.sender),to=names.indexOf(f.pass.receiver);if(from>=0&&to>=0){ctx.setLineDash([5,6]);ctx.strokeStyle='#e5d99d';ctx.lineWidth=1.5;line(f.players[from][0],f.players[from][1],f.players[to][0],f.players[to][1]);ctx.setLineDash([]);}}
  f.players.forEach((p,i)=>{
   const [x,y,yaw]=p,n=names[i],pos=xy(x,y),r=data.model.robot_radius*scale;
   if(i===selected){ctx.lineWidth=2;circle(x,y,data.model.robot_radius+.075,null,'#f5d686');}
   if(n===f.touch){ctx.lineWidth=1;circle(x,y,data.model.robot_radius+.035,null,'#f1c164');}
   ctx.lineWidth=1.5;circle(x,y,data.model.robot_radius,colour(n),'rgba(255,255,255,.8)');
   ctx.strokeStyle='#eaf7ef';ctx.lineWidth=2;line(x+Math.cos(yaw)*.08,y+Math.sin(yaw)*.08,x+Math.cos(yaw)*.245,y+Math.sin(yaw)*.245);
   ctx.font='800 '+Math.max(8,r*.95)+'px system-ui';ctx.fillStyle='white';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(role(n),pos[0],pos[1]+.5);
   if(el('labels').checked){ctx.font='650 '+Math.max(9,scale*.13)+'px system-ui';ctx.fillStyle='#f0f7ed';ctx.fillText(short(n),pos[0],pos[1]-r-10);}
  });
  ctx.lineWidth=2;circle(...f.ball,g.BALL_RADIUS+.05,null,'#eac15d');ctx.lineWidth=1;circle(...f.ball,g.BALL_RADIUS,'#fff8e5','#142d2b');circle(...f.ball,g.BALL_RADIUS*.32,'#273d37');
  ctx.textBaseline='alphabetic';
 }
 const cards=names.map((n,i)=>{const b=document.createElement('button');b.className='player';b.setAttribute('aria-label',n);const token=document.createElement('span');token.className='token';token.style.background=colour(n);token.textContent=short(n);const info=document.createElement('span'),name=document.createElement('div'),action=document.createElement('div'),behaviour=document.createElement('span');name.className='pname';name.textContent=(n.startsWith('Red')?'Red ':'Blue ')+roles[role(n)];action.className='paction';behaviour.className='pbehaviour';info.append(name,action);b.append(token,info,behaviour);b.onclick=()=>{selected=i;refresh();};el('roster').append(b);return {b,action,behaviour};});
 function eventText(e){if(e.event==='phase')return phases[e.phase]||e.phase;if(e.event==='fixture_formation')return 'Half '+e.half+' · Formation fixture';if(e.event==='restart')return (e.team==='RED'?'Red':'Blue')+' restart · '+e.kind;if(e.event==='goal')return 'Goal · '+(e.team||'');if(e.event==='kick_start')return short(e.robot)+' starts '+(actions[e.action]||e.action);if(e.event==='kick_contact')return short(e.robot)+' model kick contact';if(e.event==='pass_result')return e.completed?'Intended receiver touched ball':'Another player touched the pass';return e.event;}
 const important=data.events.filter(e=>['phase','fixture_formation','restart','goal','kick_start','kick_contact','pass_result'].includes(e.event));
 function refresh(){
  const f=frames[index];el('redScore').textContent=f.match.score[0];el('blueScore').textContent=f.match.score[1];el('phase').textContent=(phases[f.match.phase]||f.match.phase);el('clock').textContent=clock(f.t);el('half').textContent=(f.match.half===1?'First':'Second')+' half · Remaining '+clock(f.match.remaining);el('seek').value=index;el('progress').textContent=clock(f.t)+' / '+clock(frames.at(-1).t);el('attackDirection').textContent=f.match.red_direction===1?'RED →　← BLUE':'RED ←　→ BLUE';
  cards.forEach((c,i)=>{const p=f.players[i];c.b.classList.toggle('selected',i===selected);c.b.setAttribute('aria-pressed',String(i===selected));c.action.textContent=actionText(p);c.behaviour.textContent=behaviours[p[3]]||p[3]||'Initial';});
  const p=f.players[selected];el('selectedName').textContent=names[selected];el('position').textContent=p[0].toFixed(2)+' / '+p[1].toFixed(2);el('heading').textContent=(p[2]*180/Math.PI).toFixed(1)+'°';el('distance').textContent=Math.hypot(p[0]-f.ball[0],p[1]-f.ball[1]).toFixed(2);el('action').textContent=actionText(p);el('ballInfo').textContent='Ball ('+f.ball.map(v=>v.toFixed(2)).join(', ')+') m · Speed '+Math.hypot(...f.velocity).toFixed(2)+' m/s';
  const list=el('events');list.replaceChildren();const recent=important.filter(e=>e.time<=f.t+1e-7).slice(-8).reverse();if(!recent.length){const p=document.createElement('div');p.className='empty';p.textContent='Waiting for match events';list.append(p);}for(const event of recent){const b=document.createElement('button');b.className='event';const t=document.createElement('time'),label=document.createElement('span');t.textContent=clock(event.time);label.textContent=eventText(event);b.append(t,label);b.onclick=()=>seek(at(event.time));list.append(b);}draw();
 }
 function toggle(force){playing=force===undefined?!playing:force;el('play').textContent=playing?'Ⅱ Pause':'▶ Play';el('play').setAttribute('aria-pressed',String(playing));lastWall=null;}
 function seek(i){toggle(false);index=Math.max(0,Math.min(frames.length-1,i));time=frames[index].t;refresh();}
 el('play').onclick=()=>{if(index===frames.length-1)seek(0);toggle();};el('restart').onclick=()=>seek(0);el('previous').onclick=()=>seek(index-1);el('next').onclick=()=>seek(index+1);el('seek').oninput=e=>seek(Number(e.target.value));el('trails').onchange=draw;el('labels').onchange=draw;
 document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();el('play').click();}if(e.code==='ArrowLeft'){e.preventDefault();seek(index-1);}if(e.code==='ArrowRight'){e.preventDefault();seek(index+1);}if(e.code==='Home'){e.preventDefault();seek(0);}if(e.code==='End'){e.preventDefault();seek(frames.length-1);}});
 canvas.addEventListener('click',e=>{const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left-ox)/scale,y=-(e.clientY-r.top-oy)/scale;let hit=-1,best=.35;frames[index].players.forEach((p,i)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<best){hit=i;best=d;}});if(hit>=0){selected=hit;refresh();}});
 function resize(){const r=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;cssW=r.width;cssH=r.height;canvas.width=Math.round(cssW*dpr);canvas.height=Math.round(cssH*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);draw();}
 new ResizeObserver(resize).observe(canvas);
 function tick(now){if(playing){if(lastWall!==null){time+=Math.min((now-lastWall)/1000,.25)*Number(el('speed').value);if(time>=frames.at(-1).t){if(el('loop').checked)time=frames[0].t;else{time=frames.at(-1).t;toggle(false);}}const next=at(time);if(next!==index){index=next;refresh();}}lastWall=now;}requestAnimationFrame(tick);}
 el('seek').max=frames.length-1;el('mode').textContent=data.candidate==='baseline'?'Baseline vs baseline · SEED '+data.seed:'Candidate '+data.candidateTeam+' · SEED '+data.seed;el('redMode').textContent=data.candidate!=='baseline'&&data.candidateTeam==='RED'?'Candidate':'Baseline';el('blueMode').textContent=data.candidate!=='baseline'&&data.candidateTeam==='BLUE'?'Candidate':'Baseline';el('recordInfo').textContent=frames.length+' frames · '+data.model.dt.toFixed(1)+' s sampling · Recorded replay';el('pitchSpecs').textContent=g.PITCH_LENGTH+' × '+g.PITCH_WIDTH+' m · Goal width '+g.GOAL_WIDTH+' m · Ball diameter '+(g.BALL_RADIUS*2).toFixed(2)+' m';resize();refresh();requestAnimationFrame(tick);
})();
