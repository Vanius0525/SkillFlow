"""Checks scientific arm coverage and exact reuse of the audited original engine."""
import ast,json,unittest
from pathlib import Path
from plan import ROOT,conditions
class CoreTests(unittest.TestCase):
    def test_frozen_engine(self):
        old=ROOT.parent/'state_completeness_20261022/run.py'
        def tree(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.ClassDef)}
        self.assertEqual(tree(old)['Engine'],tree(ROOT/'frozen_run.py')['Engine'])
    def test_arm_grid(self):
        arms=conditions();self.assertEqual(len(arms),24);self.assertNotIn(('neutral_b',-1),arms)
        for bg in ('wrong','neutral_a'):
            for l in (8,16,24):
                self.assertIn((bg+':SC',l),arms);self.assertIn((bg+':SC_exact',l),arms)
        self.assertTrue(all('window' not in arm and ':S'!=arm[-2:] for arm,l in arms))
    def test_frozen_cells(self):
        cells=json.loads((ROOT/'candidate-cells.json').read_text())['cells'];self.assertEqual(len(cells),7);self.assertNotIn('q8-medcalc',[c['key'] for c in cells]);self.assertEqual(sum(c['candidate_count'] for c in cells),457)
        self.assertTrue(all(len(c['candidate_ids'])==len(set(c['candidate_ids'])) for c in cells))
if __name__=='__main__':unittest.main()
