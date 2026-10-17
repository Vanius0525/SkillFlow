"""CPU tests of edge direction, phase-independent absolute indexing, fail-closed."""
import unittest
import torch
from run import mask_edges


class Masks(unittest.TestCase):
    def setUp(self):
        self.mask = torch.zeros(1, 1, 8, 8)
        self.mask.masked_fill_(torch.triu(torch.ones(8, 8, dtype=torch.bool), 1),
                               torch.finfo(torch.float32).min)

    def apply(self, edge):
        return mask_edges(self.mask, lo=2, hi=5, query_start=0, edge=edge)[0]

    def test_disjoint_edges_reconstruct_combined(self):
        reader, source, both = [self.apply(e) for e in ('reader','self','both')]
        self.assertTrue(torch.equal(torch.minimum(reader, source), both))
        self.assertTrue(torch.equal(reader[..., :5, :], self.mask[..., :5, :]))
        self.assertTrue(torch.equal(source[..., 5:, :], self.mask[..., 5:, :]))
        self.assertTrue((both[..., 2:, :2] == 0).all())

    def test_decode_uses_absolute_query_position(self):
        mask = torch.zeros(1, 1, 1, 9)
        reader, n = mask_edges(mask, lo=2, hi=5, query_start=8, edge='reader')
        self.assertEqual(n, 1)
        self.assertTrue((reader[..., 2:5] < -1e20).all())
        source, n = mask_edges(mask, lo=2, hi=5, query_start=8, edge='self')
        self.assertEqual(n, 0)
        self.assertTrue(torch.equal(mask, source))

    def test_invalid_mask_rejected(self):
        for mask in (None, torch.ones(1,8)):
            with self.assertRaises(RuntimeError):
                mask_edges(mask, lo=2, hi=5, query_start=0, edge='reader')
        with self.assertRaises(RuntimeError):
            mask_edges(self.mask, lo=0, hi=5, query_start=0, edge='self')

    def test_input_mask_not_mutated(self):
        saved = self.mask.clone()
        self.apply('both')
        self.assertTrue(torch.equal(saved, self.mask))


if __name__ == '__main__':
    unittest.main()
