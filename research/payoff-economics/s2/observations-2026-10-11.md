# 2026-10-11: public-data economic observations

Decision: **HOLD**. Technical research implemented and locally tested; no live
orders, actual fills, certified matching fees or demonstrated realized profit.
Neither short selected sample estimates persistent alpha or market-wide efficiency.

## Provenance

| Item | Pilot | Event-diverse follow-up |
|---|---|---|
| GitHub capture run | 38140353386 | 38142340764 |
| Artifact ID | 11703245828 | 11702904715 |
| Capture source | d5e3bdc1fd73013a213a6e43ee116712b2de6b35 | 78df25f9cf3d2b1837e65c9154cd5f9f1dfb706e |
| Book acquisition UTC | 12:43:37.045639–12:44:33.208702 | 13:14:12.094247–13:15:08.816356 |
| China time (UTC+8) | 20:43:37–20:44:33 | 21:14:12–21:15:08 |
| Repeated cycles | 12 | 12 |
| Usable catalog events | 100 | 398 |
| Selected families | 24 | 24 |
| Distinct selected event IDs | 9 | 24 |
| Tokens observed | 84 | 88 |
| HTTP requests | 1,035 | 1,149 |
| Successful complete responses | 984 | 1,149 |

Pilot artifact ZIP SHA-256:
`7e560483579dac3381d04b51fa0cb3ad778434bc55c2f1d305e16df954f6c59f`

Follow-up artifact ZIP SHA-256:
`ea09da11e9b87c8a174029679fc34ff3f69c9c81fbe17fe17d766949d793e0e1`

The hash of the parsed request manifest (canonical JSON of records) is respectively
`3f20c2f132d3beba5cb2dcfee6bda890df11ac5e570ab8701649728d96288134` and
`2675989c14a6f014707ca65fe6cf4119d5ae4c94b2812fdb336cb0cc882c5d88`.
Raw responses were downloaded and integrity-checked in the local container.
GitHub artifacts have seven-day retention; retain the separate delivered raw
archives to reproduce after expiration. The download bundle records which ZIP
hash belongs to the original Actions artifact rather than a repackaged archive.

## Coverage failures are not no-arbitrage observations

The pilot's three 100-event liquidity pages exceeded the 12MB safety cap and
were rejected as incomplete. Only its 100 recent events were usable. Its sixteen
binary controls came from one election event. The pilot is therefore not a
liquidity-ranked or diverse sample. Forty smaller 10-event pages and one binary
control per otherwise unrepresented event were specified BEFORE the follow-up.
That follow-up obtained 398 distinct events with no HTTP or body-limit errors.
Neither is the complete venue universe; unknown position schemas are excluded.

## Conditional snapshot results

| Measurement | Pilot | Follow-up |
|---|---:|---:|
| Family snapshots attempted | 288 | 288 |
| Analyzed after input gates | 132 | 181 |
| Empty ask book exclusions | 132 | 24 |
| HTTP 404 family exclusions | 24 | 0 |
| Stale server book timestamp exclusions | 0 | 83 |
| Unique analyzed economic states | 88 | 126 |
| Exact gross BUY-only no-arbitrage witnesses | 120 | 181 |
| Gross-positive S1 snapshots | 12 | 0 |
| S1 improvements over top-book equal-size | 12 | 0 |
| S1 improvements over SAME-DEPTH equal-size | 0 | 0 |
| No-arbitrage witnesses in nominal curve-fee model | 132 | 181 |

There was only ONE gross-positive family in the pilot, repeated across twelve
snapshots. These are not twelve independent trades. The follow-up found none in
its admitted sampled models. Counts may not be added as independent statistical
trials. Stale means outside the chosen <=120-second server-timestamp gate; it is
not proof the venue would have refused that quote. Acquisition within <=5 seconds
is still not simultaneous, continuous or atomic market data.

The no-arbitrage witnesses are exact mathematical statements about the supplied
finite payment states and observed asks. Negative-risk group state coverage is
explicitly assumed, not a completed semantic/onchain audit. They do not exclude
maker, short, conversion or unobserved cross-family strategies. Nominal fees use
explicit captured rate/exponent/taker metadata and the unrounded formula; no
production debit/rounding certificate was issued.

## Representative gross candidate, not a recommendation

Pilot event 770450, `Fed Decision in December?`, markets 3215005–3215009.
Under the assumed exactly-one-winner model, five NO tokens pay four collateral
units per equal-size set. Budget: 1,000 units, no borrow or short.

The first-book equal-size baseline finds only four sets (the shallowest best
ask has four whole shares). Its gross floor is 0.028, but the order is below the
native minimum size of five. Both S1 and the same-depth equal-size baseline
choose 250 sets with NO limits 0.994, 0.989, 0.780, 0.260, 0.971.

| Value | Amount |
|---|---:|
| Conditional total minimum payout | 1,000 |
| Full-quantity-at-limit gross cost bound | 998.50 |
| Conservative gross floor | +1.50 |
| Exact sampled ladder cost, before fees | 998.49595 |
| Exact unrounded nominal curve fee scenario | 5.1127228425 |
| Sampled nominal after-fee floor | -3.6086728425 |
| Independent FOK-leg failure stress floor, no fees | -248.50 |

The nominal after-fee value uses the sampled ladder cost, not the more expensive
limit-bound cost. It is a formula scenario, NOT an actual receipt. The loss
stress is also hypothetical: one costly leg fills, the others do not, and its
outcome loses. No probability is assigned to this path.

The gross-only diagnostic ledger attempts the family at most once, locks the
resulting inventory and never invents redemption or recognized profit. Its
remaining cash is not strategy profit. In a fee-qualified deployment this
negative-fee scenario would prevent taking the proposed gross trade.

**Interpretation:** the apparent improvement over top-book scanning is deeper
liquidity access. It supplies no evidence of incremental unequal-quantity alpha
once an equally informed depth baseline is used. The nominal fees exceed the
small gross margin in this observed family.

## Local qualification and remaining work

Pinned local Node 22.22.1 / pnpm 11.13.1: full workspace check PASS, build PASS,
1,077 tests PASS. Optional Python 3.13 / NumPy 2.3.5 / SciPy 1.17.0: original
S1 11 tests PASS; S2 21 tests PASS. S2 includes 300 exact witness cases, sixty
same-objective top-book comparisons and eighty independent depth-oracle cases.
Remote qualification is reported separately in the PR, not presumed from local
results. Production files are unchanged relative to the S1 parent.

Next evidence required before further solver complexity: broader independent
windows and strategy families, explicit settlement exception coverage, fee
rounding/debit-asset qualification, and synchronized executable observations.
There is no basis here to forecast monthly revenue or claim all future
opportunities have disappeared. Do not merge this as a profitable trading system.
