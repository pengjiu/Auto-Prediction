/** Research-only bridge. Always recompile current source predicates; never accept
 * an old EXACT label or an LLM-supplied truth-table as evidence of completeness.
 */
import { hashCanonical } from "@pmh/domain";
import { bindSettlementCondition, compareDecimal, decimalParts, evaluateNumeric, observationKey,
  type BoundCondition, type NumericCondition } from "./settlement-condition.js";
import { compileSettlementProjections, SETTLEMENT_PROJECTION_COMPILER_IDENTITY } from "./settlement-projection-compiler.js";

type CompilationInput = Parameters<typeof compileSettlementProjections>[0];
export type NumericResearchInput = CompilationInput & Readonly<{ listingRefs: readonly string[] }>;

export function numericCells(conditions: readonly NumericCondition[]): readonly Readonly<{
  id: string; numerator: string; denominator: string;
}>[] {
  if (conditions.length < 1 || conditions.length > 6) throw new Error("numeric cell scope must be 1..6 conditions");
  if (conditions.some(c => observationKey(c) !== observationKey(conditions[0]!))) throw new Error("different observation axes");
  const thresholds = [...new Set(conditions.map(c => c.threshold))].sort(compareDecimal);
  const points: { id: string; numerator: string; denominator: string }[] = [];
  const add = (id: string, n: bigint, d: bigint) => points.push({ id, numerator: n.toString(), denominator: d.toString() });
  const [first, fd] = decimalParts(thresholds[0]!); add("below", first - fd, fd);
  thresholds.forEach((value, i) => {
    const [n, d] = decimalParts(value); add(`at_${i}`, n, d);
    const next = thresholds[i + 1];
    if (next !== undefined) {
      const [nn, nd] = decimalParts(next); add(`between_${i}`, n * nd + nn * d, 2n * d * nd);
    } else add("above", n + d, d);
  });
  return Object.freeze(points.map(p => Object.freeze(p)));
}

export function exportNumericPayoffResearch(input: NumericResearchInput) {
  if (input.listingRefs.length < 2 || input.listingRefs.length > 6 ||
      new Set(input.listingRefs).size !== input.listingRefs.length) throw new Error("select 2..6 unique listings");
  const refs = [...input.listingRefs].sort();
  const compiled = compileSettlementProjections(input);
  const rows = refs.map(ref => {
    const listing = input.corpus.listings.find(l => l.listingRef === ref);
    const observation = compiled.observations.find(o => o.listingRef === ref);
    const projection = compiled.projections.find(p => p.listing.listingRef === ref);
    if (!listing || observation?.disposition !== "EXACT_PROJECTED" ||
        projection?.compilerIdentity !== SETTLEMENT_PROJECTION_COMPILER_IDENTITY || projection.predicateIds.length !== 1) {
      throw new Error(`unadmitted settlement mapping: ${ref}: ${observation?.blockers.join(",") ?? "missing"}`);
    }
    const predicate = compiled.predicates.find(p => p.artifactHash === projection.predicateBindings[0]?.predicateArtifactHash)!;
    const bound = bindSettlementCondition(listing.rulesText ?? "", predicate.semantic);
    if (bound.blocker !== null || bound.condition?.atom.kind !== "NUMBER") throw new Error("opaque or unknown relation cannot generate numeric states");
    const c = bound.condition.atom;
    if (!c.source || !c.startsAt || !c.endsAt) throw new Error("common observation requires explicit source and exact interval");
    if (listing.status !== "OPEN" || listing.outcomes.length !== 2) throw new Error("unavailable binary listing");
    const yes = listing.outcomes.find(o => o.label === "Yes"), no = listing.outcomes.find(o => o.label === "No");
    if (!yes || !no || !yes.venueOutcomeId || !no.venueOutcomeId || yes.venueOutcomeId === no.venueOutcomeId) throw new Error("native outcomes unavailable");
    return { listing, projection, predicate, condition: bound.condition as BoundCondition & { atom: NumericCondition },
      yes: yes.venueOutcomeId, no: no.venueOutcomeId };
  });
  if (rows.some(r => r.listing.venueId !== rows[0]!.listing.venueId ||
      r.listing.protocolIdentity !== rows[0]!.listing.protocolIdentity)) throw new Error("cross-venue/protocol collateral not qualified");
  const cells = numericCells(rows.map(r => r.condition.atom));
  const states = cells.map(c => c.id);
  const tokens = rows.flatMap(r => [r.yes, r.no]);
  if (new Set(tokens).size !== tokens.length) throw new Error("duplicate native outcome assets");
  const independentStates = Array.from({ length: 2 ** rows.length }, (_, i) => `independent_${i}`);
  const stressStates = [...independentStates, "all_half"];
  const assets = rows.flatMap((r, index) => [true, false].map(yes => ({
    id: yes ? r.yes : r.no, venue: r.listing.venueId, listingRef: r.listing.listingRef,
    instrumentId: r.listing.venueInstrumentId, outcome: yes ? "YES" : "NO",
    payoffs: Object.fromEntries(cells.map(cell => {
      const truth = evaluateNumeric(r.condition.atom, BigInt(cell.numerator), BigInt(cell.denominator)) !== r.condition.negated;
      return [cell.id, truth === yes ? "1" : "0"];
    })),
    stressPayoffs: { ...Object.fromEntries(independentStates.map((id, world) =>
      [id, ((world & (1 << index)) !== 0) === yes ? "1" : "0"])), all_half: "0.5" },
  })));
  const body = Object.freeze({
    schemaVersion: "pmh.numeric-payoff-research.v1" as const,
    compilerIdentity: SETTLEMENT_PROJECTION_COMPILER_IDENTITY,
    coverage: "ASSUMED_STATES_ONLY" as const, authority: "RESEARCH_EXPORT_ONLY" as const,
    assumption: "SHARED_OBSERVATION_AND_CONSISTENT_RESOLUTION" as const,
    certificateAuthority: false as const, executionAuthority: false as const,
    corpusIdentity: input.corpus.snapshotIdentity,
    sources: rows.map(r => ({ listingRef: r.listing.listingRef, listingHash: hashCanonical(r.listing),
      sourceRawHash: r.listing.sourceRawHash, sourceReceivedAt: r.listing.sourceReceivedAt,
      protocolIdentity: r.listing.protocolIdentity, predicateId: r.predicate.predicateId,
      predicateArtifactHash: r.predicate.artifactHash, projectionHash: r.projection.artifactHash,
      condition: r.condition })),
    states, cells, assets, stressStates,
    stressAssumption: "INDEPENDENT_BINARY_RESOLUTIONS_PLUS_ALL_HALF_NOT_EXHAUSTIVE" as const,
  });
  return Object.freeze({ ...body, exportId: hashCanonical(body) });
}
export type NumericPayoffResearch = ReturnType<typeof exportNumericPayoffResearch>;
export function assertNumericPayoffResearch(value: unknown, input: NumericResearchInput): NumericPayoffResearch {
  const rebuilt = exportNumericPayoffResearch(input);
  if (hashCanonical(value) !== hashCanonical(rebuilt)) throw new Error("research export is not the current compiled source");
  return rebuilt;
}
