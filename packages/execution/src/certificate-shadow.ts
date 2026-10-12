import { CapitalLedger, type VenueCapitalProjection } from "@pmh/capital";
import { assertBuyOrderReplay } from "./buy-order-budget.js";
import { divideCeil, hashCanonical, type Hash } from "@pmh/domain";
import type { ArbitrageCertificate, CandidateLeg } from "@pmh/opportunity";
import { RiskGovernor } from "@pmh/risk";
import {
  assertOpportunitySimulationBundle,
  type OpportunitySimulationBundle,
} from "./opportunity-simulation.js";
import { ShadowExecutionEngine } from "./shadow-engine.js";
import type {
  ExecutionPlan,
  ExecutionProjection,
  OrderIntent,
} from "./types.js";

const HASH_PATTERN = /^sha256:[0-9a-f]{64}$/u;

export type CertificateBoundShadowObservation = Readonly<{
  intentId: string;
  certificateLegId: string;
  venueId: string;
  listingId: string;
  plannedQuantity: bigint;
  observedQuantity: bigint;
  plannedLimitPrice: bigint;
  plannedMaxDebit: bigint;
  observedDebit: bigint;
  debitHeadroom: bigint;
  sourceSimulationReportHash: Hash;
  status: "FILLED";
}>;

export type CertificateBoundShadowRun = Readonly<{
  schemaVersion: "pmh.certificate-bound-shadow-run.v1";
  artifactHash: Hash;
  opportunityId: string;
  certificateId: Hash;
  simulationBundleHash: Hash;
  executionPlan: ExecutionPlan;
  projection: ExecutionProjection;
  observations: readonly CertificateBoundShadowObservation[];
  capital: readonly VenueCapitalProjection[];
  status: "LOCKED";
  gatewayCalls: 0;
  authority: "SHADOW_REPLAY_ONLY";
  effects: Readonly<{
    externalWrites: false;
    valueMovingActions: false;
    liveExecutionEnabled: false;
  }>;
}>;

export type ShadowMarketDivergenceReason =
  | "PLAN_SCOPE_CHANGED"
  | "INCOMPLETE_FILL"
  | "QUANTITY_MISMATCH"
  | "COST_EXCEEDS_CERTIFICATE_BOUND"
  | "MODEL_NOT_EXACT"
  | "NON_POSITIVE_PORTFOLIO_FLOOR"
  | "ORDER_LIMIT_EXCEEDED"
  | "ORDER_REPLAY_INVALID"
  | "FEE_SCHEDULE_CHANGED"
  | "NON_LATER_OBSERVATION";

export type CertificateBoundShadowMarketObservation = Readonly<{
  schemaVersion: "pmh.certificate-bound-shadow-market-observation.v2";
  artifactHash: Hash;
  opportunityId: string;
  baselineShadowArtifactHash: Hash;
  certificateId: Hash;
  baselineSimulationBundleHash: Hash;
  sourceMaterializationId: Hash;
  baselineShadow: CertificateBoundShadowRun;
  baselineSimulationBundle: OpportunitySimulationBundle;
  observedSimulationBundle: OpportunitySimulationBundle;
  observedAtEpochMs: bigint;
  status: "MATCHED_BOUNDS" | "DIVERGED";
  reasons: readonly ShadowMarketDivergenceReason[];
  legs: readonly Readonly<{
    intentId: string;
    certificateLegId: string;
    venueId: string;
    plannedQuantity: bigint;
    observedQuantity: bigint;
    plannedMaxDebit: bigint;
    observedDebit: bigint;
    inputStateChanged: boolean;
    feeScheduleChanged: boolean;
    status: "MATCHED_BOUNDS" | "DIVERGED";
    reasons: readonly ShadowMarketDivergenceReason[];
    sourceSimulationReportHash: Hash;
  }>[];
  comparison: Readonly<{
    priorSimulationReused: false;
    publicMarketEvidenceOnly: true;
    actualOrderObserved: false;
    certificateReverificationRequired: true;
  }>;
  gatewayCalls: 0;
  authority: "FIRST_PARTY_SHADOW_OBSERVER";
  executionAuthority: false;
  effects: Readonly<{
    externalWrites: false;
    valueMovingActions: false;
    liveExecutionEnabled: false;
  }>;
}>;

function certificateDebit(leg: CandidateLeg): bigint {
  const notional = divideCeil(
    leg.quantity * leg.unitPrice,
    leg.quantityScale,
  );
  return (
    notional +
    leg.fee.flat +
    divideCeil(notional * leg.fee.rate, leg.fee.rateScale)
  );
}

function assertCertificate(certificate: ArbitrageCertificate): void {
  const { id, ...body } = certificate;
  if (
    !HASH_PATTERN.test(id) ||
    id !== hashCanonical(body) ||
    (certificate.classification !== "CERTIFIED_CONTRACT_ARBITRAGE" &&
      certificate.classification !== "VENUE_BOUNDED_ARBITRAGE") ||
    certificate.worstCaseAfterFees <= 0n ||
    certificate.legs.length < 2
  ) {
    throw new Error("certificate-bound shadow input is not an exact arbitrage");
  }
}

function buildExecutionPlan(
  certificate: ArbitrageCertificate,
): ExecutionPlan {
  const intents: OrderIntent[] = certificate.legs.map((leg) => {
    const intentIdentity = hashCanonical({
      certificateId: certificate.id,
      certificateLegId: leg.id,
      kind: "SHADOW_ORDER_INTENT",
    });
    const maxDebit = certificateDebit(leg);
    if (maxDebit <= 0n) {
      throw new Error("zero-debit certificate legs require another shadow model");
    }
    return Object.freeze({
      id: intentIdentity,
      certificateLegId: leg.id,
      venueId: leg.venueId,
      listingId: leg.listingId,
      clientOrderId: `shadow:${intentIdentity.slice(7, 31)}`,
      side: leg.action,
      quantity: leg.quantity,
      quantityScale: leg.quantityScale,
      limitPrice: leg.unitPrice,
      maxDebit,
    });
  });
  const planBody = Object.freeze({
    certificateId: certificate.id,
    intents: Object.freeze(intents),
    dependencies: Object.freeze([]),
    hedgeCheckpoints: Object.freeze(
      intents.map((intent) =>
        Object.freeze({
          afterIntentId: intent.id,
          maxResidualExposure: intents.reduce(
            (total, item) => total + item.maxDebit,
            0n,
          ),
          alternativeIntentIds: Object.freeze(
            intents
              .filter((item) => item.id !== intent.id)
              .map((item) => item.id),
          ),
        }),
      ),
    ),
    abortPolicies: Object.freeze([
      Object.freeze({ trigger: "REJECTED" as const, action: "CANCEL_OPEN" as const }),
      Object.freeze({ trigger: "UNKNOWN" as const, action: "RECONCILE" as const }),
      Object.freeze({ trigger: "TIMEOUT" as const, action: "CANCEL_OPEN" as const }),
      Object.freeze({ trigger: "RISK_KILL" as const, action: "CANCEL_OPEN" as const }),
    ]),
  });
  return Object.freeze({ id: hashCanonical(planBody), ...planBody });
}

export function assertCertificateBoundShadowRun(
  value: unknown,
): CertificateBoundShadowRun {
  if (value === null || typeof value !== "object") {
    throw new Error("certificate-bound shadow run is malformed");
  }
  const run = value as CertificateBoundShadowRun;
  const { artifactHash, ...body } = run;
  if (
    run.schemaVersion !== "pmh.certificate-bound-shadow-run.v1" ||
    !HASH_PATTERN.test(artifactHash) ||
    artifactHash !== hashCanonical(body) ||
    run.opportunityId.trim() === "" ||
    !HASH_PATTERN.test(run.certificateId) ||
    !HASH_PATTERN.test(run.simulationBundleHash) ||
    run.executionPlan.certificateId !== run.certificateId ||
    run.projection.planId !== run.executionPlan.id ||
    run.projection.lifecycle !== "LOCKED" ||
    run.status !== "LOCKED" ||
    run.gatewayCalls !== 0 ||
    !Array.isArray(run.observations) ||
    run.observations.length !== run.executionPlan.intents.length ||
    run.observations.some(
      (observation) =>
        observation.status !== "FILLED" ||
        observation.observedQuantity !== observation.plannedQuantity ||
        observation.observedDebit <= 0n ||
        observation.observedDebit > observation.plannedMaxDebit ||
        observation.debitHeadroom !==
          observation.plannedMaxDebit - observation.observedDebit ||
        !HASH_PATTERN.test(observation.sourceSimulationReportHash),
    ) ||
    run.authority !== "SHADOW_REPLAY_ONLY" ||
    run.effects.externalWrites !== false ||
    run.effects.valueMovingActions !== false ||
    run.effects.liveExecutionEnabled !== false
  ) {
    throw new Error("certificate-bound shadow run violates its contract");
  }
  return run;
}

export function runCertificateBoundShadow(input: {
  opportunityId: string;
  certificate: ArbitrageCertificate;
  simulationBundle: OpportunitySimulationBundle;
  nowEpochMs?: bigint;
}): CertificateBoundShadowRun {
  assertCertificate(input.certificate);
  const bundle = assertOpportunitySimulationBundle(input.simulationBundle);
  const nowEpochMs = input.nowEpochMs ?? BigInt(Date.now());
  if (
    input.opportunityId.trim() === "" ||
    input.opportunityId !== bundle.opportunityId ||
    bundle.status !== "POSITIVE_SIMULATED_FLOOR" ||
    input.certificate.expiresAtEpochMs <= nowEpochMs ||
    !input.certificate.venueAssumptions.includes(
      `SIMULATION_BUNDLE=${bundle.artifactHash}`,
    ) ||
    input.certificate.legs.length !== bundle.reports.length
  ) {
    throw new Error("shadow replay does not bind a current positive certificate");
  }
  const plan = buildExecutionPlan(input.certificate);
  const initialCapitalByVenue = new Map<string, bigint>();
  for (const intent of plan.intents) {
    initialCapitalByVenue.set(
      intent.venueId,
      (initialCapitalByVenue.get(intent.venueId) ?? 0n) + intent.maxDebit,
    );
  }
  const totalCapital = [...initialCapitalByVenue.values()].reduce(
    (total, amount) => total + amount,
    0n,
  );
  const capital = new CapitalLedger(initialCapitalByVenue);
  const risk = new RiskGovernor({
    liveExecutionEnabled: false,
    maxCapitalByVenue: new Map(initialCapitalByVenue),
    maxUnresolvedCapital: totalCapital,
    maxResidualExposure: totalCapital,
    maxCancelLatencyMs: 0n,
    maxHeartbeatAgeMs: 0n,
  });
  const engine = new ShadowExecutionEngine(capital, risk);
  engine.reservePlan(plan, {
    mode: "SHADOW",
    nowEpochMs,
    certificate: input.certificate,
    books: bundle.reports.map((report, index) =>
      Object.freeze({
        instrumentId: input.certificate.legs[index]!.listingId,
        lifecycle: "SNAPSHOT_VALID" as const,
        generation: 1n,
        bids: Object.freeze([]),
        asks: Object.freeze([]),
      }),
    ),
    capital: Object.freeze([]),
    residualExposure: 0n,
    cancelLatencyMs: 0n,
    heartbeatAgeMs: 0n,
    localVenueStateDiverged: false,
  });
  const observations: CertificateBoundShadowObservation[] = [];
  for (const [index, intent] of plan.intents.entries()) {
    const report = bundle.reports[index]!;
    const certificateLeg = input.certificate.legs[index]!;
    if (
      intent.certificateLegId !== certificateLeg.id ||
      report.status !== "FULL" ||
      report.action !== certificateLeg.action ||
      report.venueId !== intent.venueId ||
      report.inputStateHash !== certificateLeg.bookStateHash ||
      report.feeScheduleHash !== certificateLeg.feeScheduleHash ||
      report.filledQuantity !== intent.quantity ||
      report.netCollateral <= 0n ||
      report.netCollateral > intent.maxDebit
    ) {
      throw new Error("shadow observation diverges from its certificate intent");
    }
    // Revalidate the generated order, not just the original VWAP simulation.
    // A snapshot filled above this limit is not a fill of this order.
    assertBuyOrderReplay({
      action: intent.side,
      quantity: intent.quantity,
      quantityScale: intent.quantityScale,
      reportQuantityScale: report.quantityScale,
      collateralScale: report.collateralScale,
      grossCollateral: report.grossCollateral,
      netCollateral: report.netCollateral,
      fills: report.fills,
      limitPrice: intent.limitPrice,
      maximumDebit: intent.maxDebit,
    });
    engine.submit(plan.id, intent.id);
    engine.acknowledge(
      plan.id,
      intent.id,
      `shadow-order:${intent.id.slice(7, 23)}`,
    );
    engine.fill(
      plan.id,
      intent.id,
      report.filledQuantity,
      report.netCollateral,
    );
    observations.push(
      Object.freeze({
        intentId: intent.id,
        certificateLegId: certificateLeg.id,
        venueId: intent.venueId,
        listingId: intent.listingId,
        plannedQuantity: intent.quantity,
        observedQuantity: report.filledQuantity,
        plannedLimitPrice: intent.limitPrice,
        plannedMaxDebit: intent.maxDebit,
        observedDebit: report.netCollateral,
        debitHeadroom: intent.maxDebit - report.netCollateral,
        sourceSimulationReportHash: report.artifactHash,
        status: "FILLED" as const,
      }),
    );
  }
  const projection = engine.projection(plan.id);
  if (projection.lifecycle !== "LOCKED") {
    throw new Error("certificate-bound shadow replay did not lock every leg");
  }
  const body = Object.freeze({
    schemaVersion: "pmh.certificate-bound-shadow-run.v1" as const,
    opportunityId: input.opportunityId,
    certificateId: input.certificate.id,
    simulationBundleHash: bundle.artifactHash,
    executionPlan: plan,
    projection,
    observations: Object.freeze(observations),
    capital: Object.freeze(capital.projections()),
    status: "LOCKED" as const,
    gatewayCalls: 0 as const,
    authority: "SHADOW_REPLAY_ONLY" as const,
    effects: Object.freeze({
      externalWrites: false as const,
      valueMovingActions: false as const,
      liveExecutionEnabled: false as const,
    }),
  });
  return assertCertificateBoundShadowRun({
    ...body,
    artifactHash: hashCanonical(body),
  });
}

function sameShadowScope(
  baseline: OpportunitySimulationBundle,
  observed: OpportunitySimulationBundle,
): boolean {
  return (
    baseline.opportunityId === observed.opportunityId &&
    baseline.relationConstraintHash === observed.relationConstraintHash &&
    baseline.semanticDecisionId === observed.semanticDecisionId &&
    baseline.portfolioId === observed.portfolioId &&
    hashCanonical(baseline.plan.canonicalStates) ===
      hashCanonical(observed.plan.canonicalStates) &&
    hashCanonical(baseline.plan.legs.map((item) => ({
      legId: item.legId,
      payoutPerWinningUnit: item.payoutPerWinningUnit,
      venueId: item.request.venueId,
      instrumentId: item.request.instrumentId,
      model: item.request.model,
      quantityScale: item.request.quantityScale,
      collateralScale: item.request.collateralScale,
      side: item.request.model === "CLOB_TAKER_V1" ? item.request.side : item.request.action,
      fillPolicy: item.request.model === "CLOB_TAKER_V1" ? item.request.fillPolicy : null,
      quantity: item.request.model === "CLOB_TAKER_V1" ? item.request.requestedQuantity : item.request.outcomeQuantity,
    }))) === hashCanonical(observed.plan.legs.map((item) => ({
      legId: item.legId,
      payoutPerWinningUnit: item.payoutPerWinningUnit,
      venueId: item.request.venueId,
      instrumentId: item.request.instrumentId,
      model: item.request.model,
      quantityScale: item.request.quantityScale,
      collateralScale: item.request.collateralScale,
      side: item.request.model === "CLOB_TAKER_V1" ? item.request.side : item.request.action,
      fillPolicy: item.request.model === "CLOB_TAKER_V1" ? item.request.fillPolicy : null,
      quantity: item.request.model === "CLOB_TAKER_V1" ? item.request.requestedQuantity : item.request.outcomeQuantity,
    })))
  );
}

export function assertCertificateBoundShadowMarketObservation(
  value: unknown,
): CertificateBoundShadowMarketObservation {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("certificate-bound shadow market observation is malformed");
  }
  const observation = value as CertificateBoundShadowMarketObservation;
  const { artifactHash, ...body } = observation;
  const expected = buildShadowMarketObservation({
    baselineShadow: observation.baselineShadow,
    baselineSimulationBundle: observation.baselineSimulationBundle,
    observedSimulationBundle: observation.observedSimulationBundle,
    sourceMaterializationId: observation.sourceMaterializationId,
  });
  if (!HASH_PATTERN.test(String(artifactHash)) || artifactHash !== hashCanonical(body) ||
      artifactHash !== hashCanonical(expected)) {
    throw new Error("certificate-bound shadow observation does not replay its exact inputs");
  }
  return observation;
}

function buildShadowMarketObservation(input: {
  baselineShadow: CertificateBoundShadowRun;
  baselineSimulationBundle: OpportunitySimulationBundle;
  observedSimulationBundle: OpportunitySimulationBundle;
  sourceMaterializationId: Hash;
}): Omit<CertificateBoundShadowMarketObservation, "artifactHash"> {
  const baselineShadow = assertCertificateBoundShadowRun(input.baselineShadow);
  const baseline = assertOpportunitySimulationBundle(
    input.baselineSimulationBundle,
  );
  const observed = assertOpportunitySimulationBundle(
    input.observedSimulationBundle,
  );
  if (
    baselineShadow.opportunityId !== baseline.opportunityId ||
    baselineShadow.simulationBundleHash !== baseline.artifactHash ||
    baselineShadow.certificateId !== baselineShadow.executionPlan.certificateId ||
    !HASH_PATTERN.test(input.sourceMaterializationId)
  ) {
    throw new Error("shadow market observation baseline is not artifact-bound");
  }
  const scopeMatches = sameShadowScope(baseline, observed);
  const observedByLeg = new Map(
    observed.plan.legs.map((leg, index) => [leg.legId, observed.reports[index]!] as const),
  );
  const baselineByLeg = new Map(
    baseline.plan.legs.map((leg, index) => [leg.legId, baseline.reports[index]!] as const),
  );
  const baselineLatest = baseline.reports.reduce(
    (latest, report) => report.observedAtEpochMs > latest ? report.observedAtEpochMs : latest, 0n,
  );
  const globalReasons: ShadowMarketDivergenceReason[] = [];
  if (!scopeMatches) globalReasons.push("PLAN_SCOPE_CHANGED");
  if (observed.status !== "POSITIVE_SIMULATED_FLOOR") {
    globalReasons.push("NON_POSITIVE_PORTFOLIO_FLOOR");
  }
  const legs = Object.freeze(baselineShadow.executionPlan.intents.map((intent) => {
    const report = observedByLeg.get(intent.certificateLegId);
    const baselineReport = baselineByLeg.get(intent.certificateLegId);
    const reasons: ShadowMarketDivergenceReason[] = [];
    if (report === undefined || baselineReport === undefined || !scopeMatches) {
      reasons.push("PLAN_SCOPE_CHANGED");
    }
    if (report !== undefined) {
      if (report.fills.some((fill) => fill.price > intent.limitPrice)) {
        reasons.push("ORDER_LIMIT_EXCEEDED");
      }
      if (report.observedAtEpochMs <= baselineLatest) reasons.push("NON_LATER_OBSERVATION");
      if (baselineReport !== undefined && report.feeScheduleHash !== baselineReport.feeScheduleHash) {
        reasons.push("FEE_SCHEDULE_CHANGED");
      }
      if (report.status !== "FULL") reasons.push("INCOMPLETE_FILL");
      if (report.filledQuantity !== intent.quantity) reasons.push("QUANTITY_MISMATCH");
      if (report.netCollateral > intent.maxDebit) {
        reasons.push("COST_EXCEEDS_CERTIFICATE_BOUND");
      }
      if (report.modelQualification !== "BOOK_EXACT_TAKER_WALK") {
        reasons.push("MODEL_NOT_EXACT");
      }
      if (report.status === "FULL" && scopeMatches && report.filledQuantity === intent.quantity) {
        try {
          assertBuyOrderReplay({ action: report.action, quantity: intent.quantity,
            quantityScale: intent.quantityScale, reportQuantityScale: report.quantityScale,
            collateralScale: report.collateralScale, grossCollateral: report.grossCollateral,
            netCollateral: report.netCollateral, fills: report.fills,
            limitPrice: intent.limitPrice, maximumDebit: intent.maxDebit });
        } catch {
          if (!reasons.includes("ORDER_LIMIT_EXCEEDED") && !reasons.includes("COST_EXCEEDS_CERTIFICATE_BOUND")) {
            reasons.push("ORDER_REPLAY_INVALID");
          }
        }
      }
    }
    const uniqueReasons = Object.freeze([...new Set(reasons)].sort());
    const legStatus = uniqueReasons.length === 0 ? "MATCHED_BOUNDS" as const : "DIVERGED" as const;
    return Object.freeze({
      intentId: intent.id,
      certificateLegId: intent.certificateLegId,
      venueId: intent.venueId,
      plannedQuantity: intent.quantity,
      observedQuantity: report?.filledQuantity ?? 0n,
      plannedMaxDebit: intent.maxDebit,
      observedDebit: report?.netCollateral ?? 0n,
      inputStateChanged:
        report !== undefined && baselineReport !== undefined &&
        report.inputStateHash !== baselineReport.inputStateHash,
      feeScheduleChanged:
        report !== undefined && baselineReport !== undefined &&
        report.feeScheduleHash !== baselineReport.feeScheduleHash,
      status: legStatus,
      reasons: uniqueReasons,
      sourceSimulationReportHash: report?.artifactHash ?? observed.artifactHash,
    });
  }));
  for (const leg of legs) globalReasons.push(...leg.reasons);
  const reasons = Object.freeze([...new Set(globalReasons)].sort());
  const body = Object.freeze({
    schemaVersion: "pmh.certificate-bound-shadow-market-observation.v2" as const,
    opportunityId: baselineShadow.opportunityId,
    baselineShadowArtifactHash: baselineShadow.artifactHash,
    certificateId: baselineShadow.certificateId,
    baselineSimulationBundleHash: baseline.artifactHash,
    sourceMaterializationId: input.sourceMaterializationId,
    baselineShadow,
    baselineSimulationBundle: baseline,
    observedSimulationBundle: observed,
    observedAtEpochMs: observed.reports.reduce(
      (latest, report) => report.observedAtEpochMs > latest ? report.observedAtEpochMs : latest,
      0n,
    ),
    status: reasons.length === 0 ? "MATCHED_BOUNDS" as const : "DIVERGED" as const,
    reasons,
    legs,
    comparison: Object.freeze({
      priorSimulationReused: false as const,
      publicMarketEvidenceOnly: true as const,
      actualOrderObserved: false as const,
      certificateReverificationRequired: true as const,
    }),
    gatewayCalls: 0 as const,
    authority: "FIRST_PARTY_SHADOW_OBSERVER" as const,
    executionAuthority: false as const,
    effects: Object.freeze({
      externalWrites: false as const,
      valueMovingActions: false as const,
      liveExecutionEnabled: false as const,
    }),
  });
  return body;
}

export function observeCertificateBoundShadowMarket(
  input: Parameters<typeof buildShadowMarketObservation>[0],
): CertificateBoundShadowMarketObservation {
  const body = buildShadowMarketObservation(input);
  return Object.freeze({ ...body, artifactHash: hashCanonical(body) });
}
