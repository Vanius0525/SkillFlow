"""Freeze admission using complete unpatched baselines, never patched outcomes."""
def admitted_ids(rows):
    assert rows and len({r['instance_id'] for r in rows})==len(rows)
    groups={}
    for r in rows:
        assert all(k in r for k in ['calculator_id','ok_gold_in_context','ok_receiver','ok_none'])
        groups.setdefault(r['calculator_id'],[]).append(r)
    return {r['instance_id'] for rs in groups.values() if not any(x['ok_receiver'] for x in rs) for r in rs if r['ok_gold_in_context'] and not r['ok_none']}
