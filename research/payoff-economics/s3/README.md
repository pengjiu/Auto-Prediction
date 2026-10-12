# S3 — semantic binding and source-recompiled economic bridge

This is an isolated correctness/coverage experiment, not a profitable strategy.
The original six semantic-audit failures were reproduced on main `2a473d11`.
The v3 compiler replaces keyword overlap as exact-admission authority. It does
not solve arbitrary natural-language interpretation or certify actual resolution.

## What changed

- Consume the **entire** supported Yes-if / otherwise-No envelope. No ignored
  trailing paragraphs, exceptions or extra necessary conditions. Whitespace and
  supported envelope spellings can vary; identifier and source URL case is kept.
- Whole-clause identity is opaque. It preserves an entire AND/OR condition but
  does not infer relationships between different opaque clauses. Explicit
  predicate negation and `it is false that ...` invert the settlement table.
- For numeric conditions, bind the comparison, exact decimal, unit, subject,
  metric, quoted source and exact UTC interval. Supported comparisons: exceeds /
  greater than, at least, below / less than, at most / does not exceed, equals.
  Celsius and degree-C spellings are aliases; Fahrenheit is **not** converted.
- Structured THRESHOLD predicates use `comparison`, `threshold` (unit required),
  and optional `source` parameters, with the metric in `verbPhrase`. Unknown or
  repeated parameter names and non-exact intervals cannot be ignored.
- Linked but missing/truncated venue policies, ambiguity, stale native evidence,
  and modified artifact hashes block exactness. Previously bound predicates are
  downgraded on rejection. The compiler identity changes, and active server
  routing no longer falls back to old projections pinned by a checkpoint.
- The shadow-hypothesis consumer now uses **listing truth after projection**, not
  world-predicate truth, to select complementary legs. This downstream inverse
  mapping defect was independently reproduced before fixing it.

## Narrow research route (not the general Agent product)

`export.ts` rebuilds the corpus and ontology and recompiles source predicates.
It selects 2–6 admitted numeric listings with the SAME subject, metric, unit,
explicit source and UTC observation interval. It neither imports arbitrary LLM
truth tables nor trusts stored EXACT labels. Distinct native token IDs are
required. It exports mixed YES/NO payments using endpoints and open intervals,
with arbitrary-precision rational representatives. Equal-threshold conditions
share cells. Current source recompilation detects even a rehashed altered export.

The nominal payment matrix assumes a common collateral unit, common observation
and consistent resolution. This does **not** prove that separate venue decisions
are coupled. Every export additionally includes independent binary resolutions
and all-half settlement as a separately labeled stress matrix; this is a useful
stress, not a claim to enumerate all real exceptional resolutions.

`bridge.py` invokes the TypeScript compiler itself, checks retained raw GET bytes
through the existing S2 evidence reader, binds requested/native tokens, and uses
existing S2 clock, book, minimum-size and tick checks. Rules must have been
received by the decision instant and at most 15 minutes earlier. It calls the
existing S1 optimizer and the same-depth equal-share baseline on identical
assumed states, depth and capital, then runs exception and partial-fill stresses.
Unknown actual fees remain `BLOCKED_UNQUALIFIED_FEES`; reported floors are gross
conditional diagnostics, never net profit, receipts or fills. It does not sign,
trade, contact a model or use network access. Reports use exclusive creation.

## Reproduction

Install the existing frozen pnpm lockfile and optional NumPy 2.3.5 / SciPy 1.17.0
research wheels. Node 22.22.1 and Python 3.13 are the qualified environment.

```sh
# Positive path on explicitly synthetic rule/LLM-output fixtures, not real trades
packages/control-plane/node_modules/.bin/tsx \
  research/payoff-economics/s3/export.ts \
  research/payoff-economics/s3/fixtures/synthetic-source.json /tmp/compiled-payoffs.json
python -m unittest discover -s research/payoff-economics/s3 -p 'test_*.py' -v

# Real research inputs: exact source predicates plus original S2 response archive
python research/payoff-economics/s3/bridge.py \
  --source source.json --evidence-root public-evidence \
  --labels token-to-request-label.json --output new-report.json
```

`source.json` carries the corpus builder inputs, the bounded predicate artifacts,
selected listing refs and optional retained venue policy evidence. The source
predicates can originate in the existing LLM path, but that model was **not**
called in this iteration. No fabricated external-model invocation is recorded.
Sources, predictions and quotes must be actual inputs; unsupported rules halt
before an opportunity result. Reusing the example with new titles does not turn
it into a valid real-world contract model.

## Evidence and honest completion boundary

The six original negative cases now reject or invert correctly; positive control
and supported numeric cases remain admitted. A mock threshold family yields the
same gross floor for S1 and the same-depth baseline; independent resolutions erase
that opportunity. These inputs and books are intentionally **synthetic**.

A retrospective syntax-only census used the hash-verified follow-up catalog
(manifest `2675989c14a6f014707ca65fe6cf4119d5ae4c94b2812fdb336cb0cc882c5d88`).
All **16,611 unique market descriptions** were outside the complete supported
rule-envelope dialect. This is NOT 16,611 LLM relation reviews, opportunities,
liquid assets, or no-arbitrage proofs. It establishes a concrete coverage gap:
real rules contain source fallback, rounding, cancellation and extra clauses.
We did not trim those clauses or relax precision to create a positive result.

**PARTIAL_ADOPT candidate:** the semantic correctness repair and tested research
plumbing have value; real-market admission, independently reviewed settlement
coverage, live LLM integration, qualified fees, and economic value remain HOLD.
Next build one real rule-family adapter with complete exception/source handling
and independent adjudication evidence, not a larger solver or a permissive regex.
No automatic mainline merge is implied by test success.
