# S1: Conditional payoff maximin — bounded research specimen

This is a **new, isolated mutation candidate**, based on the P0 economics work in `codex/mutation-payoff-economics`. It does **not** change application trading paths, the existing verifier, market adapters, or any service configuration. This is a concrete algorithm and reproducible tests rather than a placeholder package.

## Thesis and adoption criteria

Given **the same explicitly assumed finite payout states**, visible ask ladders, stated worst-per-share fees and a fixed budget, a mixed-integer optimizer can select *different quantities for different tokens* and *a separate limit cap for each token*. It should weakly dominate a strong first-level, equal-quantity subset-search baseline on the **exact same conditional worst cash-flow objective**. This is a modeling/coverage hypothesis, not a proposition that current markets contain profitable offers.

**Adopt further development only if** (1) 100% of bounded randomly generated small cases match an independent exhaustive integer oracle; (2) every chosen asset quantity is fully coverable at its chosen limit in the supplied snapshot; (3) exact integer worst-state cash-flow is nonnegative; (4) price limit re-evaluation never uses VWAP as maximum debit; and **later** (5) genuine time-aligned and rule-reviewed market data shows incremental net economic value after multi-leg failure scenarios and capital lockup. Abandon as a production proposal if requirements 1–4 fail; HOLD until 5 is measured.

## Mathematical model

Each input asset `i` supplies a nonempty strictly sorted buy book and a declared payout `h[i,s]` for **each** state `s`. Each price cap `r` has a cumulative available quantity `D[i,r]`, price `p[i,r]` and assumed per-unit worst-case fee `f[i,r] = max(fee upper of levels <= r)`.

Integer quantities `q[i,r] >= 0` and binary tier selectors `z[i,r]` obey `q[i,r] <= D[i,r]*z[i,r]` and `sum_r z[i,r] <= 1`. All amounts are `int` price ticks and **whole shares** (fractional shares, minimum trade sizes, fixed fees and SELL/Convert require later modeling). The solver maximizes `t >= 0` subject to:

```
t <= sum_i,r (h[i,s] - p[i,r] - f[i,r]) * q[i,r]   for every stated state s
sum_i,r (p[i,r] + f[i,r])*q[i,r] <= cash budget
sum_{i in venue v,r} (p[i,r]+f[i,r])*q[i,r] <= venue budget[v]
```

This deliberately charges *every acquired share at that share's selected worst limit*, not at the historical VWAP. The optimizer can select no trade. It uses SciPy HiGHS MILP over floating internal coefficients **only to propose integer quantities**. After solving, a separate integer-only path recomputes actual selected quantities, the worst state payout, all costs, funding, limit coverage, and the observed snapshot's best-ladder-walk estimate. Inconsistent candidates are rejected, never promoted to certificates. Integer verification is still **conditional on the supplied payout states and fee premises**.

**Important:** individual per-share `fee_upper` inputs must genuinely bound any match under the chosen limit. A market requiring per-match rounding without a verified upper bound is **ineligible for the trusted cash-flow classification**. This specimen does not derive, prove or calibrate those bounds from venue rules. Nor does it model queue priority, latency, refund clauses, oracle disputes, settlement time, spread, market impact, atomic multi-leg execution or real account capital. The JSON key `coverage=ASSUMED_STATES_ONLY` is mandatory so no code can silently relabel it as a certified market rule set. Output authority is always `RESEARCH_PROPOSAL_ONLY`.

## Reproduce locally

Prerequisites: Python >= 3.12; optional research-only `numpy==2.3.5` and `scipy==1.17.0` (tested locally). **These are not application runtime dependencies.** No credentials or venue requests are performed.

```sh
python -m unittest discover -s research/payoff-economics/s1 -p 'test_*.py' -v
python research/payoff-economics/s1/maximin.py research/payoff-economics/s1/fixtures/unequal-quantities.json
python research/payoff-economics/s1/benchmark.py
```

The regression suite checks all-outcome NO baskets, unique single-limit orders, fee/venue/budget bounds, unusual quantities, 75 random small MILP problems against full integer enumeration, 75 independently fair-priced no-arbitrage models, and injection of an adverse exception state. `synthetic-benchmark.json` comes from a deterministic seeded simulation comparing 150 unrelated **synthetic** models; it must never be reported as realized revenue or inferred live fill probability.

## Relation to P0 and boundaries

The original P0 compiler only enumerates up to four YES/NO listings, and the fixed-point verifier is the sole source of application certificates. This experiment doesn't claim to replace either or to have independently verified its `ASSUMED_STATES_ONLY` truth table. It is intended to test whether flexible integer quantities and limit-aware costing are materially valuable **before** adding production solver dependencies or services. The strong comparator is *all* top-of-book equal-quantity subsets, not just two-leg arbitrage, so improvements cannot be ascribed merely to expanding the number of candidate asset subsets.

Stop/selection criteria: `HOLD` pending observed net economic benefit and payoff interpretation audit; `PARTIAL_ADOPT` if only the exact discrete optimizer design is useful; `ABANDON` if the baseline matches realistic-market opportunities or simulated capital lock renders them uneconomic. No silent merge into `main`.
