"""S1 numeric MILP vs completely separate finite integer enumeration oracle."""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maximin import (parse_model, solve_maximin, exact_bruteforce,
                     top_of_book_equal_size_baseline, proposal_json)


def asset(i: int, states: dict[str, int], levels: list[tuple[int, int, int]], venue: str = "v") -> dict:
    return {"id": f"token:{i}", "venue": venue, "payoffs": states,
            "asks": [{"price": price, "depth": qty, "fee_upper": fee} for price, qty, fee in levels]}


def model_data(assets: list[dict], states: list[str], budget: int = 10_000,
               venue_budgets: dict | None = None) -> dict:
    return {"coverage": "ASSUMED_STATES_ONLY", "evidence_id": "synthetic-research-fixture",
            "states": states, "scale": 100, "budget": budget,
            "venue_budgets": venue_budgets or {"v": budget}, "assets": assets}


class LimitMaximinTests(unittest.TestCase):
    def test_three_no_missed_by_pair_only_check(self):
        cases = ["A", "B", "C"]
        a = [asset(i, {s: (0 if s == winner else 100) for s in cases}, [(60, 10, 0)])
             for i, winner in enumerate(cases)]
        m = parse_model(model_data(a, cases, budget=1800))
        full = solve_maximin(m)
        gold = exact_bruteforce(m, max_candidates=1500)
        self.assertEqual(full.lower_floor, 200)
        self.assertEqual(full.lower_floor, gold.lower_floor)
        self.assertEqual(sum(b.quantity for b in full.buys), 30)
        # Pair-only nominal payoff bound is 100 - 2*60 = -20 per set.
        self.assertLess(100 - (60 + 60), 0)
        self.assertEqual(full.authority, "RESEARCH_PROPOSAL_ONLY")

    def test_varied_quantities_strictly_improve_equal_size_baseline(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/unequal-quantities.json").read_text())
        m = parse_model(fixture)
        new = solve_maximin(m)
        best = exact_bruteforce(m)
        baseline = top_of_book_equal_size_baseline(m)
        self.assertEqual((new.lower_floor, baseline.lower_floor), (164, 123))
        self.assertEqual(new.lower_floor, best.lower_floor)
        self.assertEqual([b.quantity for b in new.buys], [2, 2, 4])
        self.assertLessEqual(new.capital_required, m.budget)
        self.assertGreaterEqual(new.snapshot_floor, new.lower_floor)
        self.assertFalse(proposal_json(new)["execution_atomicity_proven"])
        self.assertFalse(proposal_json(new)["real_world_settlement_completeness_proven"])

    def test_multilevel_optimizes_against_full_limit_not_optimistic_vwap(self):
        m = parse_model(model_data([
            asset(0, {"A": 100, "B": 0}, [(40, 5, 0), (60, 5, 0)]),
            asset(1, {"A": 0, "B": 100}, [(45, 10, 0)])
        ], ["A", "B"], budget=1500))
        new = solve_maximin(m)
        self.assertEqual(new.lower_floor, 75)  # 5*(100-40-45)
        self.assertEqual(new.lower_floor, exact_bruteforce(m).lower_floor)
        self.assertEqual([b.quantity for b in new.buys], [5, 5])
        # Buying 10@A would require a 0.60 limit, not the 0.50 VWAP.
        self.assertLess(10 * 100 - 10 * 60 - 10 * 45, 0)

    def test_explicit_adverse_settlement_scenario_removes_guarantee(self):
        assets = [
            asset(0, {"one": 100, "two": 0}, [(40, 4, 0)]),
            asset(1, {"one": 0, "two": 100}, [(40, 4, 0)])
        ]
        clean = solve_maximin(parse_model(model_data(assets, ["one", "two"], budget=400)))
        self.assertGreater(clean.lower_floor, 0)
        for a in assets:
            a["payoffs"]["exception"] = 0
        adverse = solve_maximin(parse_model(model_data(assets, ["one", "two", "exception"], budget=400)))
        self.assertEqual(adverse.lower_floor, 0)
        self.assertEqual(adverse.buys, ())

    def test_fee_capital_and_venue_budget_are_binding(self):
        a = [
            asset(0, {"s0": 100, "s1": 0}, [(39, 10, 2)], venue="v1"),
            asset(1, {"s0": 0, "s1": 100}, [(39, 10, 2)], venue="v2"),
        ]
        d = model_data(a, ["s0", "s1"], budget=1000, venue_budgets={"v1": 82, "v2": 123})
        m = parse_model(d)
        new = solve_maximin(m)
        self.assertEqual(new.lower_floor, 36)  # 2*(100-41-41)
        self.assertEqual(new.lower_floor, exact_bruteforce(m).lower_floor)
        self.assertEqual([b.quantity for b in new.buys], [2, 2])

    def test_no_trade_is_admissible_and_not_a_profit_claim(self):
        m = parse_model(model_data([
            asset(0, {"s0": 100, "s1": 0}, [(55, 10, 0)]),
            asset(1, {"s0": 0, "s1": 100}, [(55, 10, 0)])
        ], ["s0", "s1"]))
        p = solve_maximin(m)
        self.assertEqual(p.lower_floor, 0)
        self.assertEqual(p.buys, ())
        self.assertEqual(p.capital_required, 0)

    def test_input_rejects_unknown_states_duplicates_and_false_fee_authority(self):
        d = model_data([asset(0, {"s0": 100, "s1": 0}, [(40, 2, 0)])], ["s0", "s1"])
        for item, pattern in [
            ({**d, "coverage": "CERTIFIED_PROTOCOL"}, "research-only"),
            ({**d, "states": ["s0", "s0"]}, "states"),
            ({**d, "assets": d["assets"] * 2}, "asset ids"),
            ({**d, "assets": [{**d["assets"][0], "payoffs": {"s0": 100}}]}, "payoff vector"),
            ({**d, "assets": [{**d["assets"][0], "asks": [{"price": 40, "depth": 1, "fee_upper": -1}]}]}, "fee upper"),
        ]:
            with self.subTest(message=pattern), self.assertRaisesRegex(ValueError, pattern):
                parse_model(item)

    def test_random_small_instances_match_exhaustive_integer_gold(self):
        rand = random.Random(20261011)
        for index in range(75):
            states = ["s0", "s1", "s2"]
            assets = []
            for i in range(2 + index % 2):
                p = rand.randint(12, 75)
                levels = [(p, rand.randint(1, 3), rand.randint(0, 6))]
                if rand.random() < 0.5:
                    levels.append((rand.randint(p + 1, 95), rand.randint(1, 2), rand.randint(0, 6)))
                payoff = {s: rand.randint(0, 1) * 100 for s in states}
                assets.append(asset(i, payoff, levels))
            budget = rand.randint(40, 600)
            m = parse_model(model_data(assets, states, budget=budget))
            with self.subTest(seed_index=index):
                numeric = solve_maximin(m)
                gold = exact_bruteforce(m)
                self.assertEqual(numeric.lower_floor, gold.lower_floor)
                self.assertLessEqual(numeric.capital_required, budget)
                self.assertGreaterEqual(numeric.snapshot_floor, numeric.lower_floor)

    def test_model_monotonicity_on_price_fees_and_capital(self):
        rand = random.Random(2047)
        for trial in range(35):
            states = ["a", "b", "c"]
            assets = []
            for i in range(3):
                pays = {s: rand.randint(0, 1) * 100 for s in states}
                assets.append(asset(i, pays, [(rand.randint(10, 80), rand.randint(1, 3), 0)]))
            base = model_data(assets, states, budget=500)
            baseline = solve_maximin(parse_model(base))
            increased = json.loads(json.dumps(base))
            for a in increased["assets"]:
                a["asks"][0]["price"] = min(100, a["asks"][0]["price"] + 6)
                a["asks"][0]["fee_upper"] = 4
            higher = solve_maximin(parse_model(increased))
            reduced = solve_maximin(parse_model({**base, "budget": 200}))
            with self.subTest(trial=trial):
                self.assertLessEqual(higher.lower_floor, baseline.lower_floor)
                self.assertLessEqual(reduced.lower_floor, baseline.lower_floor)

    def test_price_caps_reject_unsorted_and_duplicated_levels(self):
        good = model_data([asset(0, {"a": 100, "b": 0}, [(30, 2, 1)])], ["a", "b"])
        bad = json.loads(json.dumps(good))
        bad["assets"][0]["asks"].append({"price": 30, "depth": 2, "fee_upper": 1})
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            parse_model(bad)

    def test_consistent_probabilities_cannot_create_strict_positive_floor(self):
        rand = random.Random(734)
        # Every token is priced at least its expectation under the same legal
        # distribution. No nonnegative buy-only basket can have positive min-PnL.
        for i in range(75):
            weights = [rand.randint(1, 50) for _ in range(3)]
            total_weight = sum(weights)
            assets = []
            for j in range(3):
                payoff = {f"s{k}": 100 * rand.randint(0, 1) for k in range(3)}
                expected = sum(weights[k] * payoff[f"s{k}"] for k in range(3))
                ask = min(100, (expected + total_weight - 1) // total_weight + rand.randint(0, 10))
                assets.append(asset(j, payoff, [(ask, rand.randint(1, 4), rand.randint(0, 5))]))
            m = parse_model(model_data(assets, ["s0", "s1", "s2"], budget=2500))
            with self.subTest(index=i):
                p = solve_maximin(m)
                self.assertEqual(p.lower_floor, 0)
                self.assertEqual(p.buys, ())


if __name__ == "__main__":
    unittest.main()
