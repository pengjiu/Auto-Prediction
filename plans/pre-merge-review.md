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
- Counterexamples must fail before fixes and pass afterwards. Baseline local
  tests passed (74 execution, 11 S1, 21 S2); new counterexamples initially failed
  (5 shadow, 10 research). Store exact logs with the final report.
- Run complete pinned Node 22.22.1 / pnpm 11.13.1 check, build and tests; optional
  Python 3.13 / NumPy 2.3.5 / SciPy 1.17.0 research, independent integer oracles,
  P0 offline regression and patch-tool tests.
- Recompute saved raw data as retrospective audit only, retaining input hashes
  and exclusions. No new real trades or profitability claims.
- Publish only reviewed files; verify remote blobs against locally tested bytes.
- Merge the tested ancestry into main using an expected-head check. Recheck main
  and all prior branch tips. Report any actual remaining verification gap.
