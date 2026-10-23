"""Build reviewable bounded job commands; no submission here."""
import base64,hashlib,io,json,shlex,tarfile,zlib
from pathlib import Path
from plan import ROOT,REMOTE,PYTHON,sha,save
files={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and (p.suffix=='.py' or 'snapshot' in p.parts or p.name in ('candidate-cells.json','neutral.json')) and '__pycache__' not in p.parts}
save(ROOT/'source-manifest-preflight.json',files)
paths=[p for p in files if not p.startswith('snapshot/howskill/data/')]+['source-manifest-preflight.json']
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as tf:
    for name in paths:tf.add(ROOT/name,arcname=name)
payload=base64.b64encode(buf.getvalue()).decode();source=(ROOT/'bootstrap.py').read_text()+'\ndeploy('+repr(payload)+')\n';packed=base64.b64encode(zlib.compress(source.encode())).decode()
code="import base64,zlib;exec(zlib.decompress(base64.b64decode("+repr(packed)+")))"
jobs=[]
for cell in json.loads((ROOT/'candidate-cells.json').read_text())['cells']:
    cmd=shlex.join([PYTHON,'-u','-c',code,cell['key']]);assert len(cmd.encode())<120000
    jobs.append({'name':'wt-sc24-'+cell['key']+'-1024','cell':cell['key'],'workspace':'可上网GPU资源','project':'公共科研项目','group':'4090-2-cuda13.2','quota':'1,10,100','image':'ngc-pytorch:25.02-cuda12.8.0-py3','priority':4,'shm_size':32,'max_time':48,'command':cmd,'env':{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','MKL_NUM_THREADS':'4'}})
save(ROOT/'jobs.json',{'jobs':jobs,'max_gpu':7,'deployment':'Small compressed source payload; existing shared inputs hash-checked; no Notebook dependency','payload_bytes':len(buf.getvalue()),'per_command_bytes':len(jobs[0]['command'].encode())})
print('Prepared',len(jobs),'single-GPU jobs, payload',len(buf.getvalue()),'bytes, each command',len(jobs[0]['command'].encode()),'bytes')
