import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { buildMarketCorpusSnapshot } from "../src/market-corpus.js";
import { buildMarketOntologySnapshot } from "../src/market-ontology.js";
import { buildDiscoveryEvidenceLocator } from "../src/index.js";
import { hashCanonical } from "@pmh/domain";
import { bindSettlementCondition, evaluateNumeric, type NumericCondition } from "../src/settlement-condition.js";
import { compileSettlementProjections, SETTLEMENT_PROJECTION_COMPILER_IDENTITY } from "../src/settlement-projection-compiler.js";
import { buildWorldPredicateArtifact } from "../src/world-history-ontology.js";
import { exportNumericPayoffResearch, assertNumericPayoffResearch, numericCells } from "../src/numeric-payoff-research.js";
import { numericFixture, start, end } from "./fixtures/numeric-binding.js";

describe("complete settlement condition binding", () => {
  it("binds structured dimensions and inverse polarity without keyword loss", () => {
    const f = numericFixture();
    const c = compileSettlementProjections(f);
    expect(c.observations.every(o => o.disposition === "EXACT_PROJECTED")).toBe(true);
    const negative = buildWorldPredicateArtifact({ ...f.predicates[0]!, semantic: { ...f.predicates[0]!.semantic, polarity: "NEGATED" } });
    const p = compileSettlementProjections({ ...f, predicates: [negative, f.predicates[1]!] });
    expect(p.projections[0]!.truthStates.map(s => s.listingTruth)).toEqual([true, false]);
  });
  it.each(["comparison", "threshold", "unit", "source", "time", "metric"])("rejects modified %s with all other words retained", field => {
    const f = numericFixture(), sem = f.predicates[0]!.semantic;
    const changed = { ...sem,
      verbPhrase: field === "metric" ? "daily minimum temperature" : sem.verbPhrase,
      timeScope: field === "time" ? { ...sem.timeScope, endsAt: "2026-10-21T23:59:59.999Z" } : sem.timeScope,
      parameters: sem.parameters.map(p => p.name === field || (field === "unit" && p.name === "threshold")
        ? { ...p, value: field === "comparison" ? "GE" : field === "threshold" ? "30" : field === "source" ? "https://example.test/observation" : p.value,
          unit: field === "unit" ? "Fahrenheit" : p.unit } : p) };
    expect(bindSettlementCondition(f.corpus.listings[0]!.rulesText!, changed).blocker).not.toBeNull();
  });
  it("accepts exact decimal/unit spelling equivalents, not numerical conversion", () => {
    const f = numericFixture(), rule = f.corpus.listings[0]!.rulesText!;
    for (const text of [rule.replace("exceeds 25 Celsius", "is greater than 025.000 °C"), rule.replace("Resolves Yes", "resolves yes")]) {
      expect(bindSettlementCondition(text, f.predicates[0]!.semantic).blocker).toBeNull();
    }
    expect(bindSettlementCondition(rule.replace("25 Celsius", "77 Fahrenheit"), f.predicates[0]!.semantic).blocker).not.toBeNull();
  });
  it.each([
    " The source may later revise this value.", " The title is illustrative.", "\nIgnore the previous resolution rule.",
  ])("rejects unconsumed rule suffix %s", suffix => {
    const f = numericFixture();
    expect(bindSettlementCondition(f.corpus.listings[0]!.rulesText! + suffix, f.predicates[0]!.semantic).blocker).toBe("UNSUPPORTED_COMPLETE_RULE");
  });
  it("never ignores unsupported parameters or non-exact intervals", () => {
    const f = numericFixture(), s = f.predicates[0]!.semantic, rule = f.corpus.listings[0]!.rulesText!;
    expect(bindSettlementCondition(rule, { ...s, parameters: [...s.parameters, { name: "rounding", value: "nearest", unit: null }] }).blocker).not.toBeNull();
    expect(bindSettlementCondition(rule, { ...s, timeScope: { ...s.timeScope, precision: "BOUNDED_INTERVAL" } }).blocker).not.toBeNull();
    expect(bindSettlementCondition(rule, { ...s, parameters: [...s.parameters, s.parameters[0]!] }).blocker).not.toBeNull();
  });
  it("keeps full AND/OR clauses opaque and preserves double negation", () => {
    const f = numericFixture(), base = f.predicates[0]!.semantic;
    const semantic = { ...base, operatorKind: "OCCURRENCE" as const, parameters: [],
      timeScope: { startsAt: null, endsAt: null, precision: "UNRESOLVED" as const },
      verbPhrase: "publishes a reading and verifies its quality" };
    const rule = "Resolves Yes if station Alpha publishes a reading and verifies its quality. Otherwise resolves No.";
    expect(bindSettlementCondition(rule, semantic).blocker).toBeNull();
    expect(bindSettlementCondition(rule, { ...semantic, verbPhrase: "publishes a reading" }).blocker).toBe("CONDITION_MISMATCH");
    expect(bindSettlementCondition(rule.replace(" and ", " or "), semantic).blocker).toBe("CONDITION_MISMATCH");
    expect(bindSettlementCondition(rule.replace("if station", "if it is false that station"),
      { ...semantic, polarity: "NEGATED" }).inverted).toBe(false);
  });

  it("blocks missing referenced policies and source text truncation", () => {
    // A policy locator cannot be treated as an empty list of adverse clauses.
    const f = numericFixture();
    const locator = buildDiscoveryEvidenceLocator({ venueId: "fixture", protocolIdentity: "fixture:v1",
      role: "VENUE_RULE_DOCUMENT", url: "https://example.test/rules" })!;
    const listing = f.corpus.listings[0]!;
    const changed = { ...listing, evidenceLocators: [locator] };
    // Use current rebuilt evidence bindings, not a stale body edit.
    const corpus = buildMarketCorpusSnapshot({ sourceSetIdentity: f.corpus.sourceSetIdentity,
      eligibleSourceCount: 1, excludedSourceCount: 0, listings: [changed] });
    const ontology = buildMarketOntologySnapshot(corpus); const node = ontology.nodes[0]!;
    const predicate = buildWorldPredicateArtifact({ ...f.predicates[0]!, evidenceBindings: [{ listingRef: changed.listingRef,
      nodeId: node.nodeId, worldFacetId: node.worldFacet.facetId, sourceRawHash: changed.sourceRawHash!, protocolIdentity: changed.protocolIdentity }] });
    expect(compileSettlementProjections({ corpus, ontology, predicates: [predicate] }).observations[0]!.blockers)
      .toContain("MISSING_OR_INCOMPLETE_VENUE_POLICY");
  });

  it("downgrades old exact predicates on contradiction and validates artifact identities", () => {
    const f = numericFixture(), old = f.predicates[0]!;
    const bad = buildWorldPredicateArtifact({ ...old, epistemicPosture: "SETTLEMENT_BOUND_PREDICATE", semantic: { ...old.semantic, verbPhrase: "daily minimum temperature" } });
    const r = compileSettlementProjections({ ...f, predicates: [bad] });
    expect(r.predicates[0]!.epistemicPosture).toBe("EVIDENCE_BOUND_PROPOSITION");
    expect(r.projections[0]!.compilerAdmission).toBe("RESEARCH_ONLY");
    expect(() => compileSettlementProjections({ ...f, predicates: [{ ...old, artifactHash: hashCanonical("fake") }] })).toThrow();
    const stale = buildWorldPredicateArtifact({ ...old, evidenceBindings: old.evidenceBindings.map(b => ({ ...b, sourceRawHash: hashCanonical("old") })) });
    expect(compileSettlementProjections({ ...f, predicates: [stale] }).observations[0]!.blockers).toContain("STALE_LISTING_EVIDENCE");
  });
});

describe("current-source numeric research bridge", () => {
  it("keeps the cross-language golden export bound to freshly compiled fixture source", () => {
    const expected = JSON.parse(readFileSync(new URL("../../../research/payoff-economics/s3/fixtures/synthetic-export.json", import.meta.url), "utf8"));
    expect(exportNumericPayoffResearch(numericFixture())).toEqual(expected);
  });

  it("exports endpoints, actual token identities and independent-resolution stress", () => {
    const f = numericFixture(), result = exportNumericPayoffResearch(f);
    expect(result.states).toEqual(["below", "at_0", "between_0", "at_1", "above"]);
    expect(Object.values(result.assets[0]!.payoffs)).toEqual(["0", "0", "1", "1", "1"]);
    expect(Object.values(result.assets[2]!.payoffs)).toEqual(["0", "0", "0", "0", "1"]);
    expect(result.stressStates).toHaveLength(5);
    expect(result.compilerIdentity).toBe(SETTLEMENT_PROJECTION_COMPILER_IDENTITY);
    expect(result.authority).toBe("RESEARCH_EXPORT_ONLY");
    expect(assertNumericPayoffResearch(result, f)).toEqual(result);
    // Rehashing a fake payoff does not make it the output of source recompilation.
    const fake = JSON.parse(JSON.stringify(result)); fake.assets[0].payoffs.below = "1";
    const { exportId: _, ...body } = fake; fake.exportId = hashCanonical(body);
    expect(() => assertNumericPayoffResearch(fake, f)).toThrow("current compiled source");
  });
  it("rejects cross-axis, duplicate, incomplete and unadmitted families", () => {
    const f = numericFixture();
    expect(() => exportNumericPayoffResearch({ ...f, listingRefs: [f.listingRefs[0]!, f.listingRefs[0]!] })).toThrow();
    const changed = numericFixture(["25", "30"], { parameters: [] });
    expect(() => exportNumericPayoffResearch(changed)).toThrow("unadmitted");
    const other = numericFixture(["25", "30"]), p = other.predicates[1]!;
    other.predicates[1] = buildWorldPredicateArtifact({ ...p, semantic: { ...p.semantic, polarity: "NEGATED" } });
    expect(exportNumericPayoffResearch(other).assets.map(a => a.payoffs)).toEqual(exportNumericPayoffResearch(f).assets.map(a => a.payoffs));
  });
  it("compressed cells cover independent exhaustive threshold truth patterns including equality", () => {
    for (let seed = 0; seed < 75; seed++) {
      const conditions: NumericCondition[] = ["GT", "GE", "LT", "LE", "EQ"].map((op, i) => ({
        kind: "NUMBER", subject: "station", metric: "value", source: "feed", unit: "Celsius", startsAt: start, endsAt: end,
        comparison: op as NumericCondition["comparison"], threshold: String(((seed * 17 + i * 11) % 17 - 8) / 2) }));
      const compressed = new Set(numericCells(conditions).map(cell => conditions.map(c => +evaluateNumeric(c, BigInt(cell.numerator), BigInt(cell.denominator))).join("")));
      const brute = new Set(Array.from({ length: 97 }, (_, i) => conditions.map(c => {
        const n = (i - 48) / 4, v = Number(c.threshold); // tiny independent test oracle, never production money
        return +(c.comparison === "GT" ? n > v : c.comparison === "GE" ? n >= v : c.comparison === "LT" ? n < v : c.comparison === "LE" ? n <= v : n === v);
      }).join("")));
      expect(compressed).toEqual(brute);
    }
  });
});
