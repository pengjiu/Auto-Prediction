# S4 resumed local qualification — 2026-10-12

This is a continuation of PR #7, not a new market observation. Original remote
S4 execution and its no-local-execution limitation remain in VALIDATION.md.
Current main and PR #6 are unchanged; no trading, keys, signatures or funds.

## Restoration and independent provenance

- Original network experiment code: 9a7d622d841bc0d8098f51de21999c80eb65437c.
- Capture artifact 11749144587 (4,981,008 bytes) was downloaded and hash-verified:
  0e495f3774c908a881475626dc333e403676a174c5b53f31771f32e8f7362e7a.
- Exact resumed source/history archive: commit 6f85f0d337b8f3978a9d66292f26ed373c698283,
  artifact 11755155065, SHA256 68c98538b766886f05ffa8319cf6f48309dcc3a8a1aa20b0e35f6b8361d6a741.
- Local Node 22.22.1 / pnpm 11.13.1 / TypeScript 5.9.3; Python 3.13.5,
  NumPy 2.3.5 / SciPy 1.17.0. The existing pinned offline dependency archive
  matches the unchanged lockfile. Local DNS is unavailable; tests and analyses
  nonetheless run as LOCAL processes. Clean online install is separately required
  in final GitHub CI, not claimed as a local network installation.

## Reproduced defects and limited repairs

1. Two numeric Kline intervals could be labelled closed when the request started
   during the later interval but the HTTP response arrived after it closed. The
   audit now checks both intervals ended before request start. This is still not
   a proof against later revisions or a choice of the contract's UI candle.
2. Missing error fields and malformed receipt objects were accepted or produced
   incidental runtime exceptions. Explicit receipt schema validation rejects them.
3. Campaign provenance and completion metadata were not consulted. The fixed
   original plan hash, configuration, authority, clocks and attempted population
   are now checked. Missing provenance excludes observations, without deleting
   declared attempts; missing completion preserves diagnostic rows but cannot
   qualify a completed replication.
4. Window overlap/separation was a summary flag only, so a repeated window still
   contributed another 48 admitted observations. Invalid intervals are now excluded.
   Backward/overlapping round request envelopes are rejected too. Worker start-gap
   measurements do not certify exact scheduler cadence, and no new statistical
   independence claim or outcome-fitted tolerance is introduced.
5. Source-file failure aborted the campaign summary. It now reports source
   NOT_ESTABLISHED while preserving valid market diagnostics and all seven
   unresolved assumptions. HTTP 451 remains a failure, never a zero Close.

## Actual local evidence

- Original 19 S4 tests passed before repair. Twelve new tests with subcases
  reproduced the gaps; before-repair log records 15 assertion failures and four
  errors. This includes new output-contract checks, not 19 distinct defects.
- Full `pnpm run check`, `pnpm run build`, `pnpm run test`: exit 0;
  1,144 Node tests (28 root + 1,116 workspace), zero failures.
- S1 16, S2 32, S3 24, S4 31, P0 offline 43, patch tools 8: passed.
  Focused/offline coverage overlaps; these are not all unique tests.
- Original S3 archive CLI: 2 source families, 16 admitted snapshots, no positive
  gross basket or same-depth increment. Original S4 archive CLI: 4 date families,
  96 attempts, 96 admitted, 96 exact conditional gross BUY-only price witnesses,
  zero positive gross baskets and zero same-depth increments.
- TEST COPY ONLY: replace window-1 with original window-0. Public S4 CLI now gives
  96 attempts, 48 admitted, 48 excluded, replication_protocol_conformant=false.
  Original ZIP and every original raw byte remain unchanged.

## Findings, not a trading qualification

The genuine windows remain October 12, 2026 13:14:45.763–13:15:42.913 UTC and
13:16:42.915–13:17:40.056 UTC, separated by 60.002 seconds. Four future observation
dates are not four days of sampling. The 96 observations share BTC exposure and
are not independent opportunities. No new network capture or LLM call occurred
in this local continuation. Realized profit remains null.

The original source probe returned Binance HTTP 451. The successful official
Binance/Polymarket/UMA documentation reads do not establish contract UI/API
mapping, revision cutoff, unavailable-source fallback, ancillary/clarification
identity, independent oracle outcomes, collateral timing or match-level fees.
The seven unknowns stay unresolved. No proxy or replacement data source was used.
A gross price witness only rules out guaranteed nonnegative BUY portfolios in
its supplied finite payment model and asks, not every strategy or real outcome.

The original capture remains an external artifact with expiry 2026-11-11;
local delivery includes the unchanged ZIP for retention, not a permanent online
archive guarantee. New report schema v2 adds bounded protocol qualification;
old v1 results remain historical and must not be interpreted as v2 qualifications.

## Reproduce

Run the unchanged root check/build/test commands and all optional research suites.
Then, on a separately extracted copy of the original artifact:

    python research/payoff-economics/s4/campaign.py analyze --root <capture> --output <new-result.json>

Do not overwrite any previous output. Local log hashes and results are in
`evidence/local-results.json`; final remote commit/CI receipt is in PR #7.
The temporary read-only source handoff workflow is removed before publication.
PARTIAL_ADOPT remains a candidate for research integrity, not an automatic merge
or a profitable strategy. The next economic decision needs distinct, independently
reviewed relationships; more rounds of the same structure alone are not Alpha.
