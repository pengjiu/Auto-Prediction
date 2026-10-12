# Resumed real-family audit and validation — 2026-10-12

## Recovered source and authority
PR #5 is already merged at main `239e91a0e2e2f76e2e4d5be2cd03aa90db6582d5`.
The interrupted real-family branch was at `72c11d1d595b16084139e5847a56c1f609cc811e`;
its last commit was a temporary publication workflow, not applied source fixes.
This continuation uses the source/history artifact from `a20924378f7e45deb452db1924d4486e39948b9f`,
ZIP SHA-256 `6f7ecaed70e4b1f77688ddfba5707c2dddccebca2f16f285e8d990e021a2b4dd`.
No production credential, network capture, LLM call, order, signature or fund use.
PR #6 remains a separate conditional research candidate, not an automatic merge.

## Reproduced before repair
The prior 27 real-rule tests and 15 S3 tests passed. Four newly added TypeScript
cases then failed: changed threshold slug, nonnumeric slug, different range
endpoints in the selected slug, and a contradictory adjacent-bracket slug.
Five new Python test methods produced 16 failed rejection subcases involving
future/stale/missing policy clocks, unchecked native quote URL, dropped or
repeated date-groups, changed declared parameters and substituted selections.
Failures and subsequent passing logs are retained with the handoff artifact.

## Repairs
- Parser v2 matches exact rational slug shorthand against complete question
  thresholds and endpoints; both selected and adjacent listings are checked.
  Slugs enter rule identity; unknown syntax fails closed. Original full rule
  paragraphs remain intact. This is conditional interpretation, NOT TOTAL_EXACT.
- The shared bridge validates original quote URLs itself. Source AND policy
  receipts must exist by the common decision and satisfy the unchanged 15-minute
  receipt-age limit. Receipt freshness does not prove policy semantic coverage or
  HTTP cache freshness; original cache-age limitations remain.
- Collector and replay use ONE deterministic population selector. Replay rebuilds
  selected event/market/token identities from original definitions and the
  predeclared configuration. Prices never select replacements. Unknown groups,
  altered selections or extra round/token labels are rejected.
- All declared rounds are retained in the denominator. Missing observations and
  source failures remain exclusions, not implicit no-trade/no-arbitrage results.
- Temporary source/publication workflows are removed. The normal qualification
  workflow and manual-only capture workflows remain. No dependency or lockfile
  change; no replacement of original historical evidence.

## Actual local qualification
Node 22.22.1, pnpm 11.13.1, TypeScript 5.9.3; Python 3.13.5,
NumPy 2.3.5, SciPy 1.17.0. Complete source restored with its Git history.
Pinned dependencies restored from the existing lockfile archive because the
local container cannot resolve GitHub/npm. Tests execute locally; remote CI
must separately confirm a clean frozen-lockfile installation.

- Full check, build and test: exit 0. **1,144 Node tests: 28 root + 1,116 workspace.**
- S1 16, S2 32, S3 24, P0 offline 43 and patch tools 8: all passed.
- Focused 31 real-rule tests overlap the full suite; counts are not all additive.
- The actual source-to-economics CLI recompiled the original complete real source
  and replayed all 16 snapshots: 16 exact gross witnesses, zero gross-positive
  proposals, zero same-depth increment, realized PnL null.
- On a clearly marked TEST COPY with all last-round quote receipts removed,
  full recompilation/replay reports 16 attempted, 14 admitted, 2 excluded. This is
  a missing-data stress, not a new market capture. Original bytes are unchanged.

## Economic boundary and disposition
This rechecks the same 8.224-second observation window, not a new independent
sample or current market survey. It does not overturn the zero-increment result.
Normal-path support for one real family is usable; independent settlements,
source fallback/revision, actual fee debit bounds and profitability remain
unqualified. PARTIAL_ADOPT candidate for correctness and reproducible research;
HOLD unconditional semantic authority, LLM automation and real trading.

Current local log hashes and replay summaries: `evidence/resume-results.json`.
Remote source identity and CI receipt will be recorded on PR #6 after they are
observed. This file does not presume successful publication or remote tests.
