"""CPU checks for intervention coordinates, cache audits and frozen plans."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile

import torch
from run import Engine, conditions, neutral_ids, sidecar, read_records, record_bytes
from legacy_core import mask_edges


class Instruments(unittest.TestCase):
    def setUp(self):
        self.engine = Engine.__new__(Engine)
        self.engine.t, self.engine.depth = torch, 3
        self.past = SimpleNamespace(key_cache=[torch.zeros(1, 2, 7, 4) for _ in range(3)],
                                    value_cache=[torch.zeros(1, 2, 7, 4) for _ in range(3)])
        self.donor = [(torch.ones(1, 2, 7, 4)*(l+1), torch.ones(1, 2, 7, 4)*(l+4))
                      for l in range(3)]

    def test_copy_preserves_other_positions_and_layers(self):
        self.engine.write(self.past, self.donor, range(2, 5), [1])
        self.assertTrue(torch.equal(self.past.key_cache[1][:, :, 2:5], self.donor[1][0][:, :, 2:5]))
        self.assertEqual(self.past.key_cache[1][:, :, :2].count_nonzero(), 0)
        self.assertEqual(self.past.key_cache[1][:, :, 5:].count_nonzero(), 0)
        self.assertEqual(self.past.key_cache[0].count_nonzero(), 0)
        audit = self.engine.audit(self.past, self.donor, (2, 5))
        src = [x for x in audit if x['layer'] == 1 and x['region'] == 'source']
        self.assertTrue(all(x['max_abs'] == 0 and x['exact_fraction'] == 1 for x in src))

    def test_full_copy_and_noncontiguous_other(self):
        other = [0, 1, 5, 6]
        self.engine.write(self.past, self.donor, other, range(3))
        self.assertEqual(self.past.key_cache[2][:, :, 2:5].count_nonzero(), 0)
        self.engine.write(self.past, self.donor, range(2, 5), range(3))
        audit = self.engine.audit(self.past, self.donor, (2, 5))
        self.assertTrue(all(x['max_abs'] == 0 for x in audit))

    def test_mask_preserves_causality_and_non_source(self):
        mask = torch.zeros(1, 1, 7, 7)
        mask.masked_fill_(torch.ones(7, 7, dtype=torch.bool).triu(1), torch.finfo(mask.dtype).min)
        new, count = mask_edges(mask, lo=2, hi=5, query_start=0, edge='both')
        self.assertEqual(count, 5)
        self.assertTrue(torch.equal(new[:, :, :2], mask[:, :, :2]))
        self.assertTrue(torch.equal(new[:, :, :, :2], mask[:, :, :, :2]))
        self.assertTrue((new[:, :, 2:, 2:5] == torch.finfo(mask.dtype).min).all())

    def test_frozen_ids_and_plan_unique(self):
        ids = json.loads((Path(__file__).parent/'ids.json').read_text())['ids']
        self.assertEqual(len(ids), 124)
        self.assertEqual(len(set(ids)), 124)
        for mode in ('gate', 'depth', 'repair'):
            arms = conditions(mode, 36)
            self.assertEqual(len(arms), len(set(arms)))
        self.assertEqual(len(conditions('depth', 36)), 116)
        self.assertEqual(len(conditions('repair', 36)), 49)

    def test_compressed_records_are_lossless_and_appendable(self):
        rows = [{'x': '完整记录', 'tokens': [1, 2, 3]}, {'nested': {'v': 0.125}}]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'gate-0-of-1.jsonl.gz'
            for row in rows:
                with p.open('ab') as stream:
                    stream.write(record_bytes(row, True))
                self.assertEqual(read_records(p), rows[:len(read_records(p))])
            self.assertEqual(read_records(p), rows)
            self.assertEqual(sidecar(p, '.done.json').name, 'gate-0-of-1.done.json')


if __name__ == '__main__':
    unittest.main()
