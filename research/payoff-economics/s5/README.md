# S5 — price-blind temporal relation research

This slice changes the relationship class, NOT the optimizer. Previous BTC
closing-price studies found no increment. Here complete source-reviewed contracts
refer to a qualifying occurrence between their own market creation and a deadline.
A later deadline with a later start is not a superset. No historical event is
assumed absent simply because it would help create an arbitrage.

## Mathematical boundary
For n <= 6 inclusive integer-time intervals, form atoms where interval membership
is constant. A temporal history is an arbitrary finite set of qualifying event
times. Its n-bit outcome is the bitwise OR of the occupied atoms' membership
signatures. OR-closure starting at zero enumerates exactly all achievable outcomes,
with one witness history per outcome, in at most 2^n states. This is not a model of
only the first event: multiple distinct enactments, announcements or qualifying
occurrences remain possible. Union over unresolved boundary readings is conservative.

Example [0,10], [2,12], [4,14]: no pairwise containment; B implies A OR C because
B's interval is covered by their union. Outcome 010 is impossible, but 101 is
possible from two occurrences. A first-occurrence-only implementation would
incorrectly remove 101. This is a structural use of elementary interval algebra,
not a claimed new theorem or world-leading algorithm.

## Actual source review, not model-provider automation
`reviewed-scopes.json` pins complete source text and native identities from the
retained October 11 catalog. `seed-source.json` contains explicitly labelled
semantic-field extractions, NOT raw network responses. The in-session assistant
read the complete qualification and exclusions before looking at fresh prices.
No independent legal/semantic reviewer or model-provider call is claimed.

Ohio and Texas clauses explicitly distinguish enactment from effectiveness,
exclude executive/local actions, and preserve a qualifying enactment despite
later repeal. Their internal substantive definitions remain an assumed common
qualification predicate; checking text identity does not prove those definitions
are unambiguous or that separate oracles must agree. A territorial-control
state-at-deadline and unspecified-start bankruptcy description were rejected
as candidates for this OCCURS_IN scope. We do not classify every `by` title as
an occurrence contract.

`export.ts` consumes complete original event and member descriptions against the
trusted reviewed scopes, validates original creation precision, named ET deadline,
all native identities and availability, and exposes intervals with explicit
assumptions. It does not modify or bypass the production exact-admission compiler.
Python derives interval states, never reinterprets prose or trusts a caller's
arbitrary payment table at the public capture/replay entry point.

## Fair controls and remaining risks
The same S1 solver, exact integer validation and same-depth S2 equal-size baseline
use identical books, native minimum orders, budget and payment states. A separate
pairwise-only state control isolates semantic-information gains from algorithmic
gains. Synthetic high-order control gives positive information gain and ZERO
solver gain. This is not actual profit.

Gross floors refer to terminal undiscounted payments after the latest deadline.
Multi-year capital occupation and different maturities, financing, source metadata
meaning, ancillary/clarification evidence, independent settlement and actual fee
debits remain unqualified. Independent 0/0.5/1 settlement stress and partial-leg
acceptance stress are separately reported. No realized PnL, inventory or fills
are invented; repeated snapshot opportunities are not summed as revenue.

## Reproduce
With the unchanged workspace lockfile and existing optional NumPy/SciPy:

```sh
python -m unittest discover -s research/payoff-economics/s5 -p 'test_*.py' -v
packages/control-plane/node_modules/.bin/tsx research/payoff-economics/s5/test-export.ts
python research/payoff-economics/s5/campaign.py analyze --root /path/to/original/capture --output /new/path/result.json
```

Capture is a separate explicit command. The preregistration fixes 3 families,
4 rounds, 18 tokens maximum, no replacement and a denominator of 12. Every source
is read before quotes and again after the window; sampled equality does not prove
continuous rule invariance. Shared S2 receipt/raw-byte/native/time validation is
reused. HTTP or missing data is exclusion, not a no-arbitrage witness. Preserve
the original ZIP digest externally; hashes alone cannot authenticate a consistently
rewritten evidence chain. Files are create-only at the public output boundary.

Selection: research candidate only, no new service/SDK/production dependency,
no LLM-provider call, no trading authority and no automatic merge.

## Observed completion
The preregistered real capture is complete: 3 full scopes, 12/12 admitted snapshots,
2 scopes with a genuine conditional higher-order cover, but zero positive gross
baskets and zero semantic/solver increments. Four rounds per scope share the
same numeric model; they are not independent opportunities. See `VALIDATION.md`
and `observations.json` for exact scope, failures, clocks and remaining assumptions.

Replay original bytes without network:
```sh
python research/payoff-economics/s5/replay.py --output /new/path/temporal-result.json
```
The smaller committed ZIP retains every capture byte; `fixtures/index.json` binds
it to the original full Actions artifact and inventories every file. This is not
a new capture, semantic certificate or actual trading result.
