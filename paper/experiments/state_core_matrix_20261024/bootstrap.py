"""GPU Job bootstrap: deploy small frozen source payload and copy existing shared data.

No model downloads, no deletion, no CPU Notebook dependency. One lock serializes
source verification and CPU-only tokenizer preflight across all seven jobs.
"""
import base64,fcntl,gzip,hashlib,io,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path('/inspire/ssd/project/project-public/czxs253130660/state-core-matrix-20261024-v1')
PYTHON='/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python'
ROOT.mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def deploy(payload):
    with (ROOT/'bootstrap.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(payload)),mode='r:gz') as archive:
            for member in archive.getmembers():
                assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                data=archive.extractfile(member).read();dst=ROOT/member.name;dst.parent.mkdir(parents=True,exist_ok=True)
                if dst.exists():assert dst.read_bytes()==data,'Conflicting existing source: '+member.name
                else:
                    with dst.open('xb') as f:f.write(data)
        manifest=json.loads((ROOT/'source-manifest-preflight.json').read_text())
        for name,expected in manifest.items():
            dst=ROOT/name
            if not dst.exists() and name.startswith('snapshot/howskill/data/'):
                rel=name.removeprefix('snapshot/howskill/data/')
                sources=[Path('/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v2/snapshot/howskill/data')/rel,Path('/inspire/ssd/project/project-public/czxs253130660/family-depth-20261018-v1/repo/howskill/data')/rel]
                src=next((p for p in sources if p.exists() and sha(p)==expected),None)
                assert src is not None,'No hash-matched shared input: '+name
                dst.parent.mkdir(parents=True,exist_ok=True)
                with src.open('rb') as a,dst.open('xb') as b:shutil.copyfileobj(a,b)
            assert dst.exists() and sha(dst)==expected,'Input/source hash mismatch: '+name
        if not (ROOT/'cells.json').exists():subprocess.run([PYTHON,'-u',str(ROOT/'preflight.py')],check=True)
        frozen=dict(manifest);frozen['cells.json']=sha(ROOT/'cells.json')
        fp=ROOT/'source-manifest.json'
        if fp.exists():assert json.loads(fp.read_text())==frozen
        else:fp.write_text(json.dumps(frozen,indent=2)+'\n')
        (ROOT/'PREPARED').write_text('All sources/inputs SHA-verified; frozen input eligibility prepared.\n')
    print('BOOTSTRAP_READY',flush=True)
    subprocess.run([PYTHON,'-u',str(ROOT/'worker.py'),'--cell',sys.argv[1]],check=True)
