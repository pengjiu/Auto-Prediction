import { hashCanonical } from "@pmh/domain";
import {
  verifyArbitrageCandidate,
  type ArbitrageCandidate,
} from "@pmh/opportunity";
import { describe, expect, it } from "vitest";
import {
  assertCertificateBoundShadowRun,
  assertCertificateBoundShadowMarketObservation,
  observeCertificateBoundShadowMarket,
  runCertificateBoundShadow,
  runOpportunitySimulation,
  type ClobTakerSimulationRequest,
  type OpportunitySimulationPlan,
} from "../src/index.js";

const NOW = 1_785_523_200_100n;
const OBSERVED = 1_785_523_200_000n;
const SCALE = 1_000n;

function request(venueId: string, price: bigint): ClobTakerSimulationRequest {
  return {
    model: "CLOB_TAKER_V1",
    venueId,
    instrumentId: `${venueId}:outcome-token`,
    side: "BUY",
    fillPolicy: "FILL_OR_KILL",
    requestedQuantity: SCALE,
    quantityScale: SCALE,
    collateralScale: SCALE,
    levels: [
      {
        price,
        quantity: SCALE,
        levelIdentity: hashCanonical({ venueId, price }),
      },
    ],
    fee: {
      rate: 0n,
      rateScale: SCALE,
      flat: 0n,
      scheduleHash: hashCanonical({ venueId, fee: 0 }),
    },
    bookStateHash: hashCanonical({ venueId, book: 1 }),
    observedAtEpochMs: OBSERVED,
  };
}

function fixture() {
  const opportunityId = "ai:certificate-shadow-fixture";
  const requests = [request("venue-a", 400n), request("venue-b", 450n)];
  const plan: OpportunitySimulationPlan = {
    schemaVersion: "pmh.opportunity-simulation-plan.v1",
    opportunityId,
    relationConstraintHash: hashCanonical({ relation: "equivalent" }),
    semanticDecisionId: hashCanonical({ decision: "accepted" }),
    portfolioId: hashCanonical({ portfolio: "complete" }),
    canonicalStates: [
      { stateId: "FF", winningLegIds: ["right-false"] },
      { stateId: "TT", winningLegIds: ["left-true"] },
    ],
    legs: [
      {
        legId: "left-true",
        payoutPerWinningUnit: SCALE,
        request: requests[0]!,
      },
      {
        legId: "right-false",
        payoutPerWinningUnit: SCALE,
        request: requests[1]!,
      },
    ],
  };
  const bundle = runOpportunitySimulation(plan);
  const ruleA = hashCanonical({ rule: "a" });
  const ruleB = hashCanonical({ rule: "b" });
  const generationA = hashCanonical({ generation: "a" });
  const generationB = hashCanonical({ generation: "b" });
  const candidate: ArbitrageCandidate = {
    classification: "VENUE_BOUNDED_ARBITRAGE",
    claimGraphHash: plan.relationConstraintHash,
    resolutionPartitionHash: hashCanonical(plan.canonicalStates),
    resolutionStateIds: ["FF", "TT"],
    legs: [
      {
        id: "left-true",
        venueId: "venue-a",
        listingId: "listing-a",
        action: "BUY",
        quantity: SCALE,
        maxQuantity: SCALE,
        quantityScale: SCALE,
        quantityTick: 1n,
        unitPrice: 400n,
        priceTick: 1n,
        fee: { flat: 0n, rate: 0n, rateScale: SCALE },
        payoutPerUnitByResolution: { FF: 0n, TT: SCALE },
        listingRuleHash: ruleA,
        feeScheduleHash: requests[0]!.fee.scheduleHash,
        bookGenerationHash: generationA,
        bookStateHash: requests[0]!.bookStateHash,
      },
      {
        id: "right-false",
        venueId: "venue-b",
        listingId: "listing-b",
        action: "BUY",
        quantity: SCALE,
        maxQuantity: SCALE,
        quantityScale: SCALE,
        quantityTick: 1n,
        unitPrice: 450n,
        priceTick: 1n,
        fee: { flat: 0n, rate: 0n, rateScale: SCALE },
        payoutPerUnitByResolution: { FF: SCALE, TT: 0n },
        listingRuleHash: ruleB,
        feeScheduleHash: requests[1]!.fee.scheduleHash,
        bookGenerationHash: generationB,
        bookStateHash: requests[1]!.bookStateHash,
      },
    ],
    venueAssumptions: [
      `SIMULATION_BUNDLE=${bundle.artifactHash}`,
      "VISIBLE_PUBLIC_BOOK_DEPTH_ONLY",
    ],
    expiresAtEpochMs: OBSERVED + 15_000n,
  };
  const certificate = verifyArbitrageCandidate(candidate, {
    nowEpochMs: NOW,
    claimGraphHash: candidate.claimGraphHash,
    resolutionPartitionHash: candidate.resolutionPartitionHash,
    listingRuleHashById: new Map([
      ["listing-a", ruleA],
      ["listing-b", ruleB],
    ]),
    feeScheduleHashByListingId: new Map([
      ["listing-a", requests[0]!.fee.scheduleHash],
      ["listing-b", requests[1]!.fee.scheduleHash],
    ]),
    bookGenerationHashByListingId: new Map([
      ["listing-a", generationA],
      ["listing-b", generationB],
    ]),
    bookStateHashByListingId: new Map([
      ["listing-a", requests[0]!.bookStateHash],
      ["listing-b", requests[1]!.bookStateHash],
    ]),
  });
  return { opportunityId, bundle, certificate };
}

describe("certificate-bound shadow replay", () => {
  it("runs exact certificate intents through the existing shadow engine", () => {
    const { opportunityId, bundle, certificate } = fixture();
    const run = runCertificateBoundShadow({
      opportunityId,
      certificate,
      simulationBundle: bundle,
      nowEpochMs: NOW,
    });

    expect(run).toMatchObject({
      status: "LOCKED",
      gatewayCalls: 0,
      authority: "SHADOW_REPLAY_ONLY",
      projection: { lifecycle: "LOCKED" },
      effects: {
        externalWrites: false,
        valueMovingActions: false,
        liveExecutionEnabled: false,
      },
    });
    expect(run.observations).toHaveLength(2);
    expect(run.observations.every((item) => item.status === "FILLED")).toBe(true);
    expect(run.capital.map((item) => item.deployed)).toEqual([400n, 450n]);
    expect(() => assertCertificateBoundShadowRun(run)).not.toThrow();
  });

  it("refuses expired certificates before reserving virtual capital", () => {
    const { opportunityId, bundle, certificate } = fixture();
    expect(() =>
      runCertificateBoundShadow({
        opportunityId,
        certificate,
        simulationBundle: bundle,
        nowEpochMs: certificate.expiresAtEpochMs,
      }),
    ).toThrow(/current positive certificate/);
  });

  it("compares a fresh public-book simulation without pretending it observed an order", () => {
    const { opportunityId, bundle, certificate } = fixture();
    const baselineShadow = runCertificateBoundShadow({
      opportunityId,
      certificate,
      simulationBundle: bundle,
      nowEpochMs: NOW,
    });
    const observedBundle = runOpportunitySimulation({
      ...bundle.plan,
      legs: bundle.plan.legs.map((leg, index) => ({
        ...leg,
        request: {
          ...leg.request,
          bookStateHash: hashCanonical({ observed: 2, index }),
          observedAtEpochMs: OBSERVED + 1_000n,
        },
      })) as OpportunitySimulationPlan["legs"],
    });
    const observation = observeCertificateBoundShadowMarket({
      baselineShadow,
      baselineSimulationBundle: bundle,
      observedSimulationBundle: observedBundle,
      sourceMaterializationId: hashCanonical({ materialization: 2 }),
    });

    expect(observation).toMatchObject({
      status: "MATCHED_BOUNDS",
      reasons: [],
      gatewayCalls: 0,
      authority: "FIRST_PARTY_SHADOW_OBSERVER",
      executionAuthority: false,
      comparison: {
        priorSimulationReused: false,
        publicMarketEvidenceOnly: true,
        actualOrderObserved: false,
        certificateReverificationRequired: true,
      },
    });
    expect(observation.legs.every((leg) => leg.inputStateChanged)).toBe(true);
    expect(() =>
      assertCertificateBoundShadowMarketObservation(observation),
    ).not.toThrow();
  });

  it("records an economic shadow divergence from fresh public depth", () => {
    const { opportunityId, bundle, certificate } = fixture();
    const baselineShadow = runCertificateBoundShadow({
      opportunityId,
      certificate,
      simulationBundle: bundle,
      nowEpochMs: NOW,
    });
    const observedBundle = runOpportunitySimulation({
      ...bundle.plan,
      legs: bundle.plan.legs.map((leg, index) => ({
        ...leg,
        request: {
          ...leg.request,
          levels: index === 0
            ? [{ price: 600n, quantity: SCALE, levelIdentity: hashCanonical({ observed: "expensive" }) }]
            : leg.request.model === "CLOB_TAKER_V1" ? leg.request.levels : [],
          bookStateHash: hashCanonical({ observed: "diverged", index }),
          observedAtEpochMs: OBSERVED + 2_000n,
        },
      })) as OpportunitySimulationPlan["legs"],
    });
    const observation = observeCertificateBoundShadowMarket({
      baselineShadow,
      baselineSimulationBundle: bundle,
      observedSimulationBundle: observedBundle,
      sourceMaterializationId: hashCanonical({ materialization: 3 }),
    });

    expect(observation.status).toBe("DIVERGED");
    expect(observation.reasons).toEqual([
      "COST_EXCEEDS_CERTIFICATE_BOUND",
      "NON_POSITIVE_PORTFOLIO_FLOOR",
      "ORDER_LIMIT_EXCEEDED",
    ]);
    expect(observation.legs[0]).toMatchObject({
      status: "DIVERGED",
      reasons: ["COST_EXCEEDS_CERTIFICATE_BOUND", "ORDER_LIMIT_EXCEEDED"],
      plannedMaxDebit: 400n,
      observedDebit: 600n,
    });
    expect(observation.effects.liveExecutionEnabled).toBe(false);
  });

  it("records changed plan scope instead of dropping the observation", () => {
    const { opportunityId, bundle, certificate } = fixture();
    const baselineShadow = runCertificateBoundShadow({
      opportunityId,
      certificate,
      simulationBundle: bundle,
      nowEpochMs: NOW,
    });
    const observedBundle = runOpportunitySimulation({
      ...bundle.plan,
      legs: [
        ...bundle.plan.legs,
        {
          legId: "new-market-leg",
          payoutPerWinningUnit: SCALE,
          request: {
            ...request("venue-c", 10n),
            observedAtEpochMs: OBSERVED + 3_000n,
          },
        },
      ],
    });
    const observation = observeCertificateBoundShadowMarket({
      baselineShadow,
      baselineSimulationBundle: bundle,
      observedSimulationBundle: observedBundle,
      sourceMaterializationId: hashCanonical({ materialization: 4 }),
    });

    expect(observation).toMatchObject({
      status: "DIVERGED",
      reasons: ["NON_LATER_OBSERVATION", "PLAN_SCOPE_CHANGED"],
      comparison: {
        actualOrderObserved: false,
        certificateReverificationRequired: true,
      },
    });
    expect(observation.legs).toHaveLength(2);
    expect(observation.legs.every((leg) =>
      leg.reasons.includes("PLAN_SCOPE_CHANGED")
    )).toBe(true);
  });
});

// Adversarial review: a later snapshot must remain executable by the OLD order.
describe("review: later shadow observation", () => {
  function observed(change: (r: ClobTakerSimulationRequest, i: number) => ClobTakerSimulationRequest) {
    const { opportunityId, bundle, certificate } = fixture();
    const baselineShadow = runCertificateBoundShadow({ opportunityId, certificate,
      simulationBundle: bundle, nowEpochMs: NOW });
    const next = runOpportunitySimulation({ ...bundle.plan,
      legs: bundle.plan.legs.map((leg, i) => ({ ...leg,
        request: change({ ...(leg.request as ClobTakerSimulationRequest),
          observedAtEpochMs: OBSERVED + 1000n,
          bookStateHash: hashCanonical({ revision: 2, i }) }, i) })) });
    return observeCertificateBoundShadowMarket({ baselineShadow,
      baselineSimulationBundle: bundle, observedSimulationBundle: next,
      sourceMaterializationId: hashCanonical({ next: 2 }) });
  }
  it("rejects above-limit fills even when their average is within budget", () => {
    const o = observed((r, i) => i ? r : { ...r, levels: [
      { price: 300n, quantity: 500n, levelIdentity: hashCanonical({ p: 300 }) },
      { price: 500n, quantity: 500n, levelIdentity: hashCanonical({ p: 500 }) },
    ] });
    expect(o.status).toBe("DIVERGED");
    expect(o.reasons).toContain("ORDER_LIMIT_EXCEEDED");
  });
  it("rejects a different native token", () => {
    expect(observed((r, i) => i ? r : { ...r, instrumentId: "different-token" }).status).toBe("DIVERGED");
  });
  it("rejects old observations relabelled as later evidence", () => {
    expect(observed(r => ({ ...r, observedAtEpochMs: OBSERVED - 1n })).status).toBe("DIVERGED");
  });
  it("requires review after a changed fee schedule", () => {
    expect(observed(r => ({ ...r, fee: { ...r.fee, scheduleHash: hashCanonical({ fee: "changed" }) } })).status).toBe("DIVERGED");
  });
  it("rejects rehashed success labels that erase a known divergence", () => {
    const o = observed((r, i) => i ? r : { ...r, levels: [
      { price: 600n, quantity: SCALE, levelIdentity: hashCanonical({ p: 600 }) },
    ] });
    const { artifactHash: _hash, ...body } = o;
    const forged = { ...body, status: "MATCHED_BOUNDS", reasons: [],
      legs: body.legs.map(leg => ({ ...leg, status: "MATCHED_BOUNDS", reasons: [] })) };
    expect(() => assertCertificateBoundShadowMarketObservation({ ...forged,
      artifactHash: hashCanonical(forged) })).toThrow();
  });
});
