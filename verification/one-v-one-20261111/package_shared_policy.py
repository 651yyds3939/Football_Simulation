"""Package a versioned policy snapshot and a Python-computed example replay."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT/'2D_Shared_Policy_2026-11-11'
REPO = DEMO/'backend'
files = ['tools/soccer2d.py']+['Wenao/controllers/Utils/'+name+'.py' for name in (
    '__init__', 'TeamPolicy', 'Navigation', 'DefensivePlan', 'PolicyProfile', 'CourseSpecs', 'MatchEngine', 'ProcessSupervisor')]
hashes = {}
for relative in files:
    target = DEMO/'backend'/relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if (REPO/relative).resolve() != target.resolve():
        shutil.copy2(REPO/relative, target)
    hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('shared_demo_export', DEMO/'server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
scene = module.SharedScene(seed=347, scenario='random', seconds=180)
(DEMO/'example_replay.html').write_text(module.replay_html(scene), encoding='utf-8')
defence = module.SharedScene(seed=355, scenario='random', seconds=180)
(DEMO/'defence_replay.html').write_text(module.replay_html(defence), encoding='utf-8')
manifest = {'description': 'Original Python decision/navigation source snapshot plus a display-only browser client',
            'backend_source_sha256': hashes,
            'source_preference': 'Independent 2D backend snapshot; no automatic import from the sibling 3D project',
            'replay': 'example_replay.html is an offline random-layout recording, seed 347, computed by the same Python modules',
            'defence_replay': 'defence_replay.html is an offline predictive-defence example, random layout seed 355, not a general success-rate claim',
            'does_not_include': ['Webots executable', 'robot meshes', 'motion files', 'course PDFs', 'JavaScript decision engine']}
(DEMO/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
# Ship the short Windows README; README_DETAILED_LOCAL.md stays local.
members = [DEMO/name for name in ('server.py', 'viewer.html', 'start.sh', 'start_windows.bat', 'README.md',
                                'example_replay.html', 'manifest.json')]
members.append(DEMO/'defence_replay.html')
members += [DEMO/'backend'/name for name in files]
archive = ROOT/'2D_Shared_Policy_2026-11-11.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
    for file in members:
        bundle.write(file, arcname=str(file.relative_to(DEMO.parent)))
    assert bundle.testzip() is None
print(archive)
print('Files:', len(members), 'ZIP bytes:', archive.stat().st_size)
