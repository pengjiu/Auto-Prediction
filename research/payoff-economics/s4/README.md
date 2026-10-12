# S4 — source evidence and out-of-window replication

This optional research slice builds on PR #6, not on a claimed profitable strategy. It does not change the venue parser, exact verifier, numerical solver, fee qualification or execution authority. All network methods are anonymous GET. No model API is invoked.

## What is being tested

1. Independently retain official source/methodology documents and, if accessible, the two Binance one-minute candles bracketing the previous day's noon ET boundary.
2. Reuse the complete real-rule compiler and identical S1/S2 same-depth economics for a predeclared new population: October 13–16, 2026, thresholds 82k/84k and ranges 80–82k/82–84k. Two windows of 12 rounds, target interval 5 seconds, minimum gap 60 seconds.
3. Preserve missing members, failed reads and missing windows in the original 96 date/window/round denominator. The manifest does not choose its own expected population.

The primary experiment specification was committed first in `plans/source-evidence-validation.md`. New prices must not change dates, strikes, reference data or stopping rules. If dates are not yet listed, record that gap; do not substitute more promising listings. Data acquired within this turn is still a short, correlated BTC sample. Different target dates and temporally disjoint windows are not a claim of statistical independence.

## Source facts versus assumptions

Reviewed primary sources:

- Binance Spot market data: https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data
- Original machine-readable specification: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- Polymarket resolution: https://docs.polymarket.com/concepts/resolution
- UMA yes/no verification: https://docs.uma.xyz/verification-guide/yes_or_no

The Binance API identifies klines by OPEN time and exposes both Close and close-time fields; start/end timestamps are UTC independently of the interval timezone option. This does not itself choose how a particular prediction market's named UI candle maps onto that API. The probe validates the two complete 12-field rows with integer millisecond identities and exact decimal OHLC values. It reports both candidates and never selects a contract's final price. Equal Close values also do not establish candle identity or future equivalence.

Polymarket resolution rules and UMA ancillary data, not a strategy's parser, govern the final token payments. Unknown/50-50, too-early requests, clarification and final-value timing remain separate issues. The original parser's unknown list is NOT rewritten on a successful probe. General documentation or two consistent API samples cannot prove revision immutability, fallback, per-contract ancillary equality, future oracle behavior, match-level debit rounding or simultaneous collateral redemption.

If the official source returns HTTP 403/451 or cannot be reached, record `NOT_ESTABLISHED`; do not fetch another exchange or use a proxy and pretend it is the same source. New documentation is post-hoc evidence for earlier observations, never backfilled information available at those earlier decision times.

## Implementation boundaries

- `source_audit.py`: four literal read-only URLs, no redirects/retries, capped bytes, original request/status/time/hash records; independent raw replay with contract authority always false.
- `campaign.py`: one immutable expected population; bounded collection and deterministic offline reanalysis. Reuses S3 source recompilation and S1/S2 controls, with no duplicated payoff inference.
- `capture_real.py` / `analyze_real.py`: small explicit protocol parameter. The original recorded experiment remains reproducible by its original default. New captures require future observation dates; historical replay does not.
- Current emitted records are research evidence, not signed authenticity statements. Keep the independent GitHub artifact digest and source commit alongside the capture. Raw hashes detect alteration relative to a retained receipt, not a malicious re-authoring of the entire evidence chain.
- Financial outputs are conditional gross floors and exact price witnesses. No repeated-snapshot floor summation is called PnL. No-trade in an incomplete subset is not global no-arbitrage.

## Run

From the repository with locked Node/pnpm dependencies and optional Python NumPy/SciPy installed:

```sh
python -m unittest discover -s research/payoff-economics/s4 -p 'test_*.py' -v
python research/payoff-economics/s4/campaign.py capture --root /new/path/capture
python research/payoff-economics/s4/campaign.py analyze --root /new/path/capture --output /new/path/results.json
```

These commands perform no trading. Capture is intentionally date-bounded: after the first target date passes, a NEW independently specified experiment is needed rather than silently altering this one. Output files are create-only. Original data/fixtures and historical reports must not be overwritten.

The dedicated workflow first performs clean installation, full Node check/build/test, S1/S2/S3/S4/P0 regressions and original real-archive replay. Network capture is enabled only for an explicitly prefixed `capture(source-evidence):` commit or manual workflow dispatch, never on a PR/main merge or an ordinary fix commit. There is no recurring schedule. See the run receipt for actual outcomes; code existence is not evidence of a successful run.

## Verification status at authoring

The local container and Python tools returned infrastructure `ClientError`, including a minimal echo attempt. No new local test success is claimed in this slice. Clean isolated GitHub Actions tests and actual evidence results will be reported separately after observation. Prior local tests belong to PR #6 and cannot certify new code.

Selection is HOLD for broad semantic automation and profitability; narrowly useful evidence and replay tools may be partially adopted after qualification. Main and PR #6 are unchanged by this stacked branch.
