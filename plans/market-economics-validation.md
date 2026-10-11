# S2: Bounded public-market economic validation

Date: 2026-10-11. Parent: S1 e5109f5c4fcbeac4928d9109cc6b040efee893fd.
Branch: codex/mutation-market-economics. Decision: HOLD pending observations.

## Proposition
S1 passed synthetic correctness tests, not a market profitability test. This
mutation replaces speculation about residual alpha with a reproducible, bounded
public-data experiment. It adds research code only; production verification,
credentials, orders, signing, approvals and funds remain unchanged.

## Observation protocol (fixed before seeing results)
- Anonymous GET requests only to official Gamma, CLOB and documentation hosts.
- Retain response bytes, status, requested URL, request/receive UTC nanoseconds,
  monotonic duration, HTTP Date and content hash. Never substitute a reference
  price for an absent order book. Non-success and unknown schemas are evidence
  gaps, not zero liquidity or zero fees.
- Discover a bounded liquidity-ranked and recent-event catalog slice; disclose
  filters and exclusions. Select ordinary binary complements and small,
  non-augmented negative-risk event groups. Capture all member definitions.
- Negative-risk grouping is a conditional modeling hypothesis, NOT independent
  semantic or onchain completeness certification. An event title cannot certify
  exhaustive outcomes. Recheck rules at the end; any changes invalidate admission.
- Record repeated snapshots of a fixed universe. A batch is not atomic. Enforce
  explicit response-time and within-family acquisition-skew limits. Server book
  timestamps do not constitute continuous sequence numbers.
- Public data acquisition may run on an isolated GitHub Actions runner because
  the local container cannot resolve public hosts. Analysis and tests run locally
  on the downloaded exact bytes. Disclose this separation, not 'local collection'.

## Economic methods
1. Exact state-price witness: find nonnegative rational state weights summing to
   one with expected payoff of every purchasable token <= its best ask. Verify
   all inequalities with integer/rational arithmetic. This rules out strictly
   positive guaranteed profit for nonnegative purchases in the stated model,
   before nonnegative fees, even with unlimited depth. No inference about other
   markets, future quotes, shorts, makers, conversions or true semantic coverage.
2. If no witness is found, that alone does not prove arbitrage. Compare original
   S1 integer/limit-cost solver and its equal-size baseline on identical bounded
   books and assumed states. Fee-free diagnostics are NOT after-fee profits.
3. Fee schedule unknown => no after-fee certification. Explicit zero-fee flags
   must be internally consistent. Nonzero curve fees stay unqualified unless
   debit asset and per-match rounding bounds have independent evidence.
4. Add all-none/exception payment states as declared semantic stresses where
   appropriate. Never pick the interpretation that makes a basket profitable.
5. Replay any candidate against later captured books, using the original limits;
   use the next observed book only as sampled delayed evidence, not exact
   millisecond execution. Assess independent leg failure paths and residual
   inventory. No cancellation can undo fills. Never sum repeated snapshot edges
   as revenue; capital/depth reservations must be shared at account level.

## Acceptance and stopping
- Raw integrity, numeric parsing, duplicate identity, zero/missing fields, stale
  or asynchronous data, unknown fee, optimistic fill and false no-arbitrage
  certificate adversarial tests must pass.
- Re-run S1 independent exhaustive tests, and full Node workspace qualification
  where complete dependencies are available. Preserve all failures and fixes.
- Report sample coverage, exclusions, assumed semantics, exact no-arbitrage
  witnesses, gross-only candidates, qualified fee results, delayed replay and
  worst partial-fill losses separately. No invented APR, capture rate or revenue.
- A short observation window can reject opportunities in that sample only. It
  cannot prove all Polymarket markets efficient or future profitability absent.
- If no positive candidate survives, preserve the negative evidence and do not
  add optimizer complexity. If none is admitted, report a data/semantic blocker
  rather than 'zero opportunities'.

## Integration
Add one research directory under research/payoff-economics/s2 and a bounded
manual/capture workflow. Use the existing S1 proposer without changing its
certificate authority. No new production service or persistent truth database.
Stack the draft PR on codex/mutation-state-maximin, never merge main implicitly.
