"""Frozen LogicBench baseline generation and independent raw-answer audit."""
from __future__ import annotations
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'snapshot'))
from howskill import sra, sra_eval, arms
from howskill.prompts import build_prompt_spans
from engine import Scorer, Engine

MODELS = {
    'q8': 'Qwen3-8B', 'mistral': 'Mistral-7B-Instruct-v0.3',
    'llama': 'Llama-3.1-8B-Instruct', 'deepseek': 'deepseek-llm-7b-chat',
}
MODEL_ROOT = Path('/inspire/ssd/project/project-public/czxs253130660/models')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    inst, skills, pairs, distractor = sra.load('logicbench')
    assert len(inst) == 760 and len(skills) == 19
    assert all(sra.single_skill(i) for i in inst.values())
    assert all(n == 40 for n in collections.Counter(sra.group_key(i) for i in inst.values()).values())
    return inst, skills, pairs, distractor


def expected(inst, distractor):
    return {(iid, arm) for iid, item in inst.items()
            for arm in (('donor', 'no_skill') if item['skill_annotations'][0] == distractor
                        else ('donor', 'receiver', 'no_skill'))}


def read_rows(path):
    if not path.exists():
        return {}
    rows = {}
    for line in path.read_text().splitlines():
        r = json.loads(line)
        k = (r['instance_id'], r['arm'])
        assert k not in rows, f'Duplicate {k}'
        rows[k] = r
    return rows


def audit(path, *, require_complete=True):
    inst, skills, pairs, distractor = inputs()
    rows = read_rows(path)
    exp = expected(inst, distractor)
    assert set(rows) <= exp
    if require_complete:
        assert set(rows) == exp, f'Missing {len(exp-set(rows))} records'
    # Re-evaluate in reverse order, without trusting saved correctness labels.
    for k in reversed(list(rows)):
        r = rows[k]
        result = sra_eval.evaluate(r['text'], inst[k[0]])
        assert result == r['grade'], k
        assert r['correct'] == result['correct'], k
        assert r['n_generated'] == len(r['token_ids'])
    eligible = sorted(i for i in inst if all((i, a) in rows for a in ('donor', 'receiver', 'no_skill'))
                      and rows[i, 'donor']['correct'] and not rows[i, 'receiver']['correct']
                      and not rows[i, 'no_skill']['correct'])
    def stats(ids):
        out = {}
        for arm in ('donor', 'receiver', 'no_skill'):
            rs = [rows[i, arm] for i in ids if (i, arm) in rows]
            n = len(rs)
            out[arm] = {'n': n, 'correct': sum(r['correct'] for r in rs),
                        'accuracy': sum(r['correct'] for r in rs)/n if n else None,
                        'truncated': sum(r['truncated'] for r in rs)}
        both = [i for i in ids if (i, 'donor') in rows and (i, 'no_skill') in rows]
        out['rescued'] = sum(rows[i, 'donor']['correct'] and not rows[i, 'no_skill']['correct'] for i in both)
        out['harmed'] = sum(not rows[i, 'donor']['correct'] and rows[i, 'no_skill']['correct'] for i in both)
        out['paired_n'] = sum((i, 'receiver') in rows for i in ids)
        out['eligible_n'] = len(set(ids) & set(eligible))
        return out
    paired = [i for i in inst if inst[i]['skill_annotations'][0] != distractor]
    result = {'time': time.time(), 'complete': set(rows) == exp, 'records': len(rows),
              'expected_records': len(exp), 'raw_sha256': digest(path),
              'all': stats(list(inst)), 'paired': stats(paired),
              'by_type': {typ: stats([i for i in inst if inst[i]['eval_data']['task_type'] == typ])
                          for typ in ('BQA', 'MCQA')},
              'by_skill': {sid: stats([i for i in inst if sra.group_key(inst[i]) == sid]) for sid in skills},
              'common_ids': eligible, 'common_n': len(eligible),
              'groups': len({sra.group_key(inst[i]) for i in eligible})}
    path.with_suffix('.summary.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def generate(key):
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '4'
    import torch
    import transformers
    torch.set_num_threads(4)
    assert torch.cuda.is_available() and '4090' in torch.cuda.get_device_name()
    assert torch.version.cuda == '12.8' and transformers.__version__ == '4.57.6'
    inst, skills, pairs, distractor = inputs()
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    path = out / f'{key}.jsonl'
    with (out / f'{key}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        for rel, sha in manifest['sha256'].items():
            assert digest(ROOT / rel) == sha, f'Changed input: {rel}'
        run = {'model': str(MODEL_ROOT / MODELS[key]), 'max_new': 900, 'backend': 'eager',
               'dtype': 'bfloat16', 'prefill': 'full', 'seed': 0,
               'manifest_sha256': digest(ROOT / 'manifest.json')}
        runpath = out / f'{key}.run.json'
        if runpath.exists():
            previous = json.loads(runpath.read_text())
            prior_hash = previous.pop('manifest_sha256')
            assert previous == {k: v for k, v in run.items() if k != 'manifest_sha256'}
            assert prior_hash in [run['manifest_sha256']] + manifest.get('compatible_previous_manifests', [])
        else:
            with runpath.open('x') as f:
                json.dump(run, f, indent=2)
        rows = read_rows(path)
        assert set(rows) <= expected(inst, distractor)
        hardware = {'time': time.time(), 'torch': torch.__version__, 'cuda': torch.version.cuda,
                    'transformers': transformers.__version__,
                    'execution_manifest_sha256': run['manifest_sha256'],
                    'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,uuid,driver_version',
                                                    '--format=csv,noheader'], text=True).strip()}
        with (out / f'{key}.hardware.jsonl').open('a') as f:
            f.write(json.dumps(hardware)+'\n')
        torch.manual_seed(0)
        sc = Scorer(run['model'], backend='eager')
        eng = Engine(sc, 900)
        def progress(**kw):
            obj = {'time': time.time(), 'model': key, **kw}
            (out / f'{key}.progress.json').write_text(json.dumps(obj)+'\n')
            print(json.dumps(obj), flush=True)
        progress(stage='baseline_generation', completed=len(rows), expected=len(expected(inst, distractor)))
        with path.open('a', buffering=1) as f:
            for iid in sorted(inst):
                item = inst[iid]
                sid = item['skill_annotations'][0]
                if sid != distractor:
                    b = sc.build(item, skills, pairs, distractor)
                else:
                    payload = arms.build('gold_no_tool', skills[sid], neutral_for=skills.get(pairs.get(sid)), seed=0)
                    system, user, _ = build_prompt_spans(item, skills=payload)
                    ids_g = sc.tok(sc.prompt(system, user), return_tensors='pt')['input_ids']
                    system, user, _ = build_prompt_spans(item, skills=[])
                    ids_none = sc.tok(sc.prompt(system, user), return_tensors='pt')['input_ids']
                    b = {'ids_g': ids_g, 'ids_none': ids_none, 'lo': None, 'hi': None}
                for arm, source in [('donor', 'ids_g'), ('receiver', 'ids_r'), ('no_skill', 'ids_none')]:
                    if source not in b or (iid, arm) in rows:
                        continue
                    ids = b[source]
                    assert ids.shape[1]+900 <= sc.model.config.max_position_embeddings
                    started = time.time()
                    result = eng.generate(ids, span=(b['lo'], b['hi']), split=False)
                    grade = sra_eval.evaluate(result['text'], item)
                    r = {'instance_id': iid, 'group': sid, 'arm': arm, 'correct': grade['correct'],
                         'execution_manifest_sha256': run['manifest_sha256'],
                         'grade': grade, 'task_type': item['eval_data']['task_type'],
                         'prompt_sha256': hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
                         'prompt_tokens': ids.shape[1], 'source_span': [b['lo'], b['hi']],
                         'seconds': time.time()-started, 'prompt_mode': sc.prompt_mode, **result}
                    f.write(json.dumps(r, ensure_ascii=False)+'\n')
                    f.flush()
                    os.fsync(f.fileno())
                    rows[iid, arm] = r
                    progress(stage='baseline_generation', completed=len(rows), instance=iid, arm=arm,
                             correct=r['correct'], n_generated=r['n_generated'], seconds=r['seconds'])
        progress(stage='audit', completed=len(rows))
        subprocess.run([sys.executable, str(ROOT / 'baseline.py'), '--audit', str(path)], check=True)
        progress(stage='complete', completed=len(rows))
        with (out / f'{key}.done.json').open('x') as f:
            json.dump({'time': time.time(), 'records': len(rows), 'sha256': digest(path)}, f)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--key', choices=list(MODELS))
    p.add_argument('--audit', type=Path)
    a = p.parse_args()
    if a.audit:
        report = audit(a.audit)
        print(json.dumps({k: report[k] for k in ('complete', 'records', 'all', 'paired', 'common_n', 'groups')}))
    else:
        assert a.key
        generate(a.key)
