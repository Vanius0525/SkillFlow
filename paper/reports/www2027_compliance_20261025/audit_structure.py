from pathlib import Path
import re,json,collections,pymupdf
import sys,os
os.chdir(sys.argv[1])
root=Path('.'); seen=[]
def visit(name):
 p=Path(name)
 if p in seen:return ''
 seen.append(p);t=p.read_text();t=re.sub(r'(?<!\\)%[^\n]*','',t)
 for q in re.findall(r'\\input\{([^}]+)\}',t):visit(q if q.endswith('.tex') else q+'.tex')
 return t
visit('main.tex');texts={str(p):re.sub(r'(?<!\\)%[^\n]*','',p.read_text()) for p in seen};alltext='\n'.join(texts.values())
labels=collections.defaultdict(list);refs=[];cites=set()
for f,t in texts.items():
 for x in re.findall(r'\\label\{([^}]+)\}',t):labels[x].append(f)
 for x in re.findall(r'\\(?:eqref|ref|autoref|pageref)\{([^}]+)\}',t):refs.append(dict(file=f,target=x))
 for c in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}',t):cites.update(c.split(','))
bib=Path('skillvector.bib').read_text();entries={}
for m in re.finditer(r'@(\w+)\s*\{([^,]+),',bib):
 start=m.start();end=bib.find('\n@',m.end());e=bib[start:end if end>=0 else len(bib)];fields={k:re.sub(r'\s+',' ',v.strip()) for k,v in re.findall(r'(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}',e)};entries[m[2]]=dict(type=m[1],**fields)
cited={k:entries.get(k) for k in sorted(cites)}
p=pymupdf.open(sys.argv[2]);fonts=collections.Counter();sizes=collections.Counter();pages=[]
for i,page in enumerate(p):
 for b in page.get_text('dict')['blocks']:
  for line in b.get('lines',[]):
   for s in line['spans']:
    sizes[round(s['size'],2)]+=len(s['text']);fonts[s['font']]+=len(s['text'])
 pages.append(dict(page=i+1,size=list(page.rect),chars=len(page.get_text())))
font_embeds=[]
for x in sorted({f[0] for page in p for f in page.get_fonts(full=True)}):
 name,ext,typ,data=p.extract_font(x);font_embeds.append(dict(xref=x,name=name,ext=ext,type=typ,bytes=len(data)))
report=dict(active_files=[str(x) for x in seen],labels=len(labels),refs=len(refs),missing_refs=[r for r in refs if r['target'] not in labels],duplicate_labels={k:v for k,v in labels.items() if len(v)>1},cited=cited,unused_bibkeys=sorted(set(entries)-cites),pages=pages,metadata=p.metadata,font_counts=fonts.most_common(),font_sizes=sizes.most_common(),fonts=font_embeds)
Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['cited','active_files','fonts','pages']},indent=2))
for k,e in cited.items():print(k,'|',e.get('title'),'|',e.get('note',e.get('journal','')),'|',e.get('year'))
