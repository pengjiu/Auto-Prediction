import unittest,random
from itertools import product
from temporal import histories,atoms,robust_histories,relation_report,payout_rows

class Histories(unittest.TestCase):
    def test_exhaustive_independent_histories(self):
        rng=random.Random(731)
        for _ in range(150):
            iv=[sorted(rng.sample(range(8),2)) for _ in range(rng.randrange(1,5))]
            gold=set()
            for bits in product((0,1),repeat=8):
                gold.add(sum(1<<i for i,(lo,hi) in enumerate(iv) if any(bits[t] for t in range(lo,hi+1))))
            self.assertEqual(set(histories(iv)),gold)
    def test_recurring_not_first_occurrence(self):
        s=histories([(0,10),(2,12),(4,14)])
        self.assertIn(5,s) # occurrence in A-only AND C-only: 101 is legal
        self.assertNotIn(2,s) # B is covered by A union C; 010 impossible
        self.assertEqual(len(s),7)
    def test_shifted_start_breaks_deadline_implication(self):
        self.assertIn(1,histories([(0,10),(2,12)]))
        self.assertNotIn(1,histories([(2,10),(0,12)]))
    def test_point_intervals_and_large_ns(self):
        k=10**24
        self.assertEqual(set(histories([(k,k),(k+1,k+1)])),{0,1,2,3})
        self.assertEqual(set(histories([(k,k),(k,k)])),{0,3})
    def test_witness_reconstructs(self):
        iv=[(0,10),(2,12),(4,14)]
        for mask,ts in histories(iv).items():self.assertEqual(mask,sum(1<<i for i,(lo,hi) in enumerate(iv) if any(lo<=t<=hi for t in ts)))
    def test_higher_order_not_pairwise(self):
        members=[dict(startNS=str(a),endNS=str(b),endMinuteNS=str(b)) for a,b in [(0,10),(2,12),(4,14)]]
        s=robust_histories(members);r=relation_report(members,s)
        self.assertEqual(r['pairwise_implications'],[])
        self.assertEqual(len(r['pairwise_masks']),8)
        self.assertIn({'antecedent':1,'cover':[0,2]},r['higher_order_covers'])
    def test_boundary_unknown_is_union(self):
        m=[dict(startNS='0',endNS='10',endMinuteNS='11'),dict(startNS='0',endNS='10',endMinuteNS='11')]
        self.assertEqual(set(robust_histories(m)),{0,1,2,3})
    def test_invalid_inputs_fail(self):
        for iv in [[],[(0,1)]*7,[(2,1)],[(True,4)],[(0.0,1)]]:
            with self.assertRaises(ValueError):histories(iv)
        with self.assertRaises(ValueError):payout_rows([0,0],1)
    def test_complements(self):
        r=payout_rows([0,1,3],2)
        for i in (0,2):self.assertTrue(all(a+b==1 for a,b in zip(r[i],r[i+1])))

if __name__=='__main__':unittest.main()
