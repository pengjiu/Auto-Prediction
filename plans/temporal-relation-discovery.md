# S5: interval-history relations instead of repeated BTC scans

Parent: reviewed PR #7 a7944bd9. Initial preregistration committed at
5c4772e46a47b897f5174a71b39fab37af4b0220 before fresh quotes. This implementation
clarifies the same population/budget; no selection changed. Main and prior
candidates remain unchanged. No real credentials, orders, signatures or funds.

## Question and model
Can complete, price-blind reviewed clauses reveal economically useful relations
beyond same-date BTC thresholds? A later deadline does NOT imply containment when
its market was created later. Qualifying events may recur. B can be covered by A
union C with no pairwise containment. Include repeated-event counterworlds.
The solver is unchanged; compare information and numerical algorithm separately.

## Fixed source review
Three event/market groups from the hash-verified October 11 catalog:
- 255195: 3399450, 3399451, 1535973.
- 1103681: 5123848, 5123849, 5123850.
- 1103684: 5123855, 5123856, 5123857.

These concern a leadership-change occurrence and qualifying moratorium enactment
in Ohio and Texas. They are contract descriptions, not assertions about current
office-holders or enacted laws. Retain complete clauses, exclusions and reversal
rules. Full-text identity is NOT a proof of natural-language equivalence.
The in-session assistant reviewed the source; no independent reviewer, provider
API call or full-catalog LLM automation is claimed. Committed reviewed scopes
are assumptions, not certificates; callers cannot supply their own templates.

Rejected controls: territorial control at a deadline may reverse; bankruptcy
wording lacks an explicit starting anchor. Neither is silently cast to OCCURS_IN.
Creation metadata, boundary conventions, ancillary changes, independent oracle,
actual fees and different settlement maturities remain explicit unknowns.

## Prospective experiment
One capture. Four rounds, two-second target interval, the three groups above,
at most 18 tokens / 72 book GETs. Two policy reads and six before/after exact
event reads. Review sources before quotes. Missing/revised/closed members are
not replaced. Denominator stays 12 family/round attempts. Anonymous GET only.
No persistent schedule; final network workflow manual-only.

TypeScript recompiles original full source; Python consumes intervals/identities,
not another prose parser. OR-closure of atomic interval signatures enumerates
zero-or-multiple-occurrence histories. Union over unresolved start inclusion and
final-minute endpoints preserves boundary uncertainty. Independent 0/0.5/1
settlements are stress scenarios, not an exhaustive platform-risk proof.

Reuse S1 and same-depth S2 baseline, book/native/time validators. Add pairwise-only
semantic states on the identical books, budget and quantities. Semantic-information
gain is distinct from solver innovation. Fees diagnostic only; net qualification
blocked, actual PnL null, repeated snapshot floors never summed. Financing and
non-atomic execution risks cannot be removed by algebra.

## Acceptance
Independent brute-force histories, shifted starts, repeats, endpoints, full-rule
mutations, high-order positive control and missing observations. Full local
check/build/test and research suites, separate clean CI and original-byte replay.
No production dependency/lockfile change; old evidence unchanged. No auto merge.
PARTIAL_ADOPT candidate for source-bound temporal research; HOLD full semantic
certification, LLM automation and profitability. No economic increment is a valid
negative result, not justification for greater optimizer complexity.
