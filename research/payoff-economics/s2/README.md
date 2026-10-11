# S2: Public-data economic audit, not a trading strategy release

This isolated research mutation is stacked on S1 (`e5109f5...`). It does not
change production code, fee admission, certificate authority, credentials,
orders, signatures, approvals or funds. Decision: **HOLD**. A short pilot is
neither a sustainable profitability test nor evidence that all markets are
efficient. Realized PnL is intentionally `null`, never a sum of snapshot edges.

## Run locally

Use Python 3.13, NumPy 2.3.5 and SciPy 1.17.0 as optional research dependencies.
From the repository root:

```sh
python -m unittest discover -s research/payoff-economics/s1 -p 'test_*.py' -v
python -m unittest discover -s research/payoff-economics/s2 -p 'test_*.py' -v
python research/payoff-economics/s2/analyze.py \
  /path/to/downloaded/public-evidence --output /tmp/economic-report.json
```

On a host able to reach official anonymous endpoints, a new bounded capture is:

```sh
python research/payoff-economics/s2/capture.py \
  --output /tmp/new-public-evidence --cycles 12 --interval 5
```

The output directory must not exist. No wallet, API key, account or credentials
are requested. Only approved public GET paths and restricted redirects are used.
A response above the byte limit is retained as a flagged prefix, never parsed as
a complete catalog. The original complete bytes for successful responses, HTTP
status, URL, request and receive times, monotonic duration and SHA-256 are saved.
Analysis reads these files offline and checks their identities before use.

## What the exact price witness proves

For declared states w, nonnegative positions q, unit payments h_i(w), and asks
 a_i, construct rational weights p_w >= 0 with sum p_w = 1 and

    sum_w p_w h_i(w) <= a_i   for every purchasable asset i.

Then min_w sum_i q_i h_i(w) <= sum_w p_w sum_i q_i h_i(w)
<= sum_i q_i a_i. Thus strictly positive guaranteed BUY-only profit is
impossible at these or higher prices before nonnegative fees. The witness is
independently checked with exact `Fraction` arithmetic. Its weights are a
mathematical separating device, not forecasts of real event probabilities.

This proves nothing about other quotes, future states omitted by the model,
shorting, making, protocol conversions, atomic execution or semantic correctness.
A missing witness also does NOT prove arbitrage. S1 separately proposes baskets.

For ordinary complements the model assumes two same-condition payment states.
For small negative-risk groups it assumes exactly one member wins. The event
membership and rule hashes are audited, but this is **not** independent onchain
completeness or natural-language settlement certification. Special outcomes and
independent oracle decisions remain unresolved model risk. The before/after
rule equality filter is a retrospective audit condition, not information that
would have been available at the earlier decision time.

## Strong comparisons, not favorable comparisons

All proposers receive the same whole-share, <=8-level, <=10,000-share-per-token
books, declared states and 1,000-unit account budget. S1 is unchanged.

- `equal_size_frontier`: the original first-level/all-subset/equal-size objective,
  solved analytically in quantity instead of looping over every possible share.
  Sixty small randomized cases match the original enumeration exactly.
- `equal_size_depth_frontier`: all-subset/equal-size optimization using ALL the
  same S1 depth tiers and conservative full-quantity-at-limit cost. Eighty small
  random cases match an independently computed exhaustive equal-size oracle.
- S1 MILP: permits unequal asset quantities and selected limits. Its result must
  not be worse than either baseline under the identical research model.

The pilot's apparent S1 advantage over first-level scanning **vanishes against
the same-depth equal-size control**. Do not call deeper order access a new
unequal-quantity alpha. Read `observations-2026-10-11.md` for actual sample scope.

## Gross diagnostics versus fee/execute qualifications

S1 runs here with zero fees ONLY to expose gross opportunity upper diagnostics.
Missing fees are NOT inferred to be zero. Nonzero fee metadata is marked
`MATCH_FEE_BOUND_UNQUALIFIED`. A separate exact-rational scenario applies the
explicit r*p*(1-p) formula without match-level rounding. Its negative result
is a statement about that specified model, not an independently certified
charged amount. No candidate obtains production fee or payment certification.

A plan below the native minimum order size is reported as execution-blocked.
FIFO/queue position and sub-cycle market states are unavailable. The next
captured book is only a sampled delayed scenario, not exact latency replay.
Old limits are retained; no later prices are used in the original decision.
Quote generation times predating that decision are rejected for delayed replay.

Accounts are processed chronologically across families, with one in-flight
sample per strategy. Debit and inventory are committed together only after
validation. No repeated family attempts, reused unchanged book depth, fictitious
settlement or capital recycling are allowed. These accounts are gross-only
hypothetical controls; fees can make a hypothetical purchase inadmissible.
Separate exhaustive FOK-leg failure masks show possible residual terminal loss,
not estimated probabilities or realized losses. Cancellation never undoes fills.

## Validation and evidence boundary

Local pinned Node 22.22.1 / pnpm 11.13.1 workspace checks, build and 1,077 tests
passed. S1 11 tests and S2 21 tests passed, including 300 rational witness models,
60 first-level baseline comparisons, 80 independent depth-oracle comparisons,
raw-byte tampering, unknown fees, stale books, false fills, transactional debit
and chronological in-flight account controls. No test relaxes production guards.

The local environment cannot resolve public DNS. Public capture used an isolated
GitHub Actions runner; exact downloaded bytes were analyzed and tested locally.
Relocated pinned pnpm dependencies required disabling its pre-run auto-reinstall
(`pnpm_config_verify_deps_before_run=false`), not disabling type/tests/build.
The initial failed automatic network reinstall is retained in local test logs.

Capture artifacts have finite GitHub retention. Keep the downloadable raw
archive and verify its digest before reproducing a historical run. New captures
will naturally have different prices, clocks and results. Measured solver
runtimes in reports are not deterministic financial data.
