from pathlib import Path
import re,json,collections,bibtexparser,pymupdf
base=Path(__file__).resolve().parent; root=base/'remote-source/overleaf-skillvector'; texts={}
def visit(n):
 p=root/n
 if p.suffix!='.tex':p=p.with_suffix('.tex')
 if str(p) in texts:return
 t=re.sub(r'(?<!\\)%[^\n]*','',p.read_text());texts[str(p)]=t
 for x in re.findall(r'\\input\{([^}]+)\}',t):visit(x)
visit('main.tex'); alltext='\n'.join(texts.values());db=bibtexparser.loads((root/'skillvector.bib').read_text());entries={e['ID']:e for e in db.entries}
cites=set(k.strip() for x in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}',alltext) for k in x.split(','));labels=collections.Counter(re.findall(r'\\label\{([^}]+)\}',alltext));refs=re.findall(r'\\(?:eqref|ref|autoref|pageref)\{([^}]+)\}',alltext)
pdf=pymupdf.open(base/'latest.pdf');fonts=[]
for x in sorted({f[0] for p in pdf for f in p.get_fonts(full=True)}):
 n,e,t,d=pdf.extract_font(x);fonts.append(dict(name=n,embedded=bool(d),type=t))
r=dict(tex_files=len(texts),bib_entries=len(db.entries),cited_count=len(cites),missing_cites=sorted(cites-set(entries)),duplicate_bibkeys=[k for k,v in collections.Counter(e['ID'] for e in db.entries).items() if v>1],missing_refs=sorted(set(refs)-set(labels)),duplicate_labels={k:v for k,v in labels.items() if v>1},cited={k:entries[k] for k in sorted(cites)},unused=sorted(set(entries)-cites),pages=len(pdf),page_sizes=sorted(set(tuple(p.rect) for p in pdf)),fonts=fonts,metadata=pdf.metadata)
(base/'structure.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in r.items() if k not in ['cited','fonts','metadata','unused']},indent=2));print('UNEMBEDDED',[x for x in fonts if not x['embedded']])
for k in sorted(cites):print(k,entries[k]['title'])
from PIL import Image,ImageDraw
for start in [0,4,8]:
 canvas=Image.new('RGB',(1224,1584),'#cccccc')
 for j in range(start,min(start+4,len(pdf))):
  im=Image.frombytes('RGB', [612,792],pdf[j].get_pixmap(matrix=pymupdf.Matrix(1,1)).samples);canvas.paste(im,((j-start)%2*612,(j-start)//2*792))
 canvas.save(base/f'pages-{start+1}-{min(start+4,len(pdf))}.png')
