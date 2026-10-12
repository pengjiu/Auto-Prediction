# S4 — source evidence and out-of-window replication

This optional research slice builds on PR #6. It does not change the venue parser, exact verifier, numerical solver, fee qualification or execution authority. All network methods are anonymous GET; no model API is invoked. The completed observation and actual test provenance are in [OBSERVATIONS.md](OBSERVATIONS.md).

## Scope

The specification in `plans/source-evidence-validation.md` was committed before the fresh quotes. Fixed BTC dates October 13–16, 2026; above 82k/84k, ranges 80–82k/82–84k; two windows of 12 rounds, five-second target interval, minimum sixty-second gap. Missing members cannot be substituted and the denominator stays 96 date/window/round attempts. Different future observation dates and separated short windows are not statistically independent market samples or four elapsed days of observation.

`source_audit.py` uses four literal anonymous URLs: official Binance Spot REST documentation, Polymarket resolution documentation, UMA yes/no methodology, and one fixed historical BTCUSDT 1m two-candle request around October 11 noon ET. It permits no redirects, retries, proxy or alternative source, and caps response bytes. Both adjacent candles are validated by integer timestamps and exact decimal OHLC if returned; the code never chooses one as the contract final value. In this actual run Binance returned HTTP 451, so the probe is NOT_ESTABLISHED, not a successful observation of two candles.

## Facts are not contract guarantees

Primary sources retained and reviewed:

- https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data
- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- https://docs.polymarket.com/concepts/resolution
- https://docs.uma.xyz/verification-guide/yes_or_no

Binance specifies kline open/close fields and UTC request bounds. That does not on its own prove which API interval matches a particular contract's named UI candle. Contract-specific ancillary data, final-value revision cutoff, fallback, clarification, oracle outcome, fee debit and collateral timing remain unresolved. No success status or generic document removes these assumptions. Equal prices in adjacent source intervals would not establish identical intervals either.

Documentation fetched after an older trading observation is post-hoc evidence, not information available at that earlier decision time. Raw byte hashes bind records to retained data, not proof of authenticity if an attacker can rewrite the entire evidence chain. Preserve the independent artifact digest and source commit.

## Code boundaries

- `source_audit.py`: fixed-URL source collection and independent raw receipt replay; contract and execution authority always false.
- `campaign.py`: immutable expected population, two bounded windows and analysis using the existing TypeScript source compiler, S1 and same-depth S2 controls. No duplicated payoff inference.
- `s3/capture_real.py` and `s3/analyze_real.py`: an explicit bounded protocol parameter. Historical original captures remain reproducible with the original protocol; future collection rejects past target dates. Replay does not trust a captured manifest to define its own sample universe.
- Tests cover positive controls, both DST transitions, incomplete/future/misidentified candles, decimal precision, tampering, HTTP failures, changed populations and missing entire windows. Synthetic tests are not network observations.

Output is conditional gross floor, exact price witness, or exclusion. Repeated snapshot floors are never added up as captured PnL. Source API failure remains NOT_ESTABLISHED; missing market observations are exclusions, not no-arbitrage witnesses.

## Reproduce

From the repository with its locked Node/pnpm dependencies and optional NumPy/SciPy installed:

```sh
python -m unittest discover -s research/payoff-economics/s4 -p 'test_*.py' -v
python research/payoff-economics/s4/campaign.py analyze --root /path/to/original/capture --output /new/path/results.json
```

Raw archive metadata is in `evidence/observation-summary.json`. Verify the external ZIP digest before inspecting or extracting it. The archive contains the exact capture source and full results. Output files are create-only. Do not overwrite original evidence or historical results.

The collection command is deliberately separate:

```sh
python research/payoff-economics/s4/campaign.py capture --root /new/path/capture
```

After the first target date has passed, a newly preregistered protocol is required, not a silent date edit. The initial bounded run was explicitly triggered by commit prefix `capture(source-evidence):`. The final dedicated workflow is **manual-only**; ordinary fixes, PR events and merges do not capture. The shared qualification workflow includes S4 tests alongside existing gates. No recurring schedule is installed.

## Actual verification boundary

The local container and Python tools failed with infrastructure ClientError, including a minimal echo. **No new local testing is claimed.** Clean GitHub Actions run 38253958332 completed full check/build, 1,144 Node tests, S1 16, S2 32, S3 24, S4 19, P0 offline 43 and patch tools 8, then recompiled the original archive and collected/analyzed the new samples. Focused/offline tests overlap workspace coverage.

Both new windows admitted every planned group snapshot but found no positive gross basket and no S1 improvement over same-depth controls. This is evidence about a narrow conditional BUY-only sample, not all-market efficiency or a failed proof of every possible strategy. Actual fee debits, broad LLM semantic automation and profitability remain unqualified. Main and PR #6 are unchanged by this stacked candidate.
