from pathlib import Path
import re,json,hashlib,collections,bibtexparser,pymupdf
from PIL import Image
out=Path(__file__).resolve().parent;paper=out.parents[1];root=out/'source';base=paper/'audit/final-check-20261026/remote-source/overleaf-skillvector'
texts={}
def visit(name):
 p=root/name
 if not p.suffix:p=p.with_suffix('.tex')
 if p in texts:return
 t=re.sub(r'(?<!\\)%[^\n]*','',p.read_text());texts[p]=t
 for f in re.findall(r'\\input\{([^}]+)\}',t):visit(f)
visit('main.tex');alltext='\n'.join(texts.values());bib=bibtexparser.loads((root/'skillvector.bib').read_text());keys=[e['ID'] for e in bib.entries];cites=set(k.strip() for group in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}',alltext) for k in group.split(','));labels=collections.Counter(re.findall(r'\\label\{([^}]+)\}',alltext));refs=set(re.findall(r'\\(?:ref|eqref|autoref|pageref)\{([^}]+)\}',alltext))
r=dict(cited=len(cites),bib_entries=len(keys),missing_cites=sorted(cites-set(keys)),duplicate_keys=[k for k,n in collections.Counter(keys).items() if n>1],duplicate_labels=[k for k,n in labels.items() if n>1],missing_refs=sorted(refs-set(labels)),non_bib_source_changes=[str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and p.name!='skillvector.bib' and p.read_bytes()!=(root/p.relative_to(base)).read_bytes()],builds={})
pdfs={}
for name in ['baseline','revised']:
 d=out/name;log=(d/'main.log').read_text(errors='replace');aux=(d/'main.aux').read_text(errors='replace');blg=(d/'main.blg').read_text(errors='replace');p=pymupdf.open(d/'main.pdf');pdfs[name]=p
 mainpages=int(re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}',aux)[1]);text='\n'.join(x.get_text() for x in p);fonts=[]
 for x in sorted({f[0] for page in p for f in page.get_fonts(full=True)}):
  n,e,t,b=p.extract_font(x)
  if not b:fonts.append(n)
 info=dict(total_pages=len(p),main_pages=mainpages,errors=re.findall(r'^!.*',log,re.M),undefined=re.findall(r'.*(?:undefined|multiply defined).*',log),overfull=re.findall(r'.*Overfull.*',log),underfull_count=log.count('Underfull'),warnings=re.findall(r'.*Warning.*',log),bib_warnings=re.findall(r'.*(?:Warning--|error message).*',blg),fonts_not_embedded=fonts,page_sizes=sorted(set(tuple(x.rect) for x in p)),author_metadata=p.metadata.get('author'),bibitems=len(re.findall(r'\\bibitem', (d/'main.bbl').read_text())),figures={},tables={})
 for i,page in enumerate(p):
  t=page.get_text()
  for typ in ['Figure','Table']:
   for n in re.findall(typ+r' (\d+):',t):info['figures' if typ=='Figure' else 'tables'][n]=i+1
 (d/'text.txt').write_text(text)
 r['builds'][name]=info
r['first_eight_pages_text_identical']=[pdfs['baseline'][i].get_text()==pdfs['revised'][i].get_text() for i in range(8)]
r['first_eight_pages_pixels_identical']=[hashlib.sha256(pdfs['baseline'][i].get_pixmap().samples).digest()==hashlib.sha256(pdfs['revised'][i].get_pixmap().samples).digest() for i in range(8)]
r['protected_names_in_revised_pdf']={s:s in (out/'revised/text.txt').read_text() for s in ['Qwen3','SkillsBench','SWE-Skills-Bench','Doc-to-LoRA','Transformer']}
bbl=(out/'revised/main.bbl').read_text();r['formal_venues']={k:re.search(r'\\bibitem[\s\S]*?\{'+k+r'\}([\s\S]*?)(?=\\bibitem|\\end\{thebibliography\})',bbl)[1] for k in ['davidson2025prompting','tsuzuku2018lipschitz']}
r['bib_warnings_added']=sorted(set(r['builds']['revised']['bib_warnings'])-set(r['builds']['baseline']['bib_warnings']))
r['bib_warnings_removed']=sorted(set(r['builds']['baseline']['bib_warnings'])-set(r['builds']['revised']['bib_warnings']))
(out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
for start in [0,4,8]:
 canvas=Image.new('RGB',(1224,1584),'#cccccc')
 for i in range(start,start+4):
  pix=pdfs['revised'][i].get_pixmap();im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);canvas.paste(im,((i-start)%2*612,(i-start)//2*792))
 canvas.save(out/'revised'/f'pages-{start+1}-{start+4}.png')
assert not any(r[k] for k in ['missing_cites','duplicate_keys','duplicate_labels','missing_refs','non_bib_source_changes'])
v=r['builds']['revised'];assert v['main_pages']<=8 and v['total_pages']<=12
assert not any(v[k] for k in ['errors','undefined','overfull','fonts_not_embedded'])
assert v['bibitems']==33 and all(r['first_eight_pages_pixels_identical'])
assert all(r['protected_names_in_revised_pdf'].values())
print('PASS')
