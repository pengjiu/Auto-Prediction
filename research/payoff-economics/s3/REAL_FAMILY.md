# Full real Binance-close descriptions — conditional research

Date: 2026-10-12. Parent: merged PR #5, main
`239e91a0e2e2f76e2e4d5be2cd03aa90db6582d5`.
The v3 exact semantic gate remains unchanged. This adapter does not assert
TOTAL_EXACT, cannot issue a certificate and never enables a real order.

## What became usable

Two complete Polymarket descriptions have a bounded venue-owned interpretation:
BTC/USDT Binance one-minute final Close at noon America/New_York, either strictly
higher than a title threshold or within a title price bracket. The entire four
paragraphs are consumed, along with event and market question/date, native token
identity, group label and source URL. No original text is rewritten into the
synthetic grammar. Current support is CTF/v1; new protocols or altered text fail
closed. This is one deliberately narrow adapter, not a general LLM parser.

The actual full descriptions refer to the title for date/threshold, and include
source selection, pair exclusivity, source precision or higher-bracket boundary
convention. Interval endpoints use actual adjacent bracket evidence. An adjacent
label inconsistent with its full question is rejected; ambiguous terminal
`greater than K` versus inclusive higher-bracket wording is deliberately not
supported. Source quote unit USDT/BTC is separate from assumed common collateral.
Named-zone noon validation covers daylight saving changes, rather than assuming
UTC-4 year-round.

The normal interpretation does NOT settle: missing source fallback, revision
cutoff, exact candle timestamp convention, future clarification/oracle override,
independent settlement, collateral timing, refunds or token/counterparty risk.
These are explicit output unknowns, not discarded paragraphs. General policy
bytes are retained but are not a proof of all applicable venue policy.

## A real endpoint trap

Let A = Close > 82,000, B = Close > 84,000, R = 82,000 <= Close < 84,000.
The plausible identity A - B = R is false at BOTH endpoints:

| Close | A | B | R |
|---|---:|---:|---:|
| 82,000 | 0 | 0 | 1 |
| 83,000 | 1 | 0 | 1 |
| 84,000 | 1 | 0 | 0 |

A point outcome must not be deleted because a statistical model assigns it zero
probability. The numerical matrix keeps all endpoints and open cells.

## Source-to-economics route

`export.ts` dispatches an explicit real-source schema to a TypeScript exporter
that re-reads whole original JSON response bodies and invokes the venue parser.
There is no Python reinterpretation of natural-language rules and no ingestion
of a caller-authored payoff table. Raw SHA-256, source URL, native identities,
complete rule identity and capture times are bound. Four contracts yield seven
normal cells and 81 independently resolved 0/0.5/1 stress combinations. The
independent binary corners already bound complementary fractional payoffs, but
not refund/settlement timing or collateral failure.

The Python CLI uses the existing S3 validator, S1 MILP and S2 same-depth/equal-size
control without changing their authority. Every original quote body is verified;
request URL, token, condition, minimum order size, tick and common decision-time
freshness are checked. Gross-only results and unrounded nominal curve-fee
scenarios are separately labeled. Actual fee debits are still NOT certified.
A rational state-price witness is searched numerically, then independently
checked exactly. Such a witness rules out positive guaranteed BUY-only gross
profit for the selected assets and stated cells even before nonnegative costs;
it is not a probability forecast or a proof of global market efficiency.

## Predeclared real observation, not synthetic input

Design was committed before the new capture in `plans/real-binance-family.md`.
Select two observation dates (October 12/13), above 82k/84k and ranges 80–82k /
82–84k, with no price-based substitutions. Eight bounded rounds were captured by
anonymous public GET on a GitHub Actions runner. Analysis runs locally offline.

- Run: 38206964619; source commit c5d8e09e63679574dd2c2adb811506e9a6f77e2c.
- Artifact: 11726789293; original ZIP SHA-256
  `fac0590be30054a37d85775764d75bfe1fe59c6cc9d6ad533d02f307536f6e7a`.
- 138 responses, zero HTTP errors, 8 selected contracts / 16 native outcome tokens.
- Window: 2026-10-12 05:12:54.564389276–05:13:02.788104303 UTC, about 8.224 seconds.
  This is NOT two observation days of continuous collection or 16 independent
  opportunities. Each date-group is sampled eight times in this one short window.
- Definitions are fetched again afterward; relevant identities match. HTTP cache
  Age headers (145–279 seconds) are reported. Equality of sampled cached replies
  is NOT proof that no intervening rule/clarification change occurred.
- Within-group acquisition spans are about 377–430 milliseconds; none is atomic.

The entire small original artifact ZIP is retained in `fixtures/real-binance`;
it is not a reserialized or regenerated raw capture. Two original event responses
are also readable as JSON fixtures. Their checksums and original request metadata
are in `manifest.json`. The explicit Markdown policy wrapper in UNIT TESTS is
synthetic; the real CLI uses captured original policy bytes.

## Observed result

Both normal-path source groups were supported without dropping any paragraph.
All 16 group/round snapshots passed the declared data gates. S1 and the same-depth
control selected no-trade in all 16. Exact rational gross price-consistency
witnesses verified for all 16; there were zero positive gross candidates and zero
S1 increments. Independent-resolution stress also selected no-trade. No partial
candidate exists to execute; partial-fill report is null, NOT a claim that actual
partial execution is safe. These results concern the selected inputs only.

Captured nominal curve rate was 7/100 for each selected contract. Nominal fee
witnesses also verified, but no real per-match rounding/debit qualification is
claimed. No funds moved; `realized_profit=null`, `model_calls=0`.

## Validation and fixes during this experiment

Local supported environment: Node22.22.1 / pnpm11.13.1 / TypeScript5.9.3;
Python3.13.5 / NumPy2.3.5 / SciPy1.17.0. Existing lockfile is unchanged. DNS remains
blocked locally; restored dependency bytes match the prior lockfile. Remote CI
must separately do a clean frozen-lockfile install.

- Full check/build/test PASS: 1,140 Node tests (28 root + 1,112 workspaces).
- Real-rule focused tests: 27, including independent rational endpoint checks.
- S1 16, S2 32, S3 15, offline P0 43, patch tool 8: all PASS. Some overlap.
- Actual PUBLIC CLI recompiled every before/after real definition, checked all
  raw bytes and analyzed all 16 rounds successfully. The checked replay command
  also asserts expected admitted counts; a successful process exit is not enough.
- Initial failures retained: wrong local zod ownership (moved schema inside venue
  package), over-restrictive range slug assumption (matched actual complete slug
  forms), and Markdown policy misread as JSON (use verified original text bytes).
  The first public CLI exited0 with two recorded blockers; that was NOT economic
  acceptance. Dedicated regression added and the entire final suite rerun.
- URL/native identity binding, adjacent-question mismatch, terminal ambiguity,
  changed rule/policy, DST, added/deleted text, mixed halves, zero-profit controls,
  and raw corruption are tested. No fee or exact-semantic check was weakened.

Final local log hashes and original-data interpretation are in
`evidence/real-family-results.json` and `evidence/real-family-observations.json`.
Remote CI receipt belongs in the PR after actual completion, not inferred here.

## Reproduction

```sh
pnpm install --frozen-lockfile
pnpm run check && pnpm run build && pnpm run test
python -m pip install --only-binary=:all: numpy==2.3.5 scipy==1.17.0
python -m unittest discover -s research/payoff-economics/s3 -p 'test_*.py' -v
python research/payoff-economics/s3/replay_real_fixture.py --output /tmp/new-real-report.json
```

The replay uses no network and refuses to overwrite an existing output. The
manual collector remains pinned to this predeclared October 12/13 experiment;
calling it at a later date does not turn it into a new protocol or a continuous
monitor. A new observation universe/date requires a new recorded protocol.

## Decision

PARTIAL_ADOPT candidate for a real, full-text, source-bound conditional research
path. HOLD general automatic admission, semantic completeness, LLM discovery and
profitability. This creates nonzero NORMAL-PATH coverage for one genuine family;
it does not change the earlier generic exact-grammar census or solve all events.
No larger solver, new service, npm dependency or model-call pipeline was added.
The next useful evidence is independently reviewed exceptions and broader,
predeclared observations, not relaxing exactness to force positive profits.
