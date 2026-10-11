"""Deterministic SYNTHETIC algorithm comparison, not a market PnL backtest."""
from __future__ import annotations

import json
import random
from statistics import median
from time import perf_counter
from pathlib import Path

from maximin import parse_model, solve_maximin, top_of_book_equal_size_baseline


def main() -> None:
    rng = random.Random(20261011)
    runs = 150
    total_synthetic_milp_advantage_ticks = 0
    cases_stronger = 0
    cases_equal = 0
    milp_ms = []
    reference_ms = []
    for j in range(runs):
        states = ["low", "mid", "high", "exception"]
        assets = []
        for i in range(3 + j % 2):
            outcome = [100 * rng.randint(0, 1) for _ in states]
            if outcome == [0] * len(states):
                outcome[0] = 100
            price = rng.randint(12, 69)
            levels = [
                {"price": price, "depth": rng.randint(1, 6), "fee_upper": rng.randint(0, 5)},
                {"price": rng.randint(price + 1, 99), "depth": rng.randint(1, 6),
                 "fee_upper": rng.randint(0, 5)},
            ]
            assets.append({"id": f"paper:{i}", "venue": "paper", "asks": levels,
                           "payoffs": dict(zip(states, outcome))})
        model = parse_model({
            "coverage": "ASSUMED_STATES_ONLY",
            "evidence_id": f"synthetic-seed-20261011-case-{j}",
            "states": states, "scale": 100, "budget": rng.randint(90, 1300),
            "venue_budgets": {"paper": 1300}, "assets": assets,
        })
        start = perf_counter()
        new = solve_maximin(model, time_limit=5)
        milp_ms.append((perf_counter() - start) * 1000)
        start = perf_counter()
        baseline = top_of_book_equal_size_baseline(model)
        reference_ms.append((perf_counter() - start) * 1000)
        if new.lower_floor < baseline.lower_floor:
            raise AssertionError("maximin search regressed below its included baseline")
        gain = new.lower_floor - baseline.lower_floor
        total_synthetic_milp_advantage_ticks += gain
        if gain > 0:
            cases_stronger += 1
        else:
            cases_equal += 1
    result = {
        "dataset": "SYNTHETIC_FINITE_PAYOFF_MODELS_ONLY",
        "real_market_pnl_claimed": False,
        "capturable_execution_estimated": False,
        "algorithm": "HiGHS MILP one executable BUY limit per asset, integer quantity, conservatively full-at-limit cost",
        "baseline": "all subsets equal share count at first ask, same states, fees and budget",
        "cases": runs,
        "milp_strictly_stronger": cases_stronger,
        "equal": cases_equal,
        "sum_objective_difference_ticks_across_unrelated_synthetic_cases_not_profit": total_synthetic_milp_advantage_ticks,
        "median_milp_ms": round(median(milp_ms), 3),
        "median_equal_size_scan_ms": round(median(reference_ms), 3),
        "max_milp_ms": round(max(milp_ms), 3),
    }
    p = Path(__file__).parent / "synthetic-benchmark.json"
    p.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
