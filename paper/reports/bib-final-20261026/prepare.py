from pathlib import Path
import shutil,re,difflib,json,bibtexparser
out=Path(__file__).resolve().parent;root=out.parents[1];before=root/'audit/final-check-20261026/remote-source/overleaf-skillvector';dest=out/'source'
shutil.copytree(before,dest,dirs_exist_ok=True)
p=dest/'skillvector.bib';old=p.read_text();new=old
for key,volume,url,doi in [
('davidson2025prompting','38','https://proceedings.neurips.cc/paper_files/paper/2025/hash/66b35d2e8d524706f39cc21f5337b002-Abstract-Conference.html','10.52202/085713-2380'),
('tsuzuku2018lipschitz','31','https://arxiv.org/abs/1802.04034',None)]:
 pat=r'@article\{'+key+r',[\s\S]*?\n\}'
 m=re.search(pat,new);assert m,key
 block=m[0].replace('@article{','@inproceedings{',1)
 fields='booktitle = {Advances in Neural Information Processing Systems},\n  volume = {'+volume+'},'
 if doi:fields+='\n  doi = {'+doi+'},'
 block=re.sub(r'journal\s*=\s*\{[^\n]+\},',lambda m:fields,block)
 block=re.sub(r'url\s*=\s*\{[^\n]+\}',lambda m:'url = {'+url+'}',block)
 new=new[:m.start()]+block+new[m.end():]
for a,b in [('{Qwen3 Technical Report}','{{Qwen3} Technical Report}'),('{SkillsBench:','{{SkillsBench}:'),('{SWE-Skills-Bench:','{{SWE-Skills-Bench}:'),('{Doc-to-{L}o{RA}:','{{Doc-to-LoRA}:'),('{Fast Transformer Decoding:','{Fast {Transformer} Decoding:')]:
 assert new.count(a)==1,a
 new=new.replace(a,b)
p.write_text(new)
(out/'bibliography.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='before/skillvector.bib',tofile='after/skillvector.bib')))
a={x['ID']:x for x in bibtexparser.loads(old).entries};b={x['ID']:x for x in bibtexparser.loads(new).entries};assert a.keys()==b.keys()
changes={k:{f:[a[k].get(f),b[k].get(f)] for f in a[k].keys()|b[k].keys() if a[k].get(f)!=b[k].get(f)} for k in a if a[k]!=b[k]}
assert len(changes)==7,changes
for k,v in changes.items():
 assert set(v)<=({'ENTRYTYPE','journal','booktitle','volume','doi','url'} if k in ['davidson2025prompting','tsuzuku2018lipschitz'] else {'title'})
for f in before.rglob('*'):
 if f.is_file() and f.name!='skillvector.bib':assert f.read_bytes()==(dest/f.relative_to(before)).read_bytes()
(out/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
print((out/'bibliography.patch').read_text())
