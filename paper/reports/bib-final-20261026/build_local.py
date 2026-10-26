from pathlib import Path
import subprocess,tempfile,shutil,json,sys
out=Path(__file__).resolve().parent;paper=out.parents[1]
base=Path('/mnt/c/Users/12970/AppData/Local/Temp/WWW2027');bins=Path('/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64')
receipt=json.loads((out/'build-receipt.json').read_text()) if (out/'build-receipt.json').exists() else {}
for name,src in [('baseline',paper/'audit/final-check-20261026/remote-source/overleaf-skillvector'),('revised',out/'source')]:
 if '--revised-only' in sys.argv and name!='revised':continue
 stage=Path(tempfile.mkdtemp(prefix='bib-final-'+name+'-',dir=base));shutil.copytree(src,stage,dirs_exist_ok=True)
 target=out/name;target.mkdir(exist_ok=True);receipt[name]={'stage':str(stage),'runs':[]}
 (out/'build-receipt.json').write_text(json.dumps(receipt,indent=2))
 for i,cmd in enumerate([['pdflatex.exe','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex.exe','main'],['pdflatex.exe','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex.exe','main'],['pdflatex.exe','-interaction=nonstopmode','-halt-on-error','main.tex'],['pdflatex.exe','-interaction=nonstopmode','-halt-on-error','main.tex']]):
  print(name,i,cmd[0],flush=True)
  r=subprocess.run([str(bins/cmd[0])]+cmd[1:],cwd=stage,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  (target/f'pass-{i}.txt').write_bytes(r.stdout);receipt[name]['runs'].append({'command':cmd,'returncode':r.returncode});(out/'build-receipt.json').write_text(json.dumps(receipt,indent=2))
  if r.returncode:print(r.stdout.decode(errors='replace')[-5000:],flush=True);raise SystemExit(r.returncode)
 for ext in ['pdf','log','aux','bbl','blg']:shutil.copy2(stage/('main.'+ext),target/('main.'+ext))
 print('COMPLETE',name,stage,flush=True)
