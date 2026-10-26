from pathlib import Path
import re, json, collections, hashlib, sys
import pymupdf, bibtexparser
out=Path(__file__).resolve().parent
root=out.parents[1]/'current/source'
sys.path.insert(0,str(out.parents[1]/'tools'))
from make_overleaf_zip import project_members
members=project_members(root)
text='\n'.join(re.sub(r'(?<!\\)%[^\n]*','',p.read_text()) for p in members if p.suffix=='.tex')
bib=bibtexparser.loads((root/'skillvector.bib').read_text())
keys=[e['ID'] for e in bib.entries]
cites=set(k.strip() for group in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}',text) for k in group.split(','))
labels=collections.Counter(re.findall(r'\\label\{([^}]+)\}',text))
refs=set(re.findall(r'\\(?:ref|eqref|autoref|pageref)\{([^}]+)\}',text))
pdf=pymupdf.open(out/'main.pdf')
log=(out/'main.log').read_text(errors='replace')
aux=(out/'main.aux').read_text(errors='replace')
fonts={f[0] for p in pdf for f in p.get_fonts(full=True)}
r=dict(main_pages=int(re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}',aux)[1]),total_pages=len(pdf),cited=len(cites),bib_entries=len(keys),missing_cites=sorted(cites-set(keys)),duplicate_keys=[k for k,n in collections.Counter(keys).items() if n>1],missing_refs=sorted(refs-set(labels)),duplicate_labels=[k for k,n in labels.items() if n>1],errors=re.findall(r'^!.*',log,re.M),undefined=re.findall(r'.*(?:undefined|multiply defined).*',log),overfull=re.findall(r'.*Overfull.*',log),warnings=re.findall(r'.*Warning.*',log),bib_warnings=(out/'main.blg').read_text().count('Warning--'),bibitems=len(re.findall(r'\\bibitem',(out/'main.bbl').read_text())),fonts_not_embedded=[pdf.extract_font(f)[0] for f in fonts if not pdf.extract_font(f)[3]],page_sizes=sorted({tuple(p.rect) for p in pdf}),pdf_author=pdf.metadata.get('author'),source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in members})
(out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
assert r['main_pages']<=8 and r['total_pages']<=12
assert not any(r[k] for k in ['missing_cites','duplicate_keys','missing_refs','duplicate_labels','errors','undefined','overfull','fonts_not_embedded'])
