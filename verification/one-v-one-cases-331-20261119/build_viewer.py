from pathlib import Path
import json,re
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
records=json.loads((H/'records.json').read_text());summaries=json.loads((H/'summary.json').read_text())['cases']
for record,summary in zip(records,summaries):
 if record['kind']=='contact_breakthrough':mark=summary['frontal_contact_at']
 elif record['kind']=='tackle_counter_goal':mark=summary['exclusive_blue_foot_at']
 else:mark=next(f['t'] for f in record['frames'] if f['ball']['x']>f['defender']['x']+.8 and f['lastTouch']=='attacker')
 record['keyMoment']=mark
options=''.join(f'<option value="{i}">{i+1}</option>' for i in range(7))
s=(ROOT/'verification/simple-html-20261112/template.html').read_text();s=s.replace('<title>Football Lab · 1 vs 1</title>','<title>Football Lab · 1v1 · 3:3:1 cases</title>')
s=re.sub(r'<select id="scene".*?</select>',f'<select id="scene" aria-label="Recorded example">{options}</select>',s,count=1,flags=re.S)
s=s.replace('   <label><span data-i="speed">', '   <button id="moment" type="button" data-i="moment">Key moment</button><label><input id="autoNext" type="checkbox" checked><span data-i="autoNext">Auto next</span></label>\n   <label><span data-i="speed">')
s=s.replace('<div class="layout">','<p id="caseTitle" style="font-weight:750;margin:0 0 12px"></p><div class="layout">',1)
s=s.replace('const pendingNextAt=null;', 'let pendingNextAt=null;')
anchor='const tr=key=>';i=s.index(anchor);s=s[:i]+'''Object.assign(translations.en,{title:'1v1 · Three kinds of contest',intro:'Seven recorded cases · 3 contact breakthroughs / 3 tackles and counter goals / 1 failed recovery.',note:'Selected examples in a 3:3:1 ratio by case count, not a success-rate estimate. Playback does not change physical movement rates.',contact_breakthrough:'Contact breakthrough and goal',tackle_counter_goal:'Tackle and counter goal',failed_recovery:'Defender cannot catch up',case:'Case',moment:'Key moment',autoNext:'Auto next',keyLabel:'Key moment',next:'Next case in 2 s',allDone:'All seven selected cases finished.'});
Object.assign(translations.zh,{title:'1v1 · 三类攻防案例',intro:'七个真实计算回放：3次接触后突破进球 / 3次抢断反进球 / 1次回追不及。',note:'3:3:1按案例数量选取，不代表总体成功率。倍速只改变观看时间，不提高机器人速度。',contact_breakthrough:'正面接触后突破进球',tackle_counter_goal:'抢断后反进球',failed_recovery:'防守回追不及',case:'案例',moment:'关键时刻',autoNext:'自动下一例',keyLabel:'关键时刻',next:'2秒后播放下一例',allDone:'七个选定案例已全部播放完毕。'});
'''+s[i:]
s=s.replace(" $('clock').textContent=clock(sim.t);", " $('caseTitle').textContent=tr('case')+' '+(selected+1)+'/7 · '+tr(records[selected].kind);$('clock').textContent=clock(sim.t);")
s=s.replace("$('result').textContent=tr(sim.outcome||'live');", "$('result').textContent=tr(sim.outcome||'live')+(sim.outcome&&$('autoNext').checked&&selected<6?' · '+tr('next'):'');")
s=s.replace("function select(value){selected=value;", "function select(value){pendingNextAt=null;selected=value;$('scene').value=String(value);")
s=s.replace("$('language').textContent=lang==='en'?'中文':'English';update();draw();", "$('language').textContent=lang==='en'?'中文':'English';Array.from($('scene').options).forEach((o,i)=>o.textContent=(i+1)+' · '+tr(records[i].kind));update();draw();")
s=s.replace("if(time>=duration()){running=false;update();}", "if(time>=duration()){running=false;pendingNextAt=$('autoNext').checked&&selected<records.length-1?stamp+2000:null;update();}")
s=s.replace(' requestAnimationFrame(frame);', " if(pendingNextAt!==null&&stamp>=pendingNextAt&&!document.hidden){pendingNextAt=null;if($('autoNext').checked){running=true;select(selected+1);}}\n requestAnimationFrame(frame);",1)
s=s.replace("$('play').onclick=()=>{", "$('play').onclick=()=>{pendingNextAt=null;")
s=s.replace("$('seek').oninput=()=>{running=false;", "$('seek').oninput=()=>{pendingNextAt=null;running=false;")
s=s.replace("$('trail').onchange=draw;", "$('moment').onclick=()=>{pendingNextAt=null;running=false;const t=records[selected].keyMoment;const j=records[selected].frames.findIndex(f=>f.t>=t-1e-8);seek(j);time=sim.t;lastReal=null;};$('autoNext').onchange=()=>{pendingNextAt=null;update();};$('trail').onchange=draw;")
s=s.replace('window.simpleReplay={', '''window.caseVideo={renderAt(n,t,key=false){pendingNextAt=null;running=false;if(selected!==n)select(n);const f=records[n].frames;let j=0;while(j+1<f.length&&f[j+1].t<=t+1e-8)j++;time=t;seek(j);$('phase').textContent=key?tr('keyLabel'):'RECORDED REPLAY · 8×';}};
window.simpleReplay={''')
viewer=(ROOT/'2D_Shared_Policy_2026-11-11/viewer.html').read_text();drawing=viewer[viewer.index("const canvas=$('pitch')"):viewer.index('async function advance(steps)')]
s=s.replace('__DRAWING__',drawing).replace('__RECORDINGS__',json.dumps(records,separators=(',',':'),ensure_ascii=False,allow_nan=False).replace('<','\\u003c'))
assert 'fetch(' not in s and '__DRAWING__' not in s
(ROOT/'Football_1v1_Cases_3-3-1.html').write_text(s,encoding='utf-8');(H/'template.html').write_text(s[:s.index('<script id="recordings"')]+'\n<!-- Recorded data built by build_viewer.py -->\n')
print('Built single-file seven-case replay')
