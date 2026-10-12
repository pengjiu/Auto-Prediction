# All-branch adversarial review — 2026-10-12

## Decision and authority

The user explicitly requested repair and mainline integration of all unmerged
branches. ADOPT the corrected P0/S1/S2 code as **research-only tooling** after
local and remote validation. No actual profitability or trading authority is
implied. No keys, orders, signatures, approvals or funds were used.

## Reviewed source

P0 `8394e819`, S1 `e5109f5c`, S2 `c43f9a64` form one ancestry chain.
The interrupted `30ea8c17` review branch contained documentation and CI only.
The resumed source/history archive at `4dcef72b` was verified against its GitHub
artifact digest and restored locally, not re-created from prose. All changed
paths and adjacent materialization, simulation and persistence code were read.
This is a bounded review, not a proof that every defect in the repository is gone.

## Reproduced and repaired

1. Later shadow observations accepted above-limit fills when total cost stayed
   inside budget. They also failed to reject changed native IDs, scale, fees or
   earlier samples. Observation v2 now retains baseline inputs and deterministically
   replays all statuses and reasons on read. Rehashed success labels are rejected.
2. Exact promotion accepted a newly simulated, rehashed plan while keeping an
   unrelated original materialization record. Payment inflation, cheaper levels,
   altered fee parameters and a newer clock all reproduced. Materialization v2
   binds the complete normalized plan, and promotion checks binary units/native
   outcomes plus fee-evidence expiry. Old unbound normalized records fail closed;
   original raw evidence remains intact and can be re-materialized.
3. S1 ignored native minimum order quantities, allocated exhaustive-oracle arrays
   before applying its cap, and omitted currency scale from proposals. Minima are
   now present in solver and oracle; bounds precede allocation; units and minimum
   constraints enter identities; zero-floor ties explicitly select no-trade.
4. S2 silently truncated zipped asset/state vectors and fractional payouts;
   duplicated members could impersonate an exhaustive group. Length/identity,
   exact representability, native minimum/tick and uniqueness checks now reject
   those inputs. Event-level rules enter the immutable rule identity.
5. A second nominal-fee path bypassed contradictory fee flags. All nominal
   calculations now use the same checked interpretation; unknown fees never
   turn into zero. Match-level debit certification stays unqualified.
6. Freshness was checked per-response, not at the common decision instant.
   Later replay now respects actual proposal units and changed native constraints.
   A new book hash does not prove depth replenishment: the sampled ledger permits
   one use per token per run pending independently evidenced replenishment.
7. Branch-only CI would not protect main. One qualification workflow now covers
   main and PRs; public capture is manual only. The offline P0 runner no longer
   overwrites tracked historical validation files; current results are written to
   `.offline-build/results`. CI also checks that tracked source/history remain clean.

## Actual local validation

- Pinned Node 22.22.1 / pnpm 11.13.1 restored dependencies match the unchanged
  lockfile. TypeScript 5.9.3, Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0.
- Full `pnpm run check`, `pnpm run build`, `pnpm run test`: PASS.
- **1,086 Node tests**, **16 S1**, **32 S2**, **43 P0 offline**, **8 patch-tool** tests pass.
  The 43 focused checks overlap the main suite; do not add them as unique coverage.
- New tests first reproduced 5 shadow, 4 source-binding, 3 S1 failures/errors and
  8 S2 failures. One tie/no-trade control already passed. Additional tests cover
  60 minimum-size integer-oracle comparisons, non-default units, changed tick
  sizes and duplicate market selection. Original random/exhaustive tests remain.
- The first whole-workspace rerun found one old expected-reasons array missing
  the newly detected limit violation. The expectation was corrected to require
  the additional rejection reason; the full suite then passed. No test skipped.
- A previous test fixed one arbitrary quantity allocation among tied optima. It
  now requires equality with the independent exhaustive optimum and a genuinely
  unequal allocation, rather than one HiGHS tie-breaking outcome.

Local DNS still cannot resolve npm/GitHub. The source and existing pinned
runtime/dependency archive were handed off by GitHub Actions, while these tests
executed in the local container. Relocated pnpm dependency-status auto-install
was disabled locally (`pnpm_config_verify_deps_before_run=false`) to avoid a
network reinstall of the same lockfile; normal clean frozen-lockfile install is
required by final remote qualification. No production package/lockfile change.

## Retrospective raw-data recomputation

Original pilot/follow-up bytes were hash-verified and recomputed, separately from
historical reports. Pilot: 132 analyzed, 120 gross no-arbitrage witnesses, 12
repetitions of one gross-positive family; S1 improvements over same-depth baseline:
**zero**. Follow-up: 181 analyzed, all with gross witnesses, no positive S1
proposal. No new market capture or independent live experiment was performed.
Neither the assumed settlement model nor nominal fees become a real execution
certificate. These short selected samples still do not validate profitability.

## Reproduction and limits

```sh
pnpm install --frozen-lockfile
pnpm run check
pnpm run build
pnpm run test
python -m unittest discover -s research/payoff-economics/s1 -p 'test_*.py' -v
python -m unittest discover -s research/payoff-economics/s2 -p 'test_*.py' -v
node research/payoff-economics/offline/run.mjs
python -m unittest discover -s research/payoff-economics/tests -v
```

Machine-readable local results and log hashes: `results.json`. Final remote
commit/run and main merge receipts are recorded in the publication PR after
verification; this local report does not presume a successful remote merge.
