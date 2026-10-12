# All-branch review and mainline publication

Date: 2026-10-12. The operator explicitly requested review, repair, testing and
merging all unmerged work into main. This authorization covers source changes,
not trading, credentials, signing, approvals or funds.

## Fixed scope
- main: d6c9447cab29898a6eb5fa06be3598b8474cc02f
- P0 / PR #1: 8394e819c929e5ea896f4059d2d39fbf24577c4a
- S1 / PR #2: e5109f5c4fcbeac4928d9109cc6b040efee893fd
- S2 / PR #3: c43f9a643a2dddfea299f7d6068931d417742396
- review-publication initially equals S2; no independent unreviewed changes.
The three strategy branches are a linear ancestry stack. Review covers their
45 changed paths, including tests, workflows, retained evidence and plans.

## Reproduced findings
1. The later shadow observer can report MATCHED_BOUNDS for fills above an old
   limit when their average total remains within budget. Initial shadow locking
   already checks this; the later observer must enforce the same constraint.
2. Later observations omit native token/venue/scale identity, timestamp and fee
   schedule changes from admission. Rehashed success labels can conceal known
   divergences. Validate intrinsic bounds on creation and read.
3. S1 omits venue minimum quantities from optimization, can allocate enormous
   exhaustive-oracle option arrays before checking limits, and can return funded
   zero-floor ties instead of no-trade. Proposals also omit the collateral scale.
4. S2 converts matrices with truncating zip/int operations and accepts repeated
   selected members as an exhaustive event set. Event-level rule changes do not
   invalidate the rule identity.
5. Nominal fee helpers can bypass contradictory fee metadata. Use one checked
   nominal-rate interpretation without changing the unqualified-fee boundary.
6. Sampled replay ignores changed native minimum/tick constraints, assumes a
   global scale, and treats changed book hashes as replenished depth. Preserve
   zero-fee research labels; require units/constraints and never invent liquidity.
7. Existing CI triggers are branch-only: main would lose these checks after
   merge. Consolidate qualification on main, review branch and pull requests;
   keep public market capture explicitly manual rather than running on merges.

## Selection
ADOPT correctness fixes and bounded research tools as research-only mainline
capabilities after local and remote qualification. This does not adopt an
unproven profitable trading strategy. Preserve the original negative market
observations and historical evidence; do not rewrite them as post-fix results.

## Acceptance
- Keep exact rule/payoff checks, fee qualification and all live-effect guards.
- Counterexamples must fail before fixes and pass afterwards. The resumed audit
  independently reproduced 5 shadow failures, 4 exact-promotion source-binding
  failures, 3 S1 failures/errors and 8 S2 failures. One no-trade tie control already
  passed. Preserve actual logs; earlier interrupted-session counts are not new
  execution evidence.
- Run complete pinned Node 22.22.1 / pnpm 11.13.1 check, build and tests; optional
  Python 3.13 / NumPy 2.3.5 / SciPy 1.17.0 research, independent integer oracles,
  P0 offline regression and patch-tool tests.
- Recompute saved raw data as retrospective audit only, retaining input hashes
  and exclusions. No new real trades or profitability claims.
- Publish only reviewed files; verify remote blobs against locally tested bytes.
- Merge the tested ancestry into main using an expected-head check. Recheck main
  and all prior branch tips. Report any actual remaining verification gap.

## Resumed implementation and decisions

The publication branch initially contained only the review plan and CI, not the
interrupted session's code. The resumed run restored the exact source/history
from commit 4dcef72b7969927fb2d415147666fc779a9561d8 and replayed fresh counterexamples.

- **P0:** materialization v2 binds the complete normalized simulation plan. A
  rehashed bundle cannot substitute payment scale, cheaper book levels, fee
  parameters or a newer clock while reusing the original materialization record.
  Binary payment and price/quantity units are checked against listing bindings.
  Future quote timestamps are rejected; fee evidence also limits expiry.
- **P0:** observation v2 retains bounded original inputs and derives its result
  again on read. Above-limit fills, changed native identity/scale/fee and earlier
  observations cannot pass by recomputing only a content hash. This is model
  consistency, not proof that natural-language settlement assumptions are true.
- **S1:** native whole-share minima are constraints in both MILP and the exhaustive
  oracle; guards run before allocating oracle arrays. Zero-floor ties return
  no-trade. Proposals and identity hashes include units and minimum quantities.
  A test previously demanded one arbitrary allocation among tied optima; it now
  checks objective equality with the independent oracle and unequal quantities.
- **S2:** lengths, exact representability, native asset/constraint metadata and
  event-member uniqueness are mandatory. Event-level rule changes invalidate
  grouping. Fee diagnostics share one conflict-checking interpretation.
- **S2:** freshness is measured at the common decision time; retrospective
  compute delay is charged before later observations are eligible. Sampled
  orders use proposal units and current tick/minimum constraints. A changed
  hash is not replenishment: tokens are conservatively consumed once per account
  run, pending separately evidenced replenishment. This can undercount fills;
  it must not be presented as a calibrated fill model.
- **CI:** branch-specific qualification is replaced by one main/PR gate. The
  anonymous capture workflow is manual, never triggered by merge or a schedule.

Historical reanalysis retained the exact original raw bytes and found unchanged
headline counts: pilot 132 analyzed, 120 gross witnesses, 12 repeated positive
snapshots of one family, zero S1 improvements over the same-depth baseline;
follow-up 181 analyzed, 181 gross witnesses, zero positive S1 proposals. These
remain short selected samples with assumed states and unqualified execution.

New v2 normalized records intentionally reject old records that lack binding
information. Re-materialize/replay from retained original evidence rather than
silently upgrading an old approval. Raw fixtures and historical observations are
not rewritten or treated as current certificates.

Final verification details and content identities are in
`research/payoff-economics/review/VALIDATION.md`. Adoption here concerns tested,
research-only software; live orders, signing, credentials and funds stay disabled.
