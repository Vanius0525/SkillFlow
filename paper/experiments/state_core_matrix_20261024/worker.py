import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cell',required=True);a=p.parse_args()
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='4'
try:
    subprocess.run([sys.executable,'-u',str(ROOT/'run_core.py'),'--cell',a.cell],check=True)
    subprocess.run([sys.executable,'-u',str(ROOT/'audit_core.py'),'--cell',a.cell],check=True)
    print('CELL_COMPLETE_INDEPENDENTLY_AUDITED',a.cell,flush=True)
except BaseException as e:
    out=ROOT/'outputs'/a.cell;out.mkdir(parents=True,exist_ok=True);(out/'failed.json').write_text(json.dumps({'error':str(e),'time':time.time()})+'\n');raise
