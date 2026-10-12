# P0 payoff-economics reproduction and handoff

Base: `pengjiu/Auto-Prediction@d6c9447cab29898a6eb5fa06be3598b8474cc02f`.
Design: [`plans/certified-payoff-economics.md`](../../plans/certified-payoff-economics.md).

This directory preserves the focused offline qualification prepared before GitHub write authorization was restored. Production changes are applied under `packages/`; this directory is **not a second production implementation**. The four files in `evidence/` are immutable upstream verifier/fixed-point fixtures, pinned by Git blob SHA. The two `overlay/` files are the exact P0 helper and Vitest test submitted under `packages/execution/`; they make the original isolated experiment reproducible without installing the entire workspace. Changes to production code after this P0 snapshot need fresh integration tests rather than silently treating these snapshots as current code.

## Run the focused checks

From the repository root, with Node, TypeScript and Node type declarations already available:

```sh
node research/payoff-economics/offline/run.mjs
python3 -m unittest discover -s research/payoff-economics/tests -v
```

The runner never installs packages, connects to a venue or requests credentials. When TypeScript or Node declarations are outside the standard locations, set `TYPESCRIPT_PATH` to the TypeScript module and `NODE_TYPES_PATH` to the directory containing `@types/node`. It emits `.offline-build/` and updates the local evidence logs; do not commit generated build output.

The TypeScript test body's only runner adaptation is `vitest` describe/it -> `node:test`, plus the local import path. The six selection tests execute the exact old/new selector expressions in `source-edits.json`; they are **not** end-to-end semantic admission tests. Historical results and remaining gates are in [VALIDATION.md](VALIDATION.md).

## Reproduce patch application separately

`apply_patch.py` is retained for auditing the original delivery and only targets a **separate clean checkout of the pinned base**. This branch already contains the patch; do not run it against this branch. The design document is already committed separately and is not in this source overlay.

```sh
python3 research/payoff-economics/apply_patch.py --repo /path/to/clean-base-checkout
# Default is read-only. --apply writes only after exact blob/anchor preflight.
```

It does not run Git or make network calls. It refuses changed originals, duplicate anchors, existing added files, path escapes and symlinks. File replacements are individually atomic with best-effort rollback, not a crash-atomic multi-file transaction or a lock against concurrent writers.

## Acceptance boundary

Observed focused result: 43 tests passed, plus 8 patch-applier tests. The application runtime requirement remains Node >=22.19; the constrained offline run used Node 22.16.0 and TypeScript 5.8.3. **Full workspace `pnpm check`, `pnpm test`, build and semantic/market end-to-end checks are NOT RUN.** No market profitability, real fills, multi-leg atomicity or match-level fee qualification is asserted. Curve-fee promotion stays blocked. Live orders, signing, token approvals, credentials and fund movement remain disabled.
