#!/usr/bin/env python3
"""Paired source-edge and cache-history interventions; no outcome-based selection.

Layer numbers are zero-based block outputs. Cache repair is performed AFTER
prefilling all but the final prompt token, BEFORE recomputing that token.
It does not retroactively repair earlier reader computations.
"""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time


class Scorer:
    """Minimal inference wrapper, independent of historical whitebox loops."""
    def __init__(self, model_path, backend="eager"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch, self.device = torch, 'cuda'
        self.tok = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=torch.bfloat16, device_map='cuda',
            attn_implementation=backend).eval()
        self.model_path = model_path

    def prompt(self, system, user):
        merged = system + '\n\n' + user if system else user
        if 'deepseek-llm' in self.model_path.lower():
            self.prompt_mode = 'system-in-user'
            return self.tok.apply_chat_template([{'role':'user','content':merged}],
                tokenize=False, add_generation_prompt=True)
        messages = ([{'role':'system','content':system}] if system else []) + [
            {'role':'user','content':user}]
        try:
            result = self.tok.apply_chat_template(messages, tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
            self.prompt_mode = 'system-role'
        except Exception:
            result = self.tok.apply_chat_template([{'role':'user','content':merged}],
                tokenize=False, add_generation_prompt=True)
            self.prompt_mode = 'system-in-user'
        return result

    def build(self, inst, skills, pairs, distractor):
        from howskill import arms
        from howskill.prompts import build_prompt_spans
        from howskill.wb_spans import char_to_token_span
        sid = inst['skill_annotations'][0]
        if sid == distractor:
            raise ValueError('Gold skill equals fixed distractor')
        payload = arms.build('gold_no_tool', skills[sid],
                             neutral_for=skills.get(pairs.get(sid)), seed=0)
        system, user, spans = build_prompt_spans(inst, skills=payload)
        prompt = self.prompt(system, user)
        enc = self.tok(prompt, return_offsets_mapping=True, return_tensors='pt')
        base = prompt.rindex(user)
        offsets = enc['offset_mapping'][0].tolist()
        ts = {k:char_to_token_span(offsets,*spans[k],base=base) for k in ('skill','task')}
        ids = enc['input_ids']; lo,hi = ts['skill']
        filler = self.tok(skills[distractor]['content'],return_tensors='pt')['input_ids']
        width = hi-lo
        if filler.shape[1]<width:
            filler=filler.repeat(1,width//filler.shape[1]+1)
        receiver=ids.clone();receiver[0,lo:hi]=filler[0,:width]
        assert self.torch.equal(ids[:,:lo],receiver[:,:lo])
        assert self.torch.equal(ids[:,hi:],receiver[:,hi:])
        system0, user0, _ = build_prompt_spans(inst, skills=[])
        ids0 = self.tok(self.prompt(system0, user0), return_tensors='pt')['input_ids']
        return {'ids_g':ids,'ids_r':receiver,'ids_none':ids0,'lo':lo,'hi':hi,'task':ts['task']}


def mask_edges(mask, *, lo, hi, query_start, edge):
    """Fail closed; preserve every causal row's non-source alternatives."""
    import torch
    if mask is None or mask.ndim != 4:
        raise RuntimeError('Expected explicit 4D attention mask')
    if not 0 < lo < hi <= mask.shape[-1]:
        raise RuntimeError('Source span is invalid or has no prefix alternative')
    q = torch.arange(query_start, query_start + mask.shape[-2], device=mask.device)
    selected = ((q >= hi) if edge == 'reader' else
                ((q >= lo) & (q < hi)) if edge == 'self' else (q >= lo))
    out = mask.clone()
    out[..., selected, lo:hi] = torch.finfo(out.dtype).min
    if selected.any() and not (out[..., selected, :] == 0).any(dim=-1).all():
        raise RuntimeError('Intervention left an entirely masked query row')
    return out, int(selected.sum())


def cache_tensors(cache, layer):
    if hasattr(cache, 'layers'):
        return cache.layers[layer].keys, cache.layers[layer].values
    return cache.key_cache[layer], cache.value_cache[layer]


class Engine:
    def __init__(self, scorer, max_new):
        self.sc = scorer
        self.t = scorer.torch
        self.model = scorer.model
        self.max_new = max_new
        eos = self.model.generation_config.eos_token_id
        self.eos = set(eos if isinstance(eos, list) else [eos])
        self.eos.add(scorer.tok.eos_token_id)

    def capture(self, ids, positions, layers, lo, hi, *, split=True):
        states, handles = {}, []
        for layer in layers:
            def save(_mod, _inp, out, layer=layer):
                h = out[0] if isinstance(out, tuple) else out
                states[layer] = h[0, positions].detach().cpu().clone()
            handles.append(self.model.model.layers[layer].register_forward_hook(save))
        try:
            with self.t.inference_mode():
                prefix = (ids[:, :-1] if split else ids).to(self.sc.device)
                out = self.model(input_ids=prefix, attention_mask=self.t.ones_like(prefix), use_cache=True)
                kv = [(k[:, :, lo:hi].detach().cpu().clone(),
                       v[:, :, lo:hi].detach().cpu().clone())
                      for k, v in (cache_tensors(out.past_key_values, l)
                                   for l in range(len(self.model.model.layers)))]
        finally:
            for h in handles:
                h.remove()
        return states, kv

    def generate(self, ids, *, span, positions=None, state=None, layer=None,
                 cache=None, edge=None, cut=None, phase='both', split=True):
        t = self.t
        ids = ids.to(self.sc.device)
        n = ids.shape[1]
        lo, hi = span
        active = {'phase': 'prefill', 'start': 0}
        stats = {'mask_calls': 0, 'masked_rows': 0, 'patch_calls': 0,
                 'cache_layers_replaced': 0}
        handles = []
        if state is not None:
            def patch(_mod, _inp, output):
                if active['phase'] != 'prefill' or active['start'] != 0:
                    return output
                h = output[0] if isinstance(output, tuple) else output
                h = h.clone()
                h[0, positions] = state.to(device=h.device, dtype=h.dtype)
                stats['patch_calls'] += 1
                return (h,) + output[1:] if isinstance(output, tuple) else h
            handles.append(self.model.model.layers[layer].register_forward_hook(patch))
        if edge is not None:
            def apply_mask(_module, args, kwargs):
                if phase != 'both' and phase != active['phase']:
                    return None
                kwargs['attention_mask'], count = mask_edges(
                    kwargs.get('attention_mask'), lo=lo, hi=hi,
                    query_start=active['start'], edge=edge)
                stats['mask_calls'] += 1
                stats['masked_rows'] += count
                return args, kwargs
            for block in self.model.model.layers[cut:]:
                handles.append(block.self_attn.register_forward_pre_hook(apply_mask, with_kwargs=True))
        try:
            with t.inference_mode():
                if split:
                    prefix = ids[:, :-1]
                    out = self.model(input_ids=prefix, attention_mask=t.ones_like(prefix), use_cache=True)
                    past = out.past_key_values
                    if cache is not None:
                        for l in range(layer + 1):
                            k, v = cache_tensors(past, l)
                            dk, dv = cache[l]
                            k[:, :, lo:hi] = dk.to(k.device, k.dtype)
                            v[:, :, lo:hi] = dv.to(v.device, v.dtype)
                            stats['cache_layers_replaced'] += 1
                    active['start'] = n - 1
                    out = self.model(input_ids=ids[:, -1:], attention_mask=t.ones_like(ids),
                                     past_key_values=past, use_cache=True)
                else:
                    if cache is not None:
                        raise ValueError('Cache repair requires decision-token recomputation')
                    out = self.model(input_ids=ids, attention_mask=t.ones_like(ids), use_cache=True)
                past = out.past_key_values
                logits = out.logits[0, -1].float()
                if not t.isfinite(logits).all():
                    raise RuntimeError('Nonfinite decision logits')
                probs = logits.log_softmax(-1)
                top = t.topk(probs, 5)
                first = {'ids': top.indices.tolist(), 'logp': top.values.tolist()}
                nxt = logits.argmax().view(1, 1)
                tokens = []
                for j in range(self.max_new):
                    token = int(nxt.item())
                    tokens.append(token)
                    if token in self.eos:
                        break
                    if j == self.max_new - 1:
                        break
                    active.update(phase='decode', start=n+j)
                    out = self.model(input_ids=nxt,
                                     attention_mask=t.ones((1, n+j+1), dtype=ids.dtype, device=ids.device),
                                     past_key_values=past, use_cache=True)
                    past = out.past_key_values
                    nxt = out.logits[0, -1].argmax().view(1, 1)
        finally:
            for h in handles:
                h.remove()
        if state is not None and stats['patch_calls'] != 1:
            raise RuntimeError(f'Patch not applied exactly once: {stats}')
        if edge is not None and stats['mask_calls'] == 0:
            raise RuntimeError('Mask never called')
        return dict(text=self.sc.tok.decode(tokens, skip_special_tokens=True),
                    token_ids=tokens, truncated=tokens[-1] not in self.eos,
                    n_generated=len(tokens), first=first, instrumentation=stats)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--ids', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--dataset', default='medcalcbench')
    p.add_argument('--layers', default='8,12,16,24,28')
    p.add_argument('--suite', choices=['probe', 'bridge', 'edges', 'repair'], default='probe')
    p.add_argument('--max-new', type=int, default=1536)
    p.add_argument('--backend', choices=['eager','sdpa'], default='eager')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--shards', type=int, default=1)
    p.add_argument('--with-reader', action='store_true')
    p.add_argument('--phases', default='both,prefill,decode')
    a = p.parse_args()
    sys.path.insert(0, str(Path(a.repo)/'howskill'))
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ.setdefault(name,'4')
    from howskill import sra, grade
    def graded(text, inst, _mode):
        if inst.get('dataset','medcalcbench') != 'medcalcbench':
            from howskill import sra_eval
            return sra_eval.evaluate(text,inst)['correct']
        return grade.evaluate(text,inst)['correct']
    import torch
    import transformers
    torch.manual_seed(0)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    instances, skills, pairs, distractor = sra.load(a.dataset)
    sc = Scorer(a.model, a.backend)
    engine = Engine(sc, a.max_new)
    layers = [int(x) for x in a.layers.split(',')]
    ids = json.loads(Path(a.ids).read_text())
    if isinstance(ids, dict):
        ids = ids['ids']
    ids = ids[a.shard::a.shards]
    if a.limit:
        ids = ids[:a.limit]
    outpath = Path(a.out)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    config = vars(a) | {'torch': torch.__version__, 'transformers': transformers.__version__,
                        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        'ids_sha256': hashlib.sha256(Path(a.ids).read_bytes()).hexdigest(),
                        'gpu': torch.cuda.get_device_name(), 'protocol': 'split-final-prompt-token-v2',
                        'dependency_sha256': {str(f.relative_to(Path(a.repo))): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((Path(a.repo)/'howskill').rglob('*')) if f.is_file() and f.suffix in ('.py','.json')}}
    manifest = outpath.with_suffix('.manifest.json')
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        raise RuntimeError('Existing run has different configuration; choose a new output')
    manifest.write_text(json.dumps(config, indent=2)+'\n')
    with open(str(outpath)+'.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = {}
        if outpath.exists():
            for line in outpath.read_text().splitlines():
                r = json.loads(line)  # refuse corrupt or truncated records
                key = (r['instance_id'], r['arm'], r['layer'])
                if key in done:
                    raise RuntimeError(f'Duplicate record: {key}')
                done[key] = r
        with outpath.open('a', buffering=1) as fh:
            for index, iid in enumerate(ids):
                inst = instances[iid]
                item = sc.build(inst, skills, pairs, distractor)
                lo, hi = item['lo'], item['hi']
                ts = {'task':item['task']}
                reader = list(range(*ts['task']))
                n = item['ids_g'].shape[1]
                reader = [q for q in reader if hi <= q < n-1]
                source = list(range(lo, hi))
                positions = source + reader
                if not reader or hi >= n-1:
                    raise RuntimeError('Invalid source/reader spans')
                def run(arm, layer=-1, input_ids=None, **kw):
                    key = (iid, arm, layer)
                    if key in done:
                        return done[key]
                    start = time.monotonic()
                    result = engine.generate(item['ids_r'] if input_ids is None else input_ids,
                                             span=(lo, hi), layer=layer, **kw)
                    rec = dict(instance_id=iid, group=sra.group_key(inst), arm=arm, layer=layer,
                               source_span=[lo, hi], reader_span=ts['task'], prompt_tokens=n,
                               prompt_mode=sc.prompt_mode,
                               seconds=time.monotonic()-start,
                               correct=bool(graded(result['text'], inst, 'cot')), **result)
                    fh.write(json.dumps(rec, ensure_ascii=False)+'\n')
                    done[key] = rec
                    print(json.dumps({k: rec[k] for k in ['instance_id','arm','layer','correct','seconds','truncated']}), flush=True)
                    return rec
                run('no_skill', input_ids=item['ids_none'])
                donor = run('donor', input_ids=item['ids_g'])
                base = run('receiver')
                if a.suite in ('probe','bridge'):
                    fullg = run('donor_full', input_ids=item['ids_g'], split=False)
                    fullr = run('receiver_full', split=False)
                    print(json.dumps(dict(check='split_vs_full', instance_id=iid,
                        donor_tokens_equal=donor['token_ids']==fullg['token_ids'],
                        receiver_tokens_equal=base['token_ids']==fullr['token_ids'])), flush=True)
                if a.suite == 'bridge':
                    for split in (False, True):
                        label = 'split' if split else 'full'
                        gh, _ = engine.capture(item['ids_g'], source, layers, lo, hi, split=split)
                        rh, rk = engine.capture(item['ids_r'], source, layers, lo, hi, split=split)
                        expected = base if split else fullr
                        for l in layers:
                            own = run('identity_S_'+label, l, positions=source, state=rh[l], split=split)
                            if own['token_ids'] != expected['token_ids']:
                                raise RuntimeError(f'Identity S failed: {iid} {label} L{l}')
                            run('S_'+label, l, positions=source, state=gh[l], split=split)
                            if split:
                                own = run('identity_SC', l, positions=source, state=rh[l], cache=rk)
                                if own['token_ids'] != base['token_ids']:
                                    raise RuntimeError(f'Identity SC failed: {iid} L{l}')
                if a.suite in ('probe','repair'):
                    gold_h, gold_kv = engine.capture(item['ids_g'], positions, layers, lo, hi)
                    if a.suite == 'probe':
                        own_h, own_kv = engine.capture(item['ids_r'], positions, layers, lo, hi)
                    for l in layers:
                        sg = gold_h[l][:len(source)]
                        if a.suite == 'probe':
                            own = run('identity_SC', l, positions=source,
                                      state=own_h[l][:len(source)], cache=own_kv)
                            if own['token_ids'] != base['token_ids']:
                                raise RuntimeError(f'Identity failed: {iid} layer {l}')
                        run('S', l, positions=source, state=sg)
                        run('C', l, cache=gold_kv)
                        run('SC', l, positions=source, state=sg, cache=gold_kv)
                        if a.with_reader:
                            run('R', l, positions=reader, state=gold_h[l][len(source):])
                            run('SR', l, positions=positions, state=gold_h[l])
                        # Predeclared next-layer recut, not a best-cut search.
                        run('SC_recut', l, positions=source, state=sg, cache=gold_kv,
                            edge='reader', cut=l+1)
                if a.suite in ('probe','edges'):
                    for l in layers:
                        for phase in a.phases.split(','):
                            for edge in ('reader','self','both'):
                                # Source queries do not exist during decode.
                                if edge == 'self' and phase == 'decode':
                                    continue
                                run(f'cut_{edge}_{phase}', l, input_ids=item['ids_g'],
                                    edge=edge, cut=l, phase=phase)
                print(f'ITEM_DONE {index+1}/{len(ids)} {iid}', flush=True)
    outpath.with_suffix('.done.json').write_text(json.dumps({'items':len(ids),'records':len(done),'time':time.time()})+'\n')


if __name__ == '__main__':
    main()
