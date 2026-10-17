"""Validate and merge a complete set of disjoint, fixed-ID GPU shards."""
import hashlib
import json
from pathlib import Path


def load_completed(inputs, ids_path, suite, layers):
    ids_path=Path(ids_path)
    ids=json.loads(ids_path.read_text())['ids']
    ids_hash=hashlib.sha256(ids_path.read_bytes()).hexdigest()
    source_hash=hashlib.sha256(Path(__file__).with_name('run.py').read_bytes()).hexdigest()
    rows=[]; manifests=[]; completions=[]; hashes={}; seen=set(); common=None
    stable=['suite','backend','layers','max_new','dataset','with_reader','phases',
            'torch','transformers','script_sha256','ids_sha256','gpu','protocol',
            'dependency_sha256','shards']
    for name in inputs:
        path=Path(name)
        manifest=json.loads(path.with_suffix('.manifest.json').read_text())
        done=json.loads(path.with_suffix('.done.json').read_text())
        if manifest['suite']!=suite or manifest['backend']!='eager' or manifest['layers']!=layers:
            raise ValueError('Unexpected suite/backend/layers')
        if manifest['limit'] or manifest['ids_sha256']!=ids_hash or manifest['script_sha256']!=source_hash:
            raise ValueError('Partial sample or mismatched IDs/inference source')
        config={k:manifest[k] for k in stable}
        if common is not None and common!=config:
            raise ValueError('Incompatible inference configurations across shards')
        common=config
        shard=manifest['shard']; count=manifest['shards']
        if not 0<=shard<count or shard in seen:
            raise ValueError('Invalid or duplicate shard')
        seen.add(shard)
        part=[json.loads(x) for x in path.read_text().splitlines()]
        expected=ids[shard::count]
        if set(r['instance_id'] for r in part)!=set(expected):
            raise ValueError('Shard IDs do not match the predetermined partition')
        if done['items']!=len(expected) or done['records']!=len(part):
            raise ValueError('Completion marker disagrees with raw output')
        rows.extend(part); manifests.append(manifest);completions.append(done)
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    if common is None or seen!=set(range(common['shards'])):
        raise ValueError('Not all declared shards are complete')
    keyed={(r['instance_id'],r['arm'],r['layer']):r for r in rows}
    if len(rows)!=len(keyed):
        raise ValueError('Duplicate item/arm/layer records')
    return ids,rows,keyed,dict(input_sha256=hashes,manifests=manifests,completion=completions)
