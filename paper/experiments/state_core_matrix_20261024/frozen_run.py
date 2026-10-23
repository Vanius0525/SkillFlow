#!/usr/bin/env python3
"""Frozen-candidate state completeness experiment; eager/split/greedy only."""
import argparse
import copy
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from legacy_core import Scorer, cache_tensors, mask_edges

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sidecar(path, suffix):
    path = Path(path)
    if path.suffix == '.gz':
        path = path.with_suffix('')
    return path.with_suffix(suffix)


def read_records(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def record_bytes(row, compressed):
    line = (json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
    # Each record is one complete gzip member, so a flushed record is readable.
    return gzip.compress(line, mtime=0) if compressed else line


def save_json(path, data):
    # Small progress files may be overwritten; raw records are append-only.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


class Engine:
    def __init__(self, scorer, max_new):
        self.sc, self.t, self.model = scorer, scorer.torch, scorer.model
        self.max_new = max_new
        eos = self.model.generation_config.eos_token_id
        self.eos = set(eos if isinstance(eos, list) else [eos])
        self.eos.add(scorer.tok.eos_token_id)
        self.depth = len(self.model.model.layers)

    def snapshot(self, past):
        return [(k.detach().cpu().clone(), v.detach().cpu().clone())
                for k, v in (cache_tensors(past, l) for l in range(self.depth))]

    def prefix(self, ids, span, *, patch_layer=None, state=None, cut=None):
        t = self.t
        lo, hi = span
        states, handles = {}, []
        for layer, block in enumerate(self.model.model.layers):
            def hook(_mod, _inp, output, layer=layer):
                h = output[0] if isinstance(output, tuple) else output
                if layer == patch_layer:
                    h = h.clone()
                    h[:, lo:hi] = state.to(h.device, h.dtype)
                    output = (h,) + output[1:] if isinstance(output, tuple) else h
                states[layer] = h[:, lo:hi].detach().cpu().clone()
                return output
            handles.append(block.register_forward_hook(hook))
        if cut is not None:
            handles += self.install_cut(span, cut, {'start': 0})
        try:
            with t.inference_mode():
                out = self.model(input_ids=ids[:, :-1].to(self.sc.device),
                                 attention_mask=t.ones_like(ids[:, :-1], device=self.sc.device),
                                 use_cache=True)
        finally:
            for handle in handles:
                handle.remove()
        return out.past_key_values, states

    def install_cut(self, span, cut, active):
        lo, hi = span
        def hook(_module, args, kwargs):
            kwargs['attention_mask'], _ = mask_edges(kwargs.get('attention_mask'),
                lo=lo, hi=hi, query_start=active['start'], edge='both')
            return args, kwargs
        return [b.self_attn.register_forward_pre_hook(hook, with_kwargs=True)
                for b in self.model.model.layers[cut:]]

    def write(self, past, donor, positions, layers):
        positions = list(positions)
        for layer in layers:
            k, v = cache_tensors(past, layer)
            dk, dv = donor[layer]
            k[:, :, positions] = dk[:, :, positions].to(k.device, k.dtype)
            v[:, :, positions] = dv[:, :, positions].to(v.device, v.dtype)
            if not self.t.equal(k[:, :, positions].cpu(), dk[:, :, positions]):
                raise RuntimeError('K copy is not exact')
            if not self.t.equal(v[:, :, positions].cpu(), dv[:, :, positions]):
                raise RuntimeError('V copy is not exact')

    def audit(self, past, donor, span):
        lo, hi = span
        records = []
        for layer in range(self.depth):
            for kind, x, y in zip(('K', 'V'), cache_tensors(past, layer), donor[layer]):
                for label, parts in (('source', [(lo, hi)]),
                                     ('other', [(0, lo), (hi, x.shape[-2])])):
                    xx = self.t.cat([x[:, :, a:b].detach().float().cpu().reshape(-1)
                                     for a, b in parts])
                    yy = self.t.cat([y[:, :, a:b].float().reshape(-1) for a, b in parts])
                    delta = xx - yy
                    records.append(dict(layer=layer, tensor=kind, region=label,
                        max_abs=float(delta.abs().max()),
                        relative_l2=float(delta.norm() / yy.norm().clamp_min(1e-30)),
                        exact_fraction=float((xx == yy).float().mean())))
        return records

    def generate(self, ids, past, span, *, cut=None):
        t = self.t
        ids = ids.to(self.sc.device)
        n = ids.shape[1]
        active = {'start': n - 1}
        handles = self.install_cut(span, cut, active) if cut is not None else []
        eos, tokens = self.eos, []
        try:
            with t.inference_mode():
                out = self.model(input_ids=ids[:, -1:], attention_mask=t.ones_like(ids),
                                 past_key_values=past, use_cache=True)
                first_logits = out.logits[0, -1].float()
                if not t.isfinite(first_logits).all():
                    raise RuntimeError('Nonfinite logits')
                first = t.topk(first_logits.log_softmax(-1), 5)
                nxt = first_logits.argmax().view(1, 1)
                for j in range(self.max_new):
                    token = int(nxt.item())
                    tokens.append(token)
                    if token in eos or j == self.max_new - 1:
                        break
                    active['start'] = n + j
                    out = self.model(input_ids=nxt,
                        attention_mask=t.ones((1, n+j+1), dtype=ids.dtype, device=ids.device),
                        past_key_values=out.past_key_values, use_cache=True)
                    nxt = out.logits[0, -1].argmax().view(1, 1)
        finally:
            for handle in handles:
                handle.remove()
        return dict(token_ids=tokens, text=self.sc.tok.decode(tokens, skip_special_tokens=True),
                    n_generated=len(tokens), truncated=tokens[-1] not in eos,
                    first={'ids': first.indices.tolist(), 'logp': first.values.tolist()})


def neutral_ids(sc, original, span, text):
    lo, hi = span
    filler = sc.tok(text, add_special_tokens=False, return_tensors='pt')['input_ids']
    filler = filler.repeat(1, (hi-lo)//filler.shape[1]+1)
    ids = original.clone()
    ids[:, lo:hi] = filler[:, :hi-lo]
    assert sc.torch.equal(ids[:, :lo], original[:, :lo])
    assert sc.torch.equal(ids[:, hi:], original[:, hi:])
    return ids


def conditions(mode, depth):
    if mode == 'gate':
        return [('donor', -1), ('wrong', -1), ('identity', 16),
                ('full_copy', -1), ('C_all', -1), ('SC_exact', 16), ('suffix_replay', -1)]
    if mode == 'depth':
        return ([(x, -1) for x in ('donor', 'wrong', 'neutral_a', 'neutral_b', 'no_skill')]
                + [(x, l) for l in range(depth) for x in ('S_wrong', 'S_neutral_a', 'KO')]
                + [('S_neutral_b', l) for l in (8, 16, 24)])
    common = [(x, -1) for x in ('donor', 'wrong', 'neutral_a', 'neutral_b', 'no_skill')]
    for receiver in ('wrong', 'neutral_a'):
        common += [(f'{receiver}:{x}', -1) for x in
                   ('C_all', 'B_only', 'full_copy', 'suffix_replay')]
        common += [(f'{receiver}:{x}', l) for l in (8, 16, 24) for x in
                   ('S', 'C_low', 'SC', 'SC_exact')]
        common += [(f'{receiver}:C_wrong', -1), (f'{receiver}:C_neutral_b', -1)]
        common += [(f'{receiver}:C_window_{start}', -1) for start in (0, 8, 16, 24)]
    return common


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--mode', choices=('gate', 'depth', 'repair'), required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--shards', type=int, default=1)
    p.add_argument('--max-new', type=int, default=1536)
    a = p.parse_args()
    sys.path.insert(0, str(HERE/'snapshot'/'howskill'))
    from howskill import sra, grade
    import torch
    import transformers
    torch.manual_seed(0)
    torch.set_num_threads(4)
    ids = json.loads((HERE/'ids.json').read_text())['ids']
    # Gate IDs fixed before inference: first two historical IDs, not outcome-selected.
    ids = ids[:2] if a.mode == 'gate' else ids[a.shard::a.shards]
    outpath = Path(a.out)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with sidecar(outpath, '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = vars(a) | {'torch': torch.__version__, 'transformers': transformers.__version__,
            'gpu': torch.cuda.get_device_name(), 'cuda': torch.version.cuda, 'ids': ids,
            'files': {str(f.relative_to(HERE)): digest(f) for f in sorted(HERE.rglob('*'))
                      if f.is_file() and f.suffix in ('.py', '.json') and 'outputs' not in f.parts
                      and f.name not in ('deployment.json', 'manifest.json', 'launch-state.json')}}
        mp = sidecar(outpath, '.manifest.json')
        if mp.exists() and json.loads(mp.read_text()) != manifest:
            raise RuntimeError('Manifest changed; use new output')
        save_json(mp, manifest)
        if torch.cuda.get_device_name().find('4090') < 0:
            raise RuntimeError('Only 4090 authorized')
        sc = Scorer(a.model, 'eager')
        engine = Engine(sc, a.max_new)
        instances, skills, pairs, distractor = sra.load('medcalcbench')
        texts = json.loads((HERE/'neutral.json').read_text())
        arms = conditions(a.mode, engine.depth)
        existing = {}
        if outpath.exists():
            for row in read_records(outpath):
                key = (row['instance_id'], row['arm'], row['layer'])
                if key in existing:
                    raise RuntimeError(f'Duplicate {key}')
                existing[key] = row
        expected = {(iid, arm, layer) for iid in ids for arm, layer in arms}
        if set(existing) - expected:
            raise RuntimeError('Unexpected records')
        with outpath.open('ab') as fh:
            for iid in ids:
                item = sc.build(instances[iid], skills, pairs, distractor)
                span = (item['lo'], item['hi'])
                lo, hi = span
                inputs = {'donor': item['ids_g'], 'wrong': item['ids_r'], 'no_skill': item['ids_none']}
                inputs.update({k: neutral_ids(sc, item['ids_g'], span, text) for k, text in texts.items()})
                donor_past, donor_h = engine.prefix(inputs['donor'], span)
                donor_kv = engine.snapshot(donor_past)
                del donor_past
                # Extra cached content control uses the exact predeclared neutral-B span.
                nb_past, _ = engine.prefix(inputs['neutral_b'], span)
                neutral_kv = engine.snapshot(nb_past)
                del nb_past
                for arm, layer in arms:
                    key = (iid, arm, layer)
                    if key in existing:
                        continue
                    start = time.monotonic()
                    receiver, action = arm.split(':') if ':' in arm else ('wrong', arm)
                    input_key = arm if arm in inputs else ('donor' if arm == 'KO' else
                                'neutral_a' if arm == 'S_neutral_a' else
                                'neutral_b' if arm == 'S_neutral_b' else receiver)
                    input_ids = inputs[input_key]
                    state = donor_h[layer] if action in ('S', 'SC', 'SC_exact', 'S_wrong',
                                                        'S_neutral_a', 'S_neutral_b') else None
                    if action == 'identity':
                        own_past, own_h = engine.prefix(input_ids, span)
                        del own_past
                        state = own_h[layer]
                    past, _ = engine.prefix(input_ids, span,
                        patch_layer=layer if state is not None else None, state=state,
                        cut=layer if arm == 'KO' else None)
                    n_prefix = input_ids.shape[1]-1
                    source = range(lo, hi)
                    other = list(range(lo)) + list(range(hi, n_prefix))
                    written_layers, written_positions = [], []
                    if action in ('C_low', 'SC'):
                        written_layers = list(range(layer+1))
                        written_positions = list(source)
                    elif action in ('C_all', 'SC_exact', 'C_wrong', 'C_neutral_b', 'suffix_replay'):
                        written_layers = list(range(engine.depth))
                        written_positions = list(source)
                    elif action == 'B_only':
                        written_layers, written_positions = list(range(engine.depth)), other
                    elif action == 'full_copy':
                        written_layers, written_positions = list(range(engine.depth)), list(range(n_prefix))
                    elif action.startswith('C_window_'):
                        begin = int(action.rsplit('_', 1)[1])
                        written_layers, written_positions = list(range(begin, begin+8)), list(source)
                    measure = a.mode != 'depth' and input_key != 'no_skill'
                    before = engine.audit(past, donor_kv, span) if measure else None
                    if written_layers:
                        content = neutral_kv if action == 'C_neutral_b' else donor_kv
                        if action == 'C_wrong':
                            # Same wrong donor on neutral receiver; own-cache control on wrong.
                            wp, _ = engine.prefix(inputs['wrong'], span)
                            content = engine.snapshot(wp)
                            del wp
                        with torch.inference_mode():
                            engine.write(past, content, written_positions, written_layers)
                    if action == 'suffix_replay':
                        # Delete only transient cache tail via in-memory crop; no files removed.
                        past.crop(hi)
                        with torch.inference_mode():
                            if hi < n_prefix:
                                replay = input_ids[:, hi:-1].to(sc.device)
                                out = sc.model(input_ids=replay,
                                    attention_mask=torch.ones((1, n_prefix), dtype=input_ids.dtype, device=sc.device),
                                    past_key_values=past, use_cache=True)
                                past = out.past_key_values
                    after = engine.audit(past, donor_kv, span) if measure else None
                    result = engine.generate(input_ids, past, span, cut=layer if arm == 'KO' else None)
                    del past
                    row = dict(instance_id=iid, group=sra.group_key(instances[iid]), arm=arm,
                        layer=layer, source_span=list(span), prompt_tokens=input_ids.shape[1],
                        seconds=time.monotonic()-start,
                        correct=bool(grade.evaluate(result['text'], instances[iid])['correct']),
                        cache_audit_before=before, cache_audit_after=after,
                        written_layers=written_layers, written_position_count=len(written_positions),
                        **result)
                    if a.mode == 'gate' and arm in ('identity', 'full_copy'):
                        target = 'wrong' if arm == 'identity' else 'donor'
                        ref = existing[(iid, target, -1)]
                        if result['token_ids'] != ref['token_ids']:
                            raise RuntimeError(f'Gate {arm} not token-exact for {iid}')
                    if a.mode == 'gate' and arm == 'suffix_replay':
                        row['donor_tokens_equal'] = result['token_ids'] == existing[(iid, 'donor', -1)]['token_ids']
                    fh.write(record_bytes(row, outpath.suffix == '.gz'))
                    fh.flush()
                    os.fsync(fh.fileno())
                    existing[key] = row
                    progress = dict(mode=a.mode, shard=a.shard, records=len(existing), expected=len(expected),
                                    last_key=list(key), time=time.time())
                    save_json(sidecar(outpath, '.progress.json'), progress)
                    print(json.dumps(progress), flush=True)
        if set(existing) != expected:
            raise RuntimeError('Incomplete key grid')
        # Reverse-order independent label recount in the process; separate process audit later.
        for row in reversed(list(existing.values())):
            if bool(grade.evaluate(row['text'], instances[row['instance_id']])['correct']) != row['correct']:
                raise RuntimeError('Regrading mismatch')
        save_json(sidecar(outpath, '.done.json'), dict(records=len(existing), items=len(ids),
            raw_sha256=digest(outpath), mode=a.mode, time=time.time()))


if __name__ == '__main__':
    main()
