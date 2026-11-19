"""Check byte-identical ZIP content and standalone execution outside the repo."""
from pathlib import Path
import ast,hashlib,json,subprocess,sys,tempfile,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[1];APP=ROOT/'2D_Shared_Policy_2026-11-11';archive=ROOT/'2D_Shared_Policy_2026-11-11.zip'
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for member in z.namelist():assert z.read(member)==(ROOT/member).read_bytes(),member
 assert len(z.namelist())==20
 assert not any('README_DETAILED_LOCAL' in n for n in z.namelist())
 with tempfile.TemporaryDirectory(prefix='football-delivery-') as temp:
  d=Path(temp);z.extractall(d);app=d/APP.name
  result=subprocess.run([sys.executable,str(app/'server.py'),'--batch','3','--seed','347','--seconds','180','--output',str(d/'check')],cwd='/',capture_output=True,text=True,check=True)
  output=json.loads((d/'check'/'metrics.json').read_text())
  assert output['source']['kind']=='local snapshot'
  assert len(output['runs'])==3
  assert output['source']['sha256']==json.loads((H/'production-holdout.json').read_text())['source']['sha256']
  replay=(d/'check'/'replay.html').read_text()
  payload=json.JSONDecoder().raw_decode(replay.split('window.PYTHON_REPLAY=',1)[1])[0]
  assert len(payload['frames'])>2
  assert payload['frames'][-1]['outcome']==output['runs'][0]['outcome']
  assert abs(payload['frames'][-1]['t']-output['runs'][0]['seconds'])<1e-8
  smoke={'outcomes':output['outcomes'],'source':output['source']}
for f in (APP/'backend').rglob('*.py'):ast.parse(f.read_text(),filename=str(f),feature_version=(3,8))
result={'zip_members_match_workspace':True,'members':20,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'no_3d_dependency_smoke':smoke,'python_38_syntax_parse':True,'native_windows_execution_claimed':False}
(H/'package-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
