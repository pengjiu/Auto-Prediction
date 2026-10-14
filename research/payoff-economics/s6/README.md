# S6 — candidate coverage and joint/marginal claims

This extends the existing S5 research candidate rather than opening another
parallel mutation. It changes retrieval coverage and the conditional relation
class, not the numerical solver or production certification authority.

## Coverage is not precision

`census.py` reads a bounded, digest-checked original catalog ZIP without extraction.
It indexes full paragraphs while retaining original character offsets and hashes.
Whitespace normalization only supports retrieval: numbers, negation, subjects and
exceptions are not removed. Shared text is never a semantic certificate.

Compare a complete-block router with a simple title-token router at the same
32-pair review budget. This is not a comparison with all embedding/LLM systems.
The original population has liquidity/ranking selection and repeated templates;
router price independence does not make the population an unbiased market sample.
A retrospective exploration preceded the fixed numerical experiment. There is no
independent gold label set, so do not report precision, recall or profit hit rate.

The original 398-event catalog has 16,611 distinct market IDs but 9,598 distinct
market-description strings. Earlier reports that described 16,611 independent
rule texts should not be used as that denominator. Full logs, all candidate IDs
and original source spans are available through the census CLI. The compact
`coverage-results.json` is a derived report, not a raw source replacement.

## One reviewed composition

`reviewed-factor.json` binds complete descriptions for Senate control, House
control and their joint result. The in-session assistant inspected them; this is
not independent review, a provider API call or full-catalog LLM automation.

`export.ts` recompiles the exact original events and native IDs. Four selected
contracts represent S_D, H_D, S_D AND H_D, and S_D AND H_R. Each chamber has D, R
and OTHER states (nine latent states, five distinct traded truth vectors).
Unlisted parties and residual outcomes cannot silently disappear. No augmented
Other token or protocol conversion is traded. Matching source fields does not
force distinct oracles, clarifications or unusual outcomes to agree.

The same S1 solver and same-depth S2 baseline use identical books, budget, minimum
sizes and cost assumptions. A pairwise-projection relaxation isolates the value
of the full AND relation. Independent 0/0.5/1 contract settlements are stress,
not a complete settlement guarantee. All cashflows are undiscounted terminal
research values, not financing-adjusted realized returns. Fees are diagnostic.

## Reproduce

Use the unchanged workspace lockfile and optional pinned NumPy/SciPy environment.

```sh
python -m unittest discover -s research/payoff-economics/s6 -p 'test_*.py' -v
packages/control-plane/node_modules/.bin/tsx research/payoff-economics/s6/test-export.ts
python research/payoff-economics/s6/census.py --archive /path/to/Auto-Prediction_S2_Followup_Evidence.zip --sha256 ea09da11e9b87c8a174029679fc34ff3f69c9c81fbe17fe17d766949d793e0e1 --output /new/path/census.json
python research/payoff-economics/s6/campaign.py analyze --root /path/to/s6/capture --output /new/path/result.json
```

Capture is a separate explicit command, fixed to four contracts/eight tokens and
four rounds. Its preregistration remains unchanged; missing or changed sources
are exclusions, not replacements or no-arbitrage witnesses. Outputs are
create-only. The original new ZIP artifact and digest are in `market-results.json`;
it includes raw capture, exact source and logs and has an explicit expiry. Keep
an independent copy for long-term reproduction. No permanent archive is claimed.

See `VALIDATION.md` for actual observations, test provenance, limits and selection.
No live effects or mainline merge are enabled by this slice.
