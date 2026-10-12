# Semantic binding validation — 2026-10-12

Base main `2a473d11d62c91ee96558d9df7b6b3650f8c5aa9`, tree
`ed1d7ad5461c7957783dce6c41117b740929a4ae`. Local main source was restored
from the retained Git bundle and reviewed patch, with exact tree equality.
Node 22.22.1 / pnpm 11.13.1 / TypeScript 5.9.3, Python 3.13.5 / NumPy 2.3.5 /
SciPy 1.17.0. Dependencies were the prior frozen-lockfile offline archive;
local relocation disabled dependency-status auto-reinstall only. No lockfile or
application dependency change. Final clean-install CI is a separate requirement.

## Local runs

- Existing-source audit: 7 tests, 1 valid control passed, 6 wrong-condition tests
  **failed**, before production changes. All six now reject or map inversely.
- Downstream inverse settlement: one fresh failing test showed shadow legs used
  world truth instead of listing truth. Repaired and re-run: 5/5 pass.
- Focused semantic/projection/coverage/shadow: 38/38 pass, including 75 small
  independent exhaustive checks of threshold endpoint/open-interval truth sets.
- Full `pnpm run check` and `pnpm run build`: PASS.
- Full `pnpm run test`: **1,113 PASS, 0 FAIL** (28 root + 1,085 workspace).
- S1 **16/16**, S2 **32/32**, S3 **6/6**, P0 offline **43/43**, patch-tool **8/8**.
  Focused and offline counts overlap; these are not all unique tests.
- Actual source-export CLI reproduces the checked synthetic export; arbitrary
  rehashed exports fail comparison with first-party source recompilation.
- All historical raw evidence remains unchanged; new logs live outside it.

The first broad control-plane invocation exceeded its tool-call timeout and was
terminated; it is not counted as a pass. Final full-workspace execution completed
normally with exit 0. Initial test expectation failures exposed the intended
stricter coverage: a Senate topic label is not equivalent to a full party-control
rule. The test now requires research-only with condition mismatch. Void-rule
assertions preserve their original blocker while allowing the new unconsumed-
rule blocker. An old test used a deliberately invalid artifact hash merely to
represent a revision; it now constructs a valid revision. No tests were skipped.

## Economic/coverage evidence

A completely synthetic threshold fixture, not live LLM output or a real quote,
passes source compilation -> exact cells -> S1/same-depth controls. Both have
the SAME gross floor, **1.00** collateral unit for the selected ten-share basket.
Independent binary resolutions plus the all-half stress eliminate the candidate.
Net certification remains blocked due to unqualified fees; no realized profit
is recorded. This validates the route, not algorithmic Alpha.

A syntax-only retrospective census of the original hash-verified follow-up
catalog contains 16,611 unique market descriptions; every description is outside
the supported complete binary envelope. See evidence/real-coverage.json. This
is evidence of a real rule-coverage gap, not market inefficiency or efficiency.
No new market capture, model invocation, independent settlement sign-off or
positive real cross-event economic result occurred in this iteration.

Decision: **PARTIAL_ADOPT candidate for correctness and research plumbing;
HOLD real-market automatic admission**. The branch is not automatically merged.
Next qualification must cover complete real source/fallback/rounding/exception
rules, not remove paragraphs to fit the controlled dialect.
