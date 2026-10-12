import unittest
from unittest.mock import patch
import maximin
from test_maximin import asset, model_data
from maximin import parse_model, solve_maximin, exact_bruteforce, proposal_json

class ReviewTests(unittest.TestCase):
    def test_minimum_size_inside_optimizer(self):
        data=model_data([asset(0, {"a":100,"b":0},[(40,3,0)]),
                         asset(1, {"a":0,"b":100},[(40,3,0)])], ["a","b"])
        for a in data["assets"]: a["min_quantity"]=5
        model=parse_model(data)
        self.assertEqual(solve_maximin(model).buys, ())
        self.assertEqual(exact_bruteforce(model).buys, ())
    def test_scale_exported(self):
        p=solve_maximin(parse_model(model_data([asset(0,{"a":100},[(40,3,0)])],["a"])))
        self.assertEqual(proposal_json(p)["scale"],100)
    def test_oracle_checks_size_before_allocating(self):
        m=parse_model(model_data([asset(0,{"a":100},[(40,100_000_000,0)])],["a"]))
        builtin_range=range
        def bounded_range(*args):
            if args[-1] > 1_000_000: raise AssertionError("unbounded allocation before guard")
            return builtin_range(*args)
        with patch.object(maximin, "range", bounded_range, create=True):
            with self.assertRaises(ValueError): exact_bruteforce(m,max_candidates=100)
    def test_zero_floor_is_no_trade(self):
        p=solve_maximin(parse_model(model_data([asset(0,{"a":100},[(100,3,0)])],["a"])))
        self.assertEqual(p.buys,())

    def test_minimum_quantities_match_independent_exhaustive_oracle(self):
        import random
        rng=random.Random(9012)
        for _ in range(60):
            data=model_data([asset(i,{"a":100*(i==0),"b":100*(i!=0)},
                                  [(rng.randint(1,80),rng.randint(1,4),0)]) for i in range(2)],
                            ["a","b"],budget=rng.randint(20,600))
            for a in data["assets"]: a["min_quantity"]=rng.randint(1,5)
            m=parse_model(data)
            proposed=solve_maximin(m)
            self.assertEqual(proposed.lower_floor,exact_bruteforce(m).lower_floor)
            self.assertTrue(all(b.quantity>=next(a.min_quantity for a in m.assets if a.asset_id==b.asset_id) for b in proposed.buys))
