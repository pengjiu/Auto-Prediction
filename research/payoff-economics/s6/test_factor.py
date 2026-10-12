import unittest
from itertools import product
from fractions import Fraction as F
from factor import truth_states,pairwise_relaxation,rows
class FactorTests(unittest.TestCase):
 def test_other_not_dropped(self):
  states=truth_states();self.assertEqual(len(states),9)
  self.assertIn((True,False,False,False),states) # D Senate, Other House
  self.assertIn((False,False,False,False),states)
 def test_both_factors_needed(self):
  for s in truth_states():self.assertEqual(s[2],s[0] and s[1])
 def test_pairwise_information_is_strict_relaxation(self):
  states=truth_states();p=pairwise_relaxation(states)
  self.assertTrue(set(states)<set(p));self.assertIn((True,True,False,False),p)
 def test_true_arbitrage_positive_control_only_synthetic(self):
  p=rows(truth_states());r=rows(pairwise_relaxation(truth_states()))
  # NO(Senate D) + NO(House D) + YES(joint DD). Lower bound 1 only with AND.
  idx=[1,3,4];self.assertEqual(min(sum(p[i][j] for i in idx) for j in range(len(p[0]))),1)
  self.assertEqual(min(sum(r[i][j] for i in idx) for j in range(len(r[0]))),0)
 def test_independent_half_payments_not_bool_coerced(self):
  r=rows(list(product((F(0),F(1,2),F(1)),repeat=4)));self.assertIn(F(1,2),r[0]);self.assertEqual(len(r[0]),81)
 def test_bad_matrices_rejected(self):
  with self.assertRaises(ValueError):pairwise_relaxation([(1,0,0,0)])
  with self.assertRaises(ValueError):rows([(0.5,False,False,False)])
if __name__=='__main__':unittest.main()
