import { hashCanonical } from "@pmh/domain";
import { buildMarketCorpusSnapshot } from "../../src/market-corpus.js";
import { buildMarketOntologySnapshot } from "../../src/market-ontology.js";
import { buildWorldPredicateArtifact, type WorldPredicateSemanticCore } from "../../src/world-history-ontology.js";
import type { DiscoveryCatalogListing } from "../../src/types.js";
export const start = "2026-10-20T00:00:00.000Z", end = "2026-10-20T23:59:59.999Z";
export const observed = "2026-10-12T00:00:00.000Z";
const hash = (s: string) => hashCanonical({ s });
export function numericFixture(values: readonly string[] = ["25", "30"], overrides: Partial<WorldPredicateSemanticCore> = {}) {
  const listings = values.map((value, i): DiscoveryCatalogListing => {
    const rules = `Resolves Yes if station Alpha daily maximum temperature exceeds ${value} Celsius as reported by "https://example.test/Observation" from ${start} through ${end}. Otherwise resolves No.`;
    return { listingRef: `fixture:threshold-${i}`, venueId: "fixture", venueInstrumentId: `condition-${i}`,
      title: `Synthetic threshold ${value}`, description: "TEST FIXTURE, NOT REAL MARKET", status: "OPEN",
      mechanism: "CENTRALIZED_ORDER_BOOK", closesAt: end, rulesText: rules, rulesTextPosture: "COMPLETE",
      rulesTextSourceCharacterCount: rules.length,
      outcomes: [{ venueOutcomeId: `token-${i}-yes`, label: "Yes", indicativePrice: "0.5" },
        { venueOutcomeId: `token-${i}-no`, label: "No", indicativePrice: "0.5" }],
      priceScale: "1000000", quantityScale: "1000000", minPriceTick: "1000",
      sourceKind: "VERIFIED_FIXTURE", sourceReceivedAt: observed, sourceRawHash: hash(rules), protocolIdentity: "fixture:v1" };
  });
  const corpusInput = { sourceSetIdentity: hash("fixture"), eligibleSourceCount: 1, excludedSourceCount: 0, listings };
  const corpus = buildMarketCorpusSnapshot(corpusInput), ontology = buildMarketOntologySnapshot(corpus);
  const predicates = listings.map((l, i) => {
    const node = ontology.nodes.find(n => n.listingRef === l.listingRef)!;
    return buildWorldPredicateArtifact({
      semantic: { operatorKind: "THRESHOLD", subjects: [{ canonicalLabel: "station Alpha", entityType: "PLACE" }],
        verbPhrase: "daily maximum temperature", polarity: "POSITIVE",
        timeScope: { startsAt: start, endsAt: end, precision: "EXACT_INTERVAL" },
        parameters: [{ name: "comparison", value: "GT", unit: null },
          { name: "threshold", value: values[i]!, unit: "Celsius" },
          { name: "source", value: "https://example.test/Observation", unit: null }], ...overrides },
      evidenceBindings: [{ listingRef: l.listingRef, nodeId: node.nodeId, worldFacetId: node.worldFacet.facetId,
        sourceRawHash: l.sourceRawHash!, protocolIdentity: l.protocolIdentity }],
      source: { sourceOntologyIdentities: [ontology.ontologyIdentity], sourceSnapshotIdentities: [corpus.snapshotIdentity],
        sourceAgentRunIds: [hash("MOCK_LLM_OUTPUT")], sourceToolEffectIds: [] },
      observability: "DERIVED", epistemicPosture: "EVIDENCE_BOUND_PROPOSITION", ambiguityNotes: [], counterworlds: [], proposedAt: observed });
  });
  return { corpus, ontology, predicates, listingRefs: listings.map(l => l.listingRef),
    raw: { corpus: corpusInput, predicates, listingRefs: listings.map(l => l.listingRef) } };
}
