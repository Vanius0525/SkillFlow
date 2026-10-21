"""Bounded read-only public-asset inspection; no model calls or large downloads."""
import collections,hashlib,json,re,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent
sources={
 'gsm8k':'https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl',
 'bigcodebench':'https://huggingface.co/datasets/WeihangSu/SRA-Bench/resolve/main/instances/bigcodebench.json',
 'math_templates':'https://raw.githubusercontent.com/YangLing0818/buffer-of-thought-llm/main/math.txt',
 'bbh_object_counting':'https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/bbh/object_counting.json',
 'bbh_arithmetic':'https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/bbh/multistep_arithmetic_two.json',
 'bbh_word_sorting':'https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/bbh/word_sorting.json'}
out=json.loads((root/'public-asset-inspection.json').read_text()) if (root/'public-asset-inspection.json').exists() else {}
for name,url in sources.items():
 if name in out:continue
 with urllib.request.urlopen(url,timeout=40) as response:
  length=response.headers.get('Content-Length')
  assert not length or int(length)<=8*1024*1024
  data=response.read(8*1024*1024+1);assert len(data)<=8*1024*1024
 row={'url':url,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 if name=='gsm8k':
  items=[json.loads(line) for line in data.decode().splitlines() if line.strip()];row.update(n=len(items),answer_separator='####',note='Original GSM8K test split; no native skill category annotations')
 elif name=='bigcodebench':
  items=json.loads(data);assert isinstance(items,list);groups=collections.Counter(tuple(sorted(i['skill_annotations'])) for i in items);single=[i for i in items if len(i['skill_annotations'])==1];sg=collections.Counter(i['skill_annotations'][0] for i in single)
  row.update(instances=len(items),single_skill_n=len(single),single_skill_groups=len(sg),single_skill_cross_question_n=sum(n for n in sg.values() if n>=2),exact_skill_set_groups=len(groups),exact_set_cross_question_n=sum(n for n in groups.values() if n>=2),single_skill_group_sizes=dict(sg))
 elif name=='math_templates':
  row['template_types']=re.findall(r'^### Problem Type (\d+): (.+)$',data.decode(),re.M);row['template_count']=len(row['template_types'])
 else:
  items=json.loads(data)['examples'];row.update(n=len(items),target_types=dict(collections.Counter('integer' if re.fullmatch(r'-?\d+',str(i['target'])) else 'other_string' for i in items)))
 out[name]=row
(root/'public-asset-inspection.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
