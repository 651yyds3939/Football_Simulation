from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
base = root/'2D_Shared_Policy_2026-11-11/backend/tools'
source = (base/'soccer2d_viewer.html').read_text()
replacements = {
    'lang="zh-CN"': 'lang="en"',
    '机器人足球 · 2D 可视化场景': 'Robot Football · 2D Viewer',
    '机器人足球 · 2D 场景': 'Robot Football · 2D Scene',
    '四对四 · 9×6 米场地 · 离散模拟回放': '4 vs 4 · 9 × 6 m pitch · Recorded simulation replay',
    '正在读取场景': 'Loading scene',
    '足球场景和播放控制': 'Football scene and playback controls',
    '二维足球场：红蓝两队、足球、球员朝向和移动轨迹': '2D pitch: red and blue teams, ball, player headings and trails',
    '9 × 6 m · 球门 2.6 m · 足球直径 0.14 m': '9 × 6 m · Goal width 2.6 m · Ball diameter 0.14 m',
    '回到开场': 'Return to the start',
    '上一帧': 'Previous frame',
    '下一帧': 'Next frame',
    '‹ 帧': '‹ Frame',
    '帧 ›': 'Frame ›',
    '回放时间线': 'Replay timeline',
    '空格播放 · ← → 逐帧 · 点击球员查看': 'Space: play/pause · ← →: step · Click a player to inspect',
    '场上球员': 'Players',
    '状态观察': 'Inspector',
    '模型状态': 'Model state',
    '选择球员': 'Select a player',
    'X / Y（米）': 'X / Y (m)',
    '朝向（度）': 'Heading (degrees)',
    '距离足球（米）': 'Distance to ball (m)',
    '当前动作': 'Current action',
    '足球状态': 'Ball state',
    '比赛事件': 'Match events',
    '点击跳转': 'Click to seek',
    'G 守门员 / D 后卫 / A、B 前锋': 'G: goalkeeper / D: defender / A, B: forwards',
    '足球光圈': 'Ball marker',
    '二维记录 · 无需 Webots / ROS / 网络': '2D replay · No Webots, ROS or internet required',
    '这个场景能验证什么？': 'What does this scene show?',
    '展示现有 Python 二维模型实际产生的位置、决策标签、动作选择和比赛事件；播放速度只改变查看速度。': 'Displays positions, decision labels, actions and match events recorded from the current Python 2D model. Playback speed changes viewing speed only.',
    '圆盘运动与接触是简化模型；不模拟 NAO 关节、平衡、跌倒、相机定位和球的飞行。': 'Motion and contact use a simplified disc model. NAO joints, balance, falls, camera localisation and ball flight are not simulated.',
    '朝向与位置是离散记录，画面不在半场摆放或裁判重置之间补画运动。行为标签不是技能成功的证明。': 'Positions and headings are discrete samples. No movement is interpolated across halftime placements or referee resets. A behaviour label does not prove skill success.',
    '默认双方均使用基线；候选策略只有在生成时显式指定才启用。半场阵型摆放属于测试夹具。': 'Both teams use the baseline by default. A candidate policy is enabled only when explicitly selected at generation time. Halftime formation placement is a test fixture.',
    '界面用于观察已生成的比赛，不能拖动球员或改变正在播放的比赛结果。修改策略后重新生成场景。': 'This viewer replays a generated match. Players cannot be dragged, and the recorded outcome cannot be changed. Generate a new scene after modifying a policy.',
    '场景没有帧数据': 'The scene contains no frames',
    "G:'守门员',D:'后卫',A:'前锋 A',B:'前锋 B'": "G:'Goalkeeper',D:'Defender',A:'Forward A',B:'Forward B'",
    "FORMATION:'阵型',INTERCEPT:'拦截',DEFEND:'防守',CLEAR:'解围',RESTART:'重启',SUPPORT:'支援',DRIBBLE:'带球',GUARD:'守门',SHOOT:'射门',PASS:'传球',WAIT:'等待',PENALIZED:'受罚',RECEIVE:'接应'": "FORMATION:'Formation',INTERCEPT:'Intercept',DEFEND:'Defend',CLEAR:'Clear',RESTART:'Restart',SUPPORT:'Support',DRIBBLE:'Dribble',GUARD:'Guard',SHOOT:'Shoot',PASS:'Pass',WAIT:'Wait',PENALIZED:'Penalised',RECEIVE:'Receive'",
    "walk:'前进',stand:'站立',back:'后退',step_left:'左侧移',step_right:'右侧移',shoot:'射门',pass:'传球'": "walk:'Walk',stand:'Stand',back:'Backwards',step_left:'Step left',step_right:'Step right',shoot:'Shoot',pass:'Pass'",
    "INITIAL:'初始',READY:'准备',SET:'就位',PLAYING:'比赛中',STOPPED:'中断',PREPARE:'重启准备',HALFTIME:'半场',FINISHED:'结束'": "INITIAL:'Initial',READY:'Ready',SET:'Set',PLAYING:'Playing',STOPPED:'Stopped',PREPARE:'Restart setup',HALFTIME:'Halftime',FINISHED:'Finished'",
    "+'准备 '+": "+' wind-up '+",
    "'等待'": "'Waiting'",
    "'红队 '": "'Red '",
    "'蓝队 '": "'Blue '",
    "'第 '+e.half+' 半场 · 夹具摆阵'": "'Half '+e.half+' · Formation fixture'",
    "'红队':'蓝队'": "'Red':'Blue'",
    "+'重启 · '+": "+' restart · '+",
    "'进球 · '": "'Goal · '",
    "+' 启动'+": "+' starts '+",
    "' 模型踢球接触'": "' model kick contact'",
    "'指定接球队员触球'": "'Intended receiver touched ball'",
    "'传球后其他球员触球'": "'Another player touched the pass'",
    "(f.match.half===1?'上':'下')+'半场 · 剩余 '": "(f.match.half===1?'First':'Second')+' half · Remaining '",
    "'初始'": "'Initial'",
    "'球 ('": "'Ball ('",
    "') m · 速度 '": "') m · Speed '",
    "'等待开场事件'": "'Waiting for match events'",
    "'Ⅱ 暂停':'▶ 播放'": "'Ⅱ Pause':'▶ Play'",
    "'基线对基线 · SEED '": "'Baseline vs baseline · SEED '",
    "'候选 '": "'Candidate '",
    "?'候选':'基线'": "?'Candidate':'Baseline'",
    "+' 帧 · '+": "+' frames · '+",
    "+' s 采样 · 记录回放'": "+' s sampling · Recorded replay'",
    "+' m · 球门 '+": "+' m · Goal width '+",
    "+' m · 足球直径 '+": "+' m · Ball diameter '+",
    '基线': 'Baseline',
    '上半场': 'First half',
    '▶ 播放': '▶ Play',
    '↺ 重置': '↺ Reset',
    '>速度 <': '>Speed <',
    '>球轨迹<': '>Ball trail<',
    '>球员编号<': '>Player labels<',
    '>循环<': '>Loop<',
    '</i>红队': '</i>Red',
    '</i>蓝队': '</i>Blue',
}
for old in replacements:
    if old not in source:
        raise RuntimeError('Missing translation source: '+old)
translated = source
for old in sorted(replacements, key=len, reverse=True):
    translated = translated.replace(old, replacements[old])
remaining = re.findall(r'[^\n]*[\u4e00-\u9fff][^\n]*', translated)
if remaining:
    raise RuntimeError('Untranslated text: '+'\n'.join(remaining))
translated = translated.replace('.pbehaviour{font-size:10px;', '.pbehaviour{max-width:80px;text-align:right;overflow-wrap:anywhere;font-size:10px;')
translated = translated.replace('.legend{display:flex;gap:12px}', '.legend{display:flex;gap:12px;flex-wrap:wrap}')
translated = translated.replace('.pitchinfo{display:flex;', '.pitchinfo{flex-wrap:wrap;display:flex;')
translated = translated.replace("+' · '+f.match.phase;", ";")
(base/'soccer2d_viewer_en.html').write_text(translated)
print('Created English viewer template:', len(translated), 'characters')
