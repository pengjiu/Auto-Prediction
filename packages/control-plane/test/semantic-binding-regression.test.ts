import { hashCanonical } from "@pmh/domain";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  adaptMarketOntologyWorldProposition,
  buildMarketCorpusSnapshot,
  buildMarketOntologySnapshot,
  buildDiscoveryEvidenceLocator,
  buildEvidenceDocumentFetchPolicy,
  buildEvidenceRequirements,
  compileSettlementProjections,
  EvidenceDocumentFetcher,
  settlementVenuePolicyEvidenceFromCaptures,
  type DiscoveryCatalogListing,
  type MarketOntologyWorldPropositionProposal,
  SqliteOperationalStore,
} from "../src/index.js";

const at = "2026-08-14T00:00:00.000Z";
const hash = (label: string) => hashCanonical({ label });

function listing(overrides: Partial<DiscoveryCatalogListing> = {}): DiscoveryCatalogListing {
  return Object.freeze({
    listingRef: "fixture:cola", venueId: "fixture", venueInstrumentId: "cola",
    title: "Will Donald Trump drink cola on a livestream?", description: "Fixture.",
    status: "OPEN", mechanism: "CENTRALIZED_ORDER_BOOK", closesAt: null,
    rulesText: "Resolves Yes if Donald Trump drinks cola on a livestream. Otherwise resolves No.",
    rulesTextPosture: "COMPLETE", rulesTextSourceCharacterCount: 80,
    outcomes: [{ venueOutcomeId: "yes", label: "Yes", indicativePrice: "0.4" },
      { venueOutcomeId: "no", label: "No", indicativePrice: "0.6" }],
    priceScale: "1000000", quantityScale: "1000000", minPriceTick: "1000",
    sourceKind: "VERIFIED_FIXTURE", sourceReceivedAt: at,
    sourceRawHash: hash("raw"), protocolIdentity: "fixture:v1", ...overrides,
  });
}

function fixture(overrides: Partial<DiscoveryCatalogListing> = {}) {
  const corpus = buildMarketCorpusSnapshot({ sourceSetIdentity: hash("source-set"),
    eligibleSourceCount: 1, excludedSourceCount: 0, listings: [listing(overrides)] });
  const ontology = buildMarketOntologySnapshot(corpus);
  const node = ontology.nodes[0]!;
  const proposal = {
    schemaVersion: "pmh.market-ontology-agent-proposal.v1", kind: "WORLD_PROPOSITION",
    proposalId: hash("proposal"), ontologyIdentity: ontology.ontologyIdentity,
    sourceSnapshotIdentity: corpus.snapshotIdentity, sourceAgentRunId: hash("run"),
    sourceTrailheadIds: [hash("trailhead")], sourceRelationPatternIds: [hash("pattern")],
    listingBindings: [{ listingRef: node.listingRef, nodeId: node.nodeId,
      worldFacetId: node.worldFacet.facetId, settlementFacetId: node.settlementFacet.facetId,
      tradedFacetId: node.tradedFacet.facetId }],
    label: "Trump drinks cola on a livestream", subjectLabels: ["Donald Trump"],
    predicate: "drinks cola on a livestream", timeScope: null, parameters: [],
    ambiguityNotes: [], falsifiers: ["The drink is not cola."], rationale: "Fixture.",
    proposedAt: at, authority: "PROPOSE_ONLY", reviewStatus: "UNREVIEWED",
    semanticDecisionAuthority: false, probabilityAuthority: false, certificateAuthority: false,
    executionAuthority: false, externalWriteAuthority: false, valueMovingAuthority: false,
  } as const satisfies MarketOntologyWorldPropositionProposal;
  return { corpus, ontology, predicate: adaptMarketOntologyWorldProposition({ proposal, ontology }) };
}


import { buildWorldPredicateArtifact } from "../src/world-history-ontology.js";

const findings: unknown[] = [];
function inspectCase(name: string, input: ReturnType<typeof fixture>, semantic = input.predicate.semantic) {
  const predicate = buildWorldPredicateArtifact({ ...input.predicate, semantic });
  const result = compileSettlementProjections({ ...input, predicates: [predicate] });
  const observation = result.observations[0]!;
  findings.push({ name, inputSemantic: predicate.semantic, rules: input.corpus.listings[0]!.rulesText,
    disposition: observation.disposition, blockers: observation.blockers,
    admission: result.projections[0]?.compilerAdmission,
    truthStates: result.projections[0]?.truthStates.map(s => ({stateId:s.stateId,listingTruth:s.listingTruth})) });

  return result;
}
describe("next-step semantic correctness review", () => {
  it("positive control: matching explicit condition", () => {
    const i=fixture();
    expect(inspectCase("control", i).observations[0]!.disposition).toBe("EXACT_PROJECTED");
  });
  it("must not certify positive identity for a negated predicate", () => {
    const i=fixture();
    const r=inspectCase("negated_predicate", i, {...i.predicate.semantic,polarity:"NEGATED"});
    expect(r.projections[0]?.truthStates.map(s=>s.listingTruth)).toEqual([true,false]);
  });
  it("must not certify an explicit inverse resolution clause as identity", () => {
    const rulesText="Resolves Yes if it is false that Donald Trump drinks cola on a livestream. Otherwise resolves No.";
    const i=fixture({rulesText,rulesTextSourceCharacterCount:rulesText.length});
    expect(inspectCase("inverted_rule",i).projections[0]?.truthStates.map(s=>s.listingTruth)).toEqual([true,false]);
  });
  it("must not discard an extra required condition", () => {
    const rulesText="Resolves Yes if Donald Trump drinks cola on a livestream and wins a marathon. Otherwise resolves No.";
    const i=fixture({rulesText,rulesTextSourceCharacterCount:rulesText.length});
    expect(inspectCase("missing_conjunct",i).observations[0]!.disposition).not.toBe("EXACT_PROJECTED");
  });
  it("must distinguish a 25 threshold from a 30 threshold", () => {
    const rulesText="Resolves Yes if station Alpha daily temperature exceeds 30 Celsius. Otherwise resolves No.";
    const i=fixture({title:"Will station Alpha daily temperature exceed 30 Celsius?",rulesText,rulesTextSourceCharacterCount:rulesText.length});
    const semantic={...i.predicate.semantic,operatorKind:"THRESHOLD" as const,
      subjects:[{canonicalLabel:"station Alpha",entityType:"PLACE" as const}],
      verbPhrase:"daily temperature exceeds 25 Celsius",parameters:[]};
    expect(inspectCase("threshold_25_vs_30",i,semantic).observations[0]!.disposition).not.toBe("EXACT_PROJECTED");
  });
  it("must verify measurement units rather than ignore them", () => {
    const rulesText="Resolves Yes if station Alpha daily temperature exceeds 30 Celsius. Otherwise resolves No.";
    const i=fixture({title:"Will station Alpha daily temperature exceed 30 Celsius?",rulesText,rulesTextSourceCharacterCount:rulesText.length});
    const semantic={...i.predicate.semantic,operatorKind:"THRESHOLD" as const,
      subjects:[{canonicalLabel:"station Alpha",entityType:"PLACE" as const}],
      verbPhrase:"daily temperature exceeds",parameters:[{name:"temperature",value:"30",unit:"Fahrenheit"}]};
    expect(inspectCase("fahrenheit_vs_celsius",i,semantic).observations[0]!.disposition).not.toBe("EXACT_PROJECTED");
  });
  it("must verify the observation interval", () => {
    const rulesText="Resolves Yes if Donald Trump drinks cola on a livestream on October 20, 2026. Otherwise resolves No.";
    const i=fixture({rulesText,rulesTextSourceCharacterCount:rulesText.length});
    const semantic={...i.predicate.semantic,timeScope:{startsAt:"2027-10-20T00:00:00.000Z",endsAt:"2027-10-20T23:59:59.999Z",precision:"EXACT_INTERVAL" as const}};
    expect(inspectCase("wrong_year_interval",i,semantic).observations[0]!.disposition).not.toBe("EXACT_PROJECTED");
  });
});
