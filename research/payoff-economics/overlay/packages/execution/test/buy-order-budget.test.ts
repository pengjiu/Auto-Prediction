import { describe, it } from "vitest";
import assert from "node:assert/strict";
import { divideCeil, hashCanonical } from "@pmh/domain";
import { verifyArbitrageCandidate, type ArbitrageCandidate, type VerificationContext } from "@pmh/opportunity";
import { buildConservativeBuyBudget, assertBuyOrderReplay } from "../src/buy-order-budget.js";

const fee = { flat: 0n, rate: 0n, rateScale: 1000n };
function source() {
  return {
    quantity: 100_000n, quantityScale: 1000n, collateralScale: 1000n,
    grossCollateral: 50_000n, netCollateral: 50_000n, priceTick: 10n, fee,
    fills: [
      { levelIdentity: "low", quantity: 50_000n, price: 400n, collateral: 20_000n },
      { levelIdentity: "high", quantity: 50_000n, price: 600n, collateral: 30_000n },
    ],
  };
}
function replay() {
  return {
    ...source(), action: "BUY" as const, reportQuantityScale: 1000n,
    limitPrice: 600n, maximumDebit: 60_000n,
  };
}
function candidate(price: bigint): ArbitrageCandidate {
  return {
    classification: "VENUE_BOUNDED_ARBITRAGE", claimGraphHash: hashCanonical("claim"),
    resolutionPartitionHash: hashCanonical(["yes", "no"]), resolutionStateIds: ["yes", "no"],
    expiresAtEpochMs: 2000n, venueAssumptions: ["SYNTHETIC_SETTLEMENT_MODEL"],
    legs: [price, 450n].map((unitPrice, index) => ({
      id: `leg-${index}`, venueId: "test", listingId: `listing-${index}`, action: "BUY" as const,
      quantity: 100_000n, maxQuantity: 100_000n, quantityScale: 1000n,
      quantityTick: 1n, unitPrice, priceTick: 1n, fee,
      payoutPerUnitByResolution: { yes: index === 0 ? 1000n : 0n, no: index === 1 ? 1000n : 0n },
      listingRuleHash: hashCanonical(`rule-${index}`), feeScheduleHash: hashCanonical(`fee-${index}`),
      bookGenerationHash: hashCanonical(`generation-${index}`), bookStateHash: hashCanonical(`book-${index}`),
    })),
  };
}
function context(value: ArbitrageCandidate): VerificationContext {
  return {
    nowEpochMs: 1000n, claimGraphHash: value.claimGraphHash, resolutionPartitionHash: value.resolutionPartitionHash,
    listingRuleHashById: new Map(value.legs.map((leg) => [leg.listingId, leg.listingRuleHash])),
    feeScheduleHashByListingId: new Map(value.legs.map((leg) => [leg.listingId, leg.feeScheduleHash])),
    bookGenerationHashByListingId: new Map(value.legs.map((leg) => [leg.listingId, leg.bookGenerationHash])),
    bookStateHashByListingId: new Map(value.legs.map((leg) => [leg.listingId, leg.bookStateHash])),
  };
}

describe("conservative BUY order budget", () => {
  it("does not confuse VWAP with an executable limit", () => {
    const budget = buildConservativeBuyBudget(source());
    assert.equal(budget.averageUnitPrice, 500n);
    assert.equal(budget.worstFillPrice, 600n);
    assert.equal(budget.limitPrice, 600n);
    assert.equal(budget.maximumNotional, 60_000n);
    assert.equal(budget.expectedGrossCollateral, 50_000n);
    assert.ok(Object.isFrozen(budget));
  });
  it("rejects the old VWAP order in fill replay", () => {
    assert.throws(() => assertBuyOrderReplay({ ...replay(), limitPrice: 500n }), /submitted buy limit/);
    assert.doesNotThrow(() => assertBuyOrderReplay(replay()));
  });
  it("recomputes profitability with the unchanged first-party verifier", () => {
    const optimistic = candidate(500n);
    assert.equal(verifyArbitrageCandidate(optimistic, context(optimistic)).worstCaseAfterFees, 5000n);
    const safe = candidate(buildConservativeBuyBudget(source()).limitPrice);
    assert.throws(() => verifyArbitrageCandidate(safe, context(safe)), /strictly positive/);
  });
  it("retains opportunities that remain positive at the conservative limit", () => {
    const safe = candidate(600n);
    const modified = { ...safe, legs: safe.legs.map((leg, i) => i === 1 ? { ...leg, unitPrice: 300n } : leg) };
    assert.equal(verifyArbitrageCandidate(modified, context(modified)).worstCaseAfterFees, 10_000n);
  });
  it("charges the aggregate fee against the maximum notional", () => {
    const budget = buildConservativeBuyBudget({ ...source(), netCollateral: 51_003n, fee: { flat: 3n, rate: 20n, rateScale: 1000n } });
    assert.equal(budget.maximumFee, 1203n);
    assert.equal(budget.maximumDebit, 61_203n);
  });
  it("rounds a worst fill UP to the requested tick", () => {
    const value = source();
    value.fills[1] = { levelIdentity: "high", quantity: 50_000n, price: 601n, collateral: 30_050n };
    value.grossCollateral = value.netCollateral = 50_050n;
    assert.equal(buildConservativeBuyBudget(value).limitPrice, 610n);
  });
  it("does not assume input fill ordering", () => {
    const value = source(); value.fills.reverse();
    assert.equal(buildConservativeBuyBudget(value).limitPrice, 600n);
  });
  it("handles values larger than Number.MAX_SAFE_INTEGER exactly", () => {
    const q = 10n ** 26n;
    const value = { ...source(), quantity: q, grossCollateral: q * 3n / 5n, netCollateral: q * 3n / 5n,
      fills: [{ levelIdentity: "huge", quantity: q, price: 600n, collateral: q * 3n / 5n }] };
    assert.equal(buildConservativeBuyBudget(value).maximumDebit, q * 3n / 5n);
  });
  it("keeps quantity and collateral scales distinct", () => {
    const value = { ...source(), quantity: 10_000n, quantityScale: 100n,
      fills: [{ levelIdentity: "one", quantity: 10_000n, price: 500n, collateral: 50_000n }] };
    assert.equal(buildConservativeBuyBudget(value).maximumDebit, 50_000n);
  });
  it("fails closed when per-level rounding exceeds the one-order notional bound", () => {
    const value = { ...source(), quantity: 2n, grossCollateral: 2n, netCollateral: 2n, priceTick: 1n,
      fills: ["a", "b"].map((levelIdentity) => ({ levelIdentity, quantity: 1n, price: 1n, collateral: 1n })) };
    assert.throws(() => buildConservativeBuyBudget(value), /per-level rounding/);
  });

  const invalid: ReadonlyArray<readonly [string, (value: ReturnType<typeof source>) => unknown]> = [
    ["zero quantity", (v) => ({ ...v, quantity: 0n })],
    ["negative quantity scale", (v) => ({ ...v, quantityScale: -1n })],
    ["zero collateral scale", (v) => ({ ...v, collateralScale: 0n })],
    ["zero price tick", (v) => ({ ...v, priceTick: 0n })],
    ["tick above one", (v) => ({ ...v, priceTick: 1001n })],
    ["rounded limit above one", (v) => ({ ...v, priceTick: 700n, fills: [{ levelIdentity: "a", quantity: v.quantity, price: 999n, collateral: 99_900n }], grossCollateral: 99_900n, netCollateral: 99_900n })],
    ["empty fills", (v) => ({ ...v, fills: [] })],
    ["too many fills", (v) => ({ ...v, fills: Array(10_001).fill(v.fills[0]) })],
    ["duplicate fill identity", (v) => ({ ...v, fills: [v.fills[0], { ...v.fills[1], levelIdentity: "low" }] })],
    ["negative price", (v) => ({ ...v, fills: [{ ...v.fills[0], price: -1n }] })],
    ["binary price above one", (v) => ({ ...v, fills: [{ ...v.fills[0], price: 1001n }] })],
    ["zero fill quantity", (v) => ({ ...v, fills: [{ ...v.fills[0], quantity: 0n }] })],
    ["wrong fill collateral", (v) => ({ ...v, fills: [{ ...v.fills[0], collateral: 1n }, v.fills[1]] })],
    ["wrong total gross", (v) => ({ ...v, grossCollateral: 49_999n })],
    ["wrong total quantity", (v) => ({ ...v, quantity: 99_999n })],
    ["wrong net debit", (v) => ({ ...v, netCollateral: 49_999n })],
    ["negative flat fee", (v) => ({ ...v, fee: { ...fee, flat: -1n } })],
    ["fee at 100 percent", (v) => ({ ...v, fee: { ...fee, rate: 1000n } })],
    ["zero fee scale", (v) => ({ ...v, fee: { ...fee, rateScale: 0n } })],
    ["unqualified curve fee", (v) => ({ ...v, fee: { ...fee, model: "BINARY_PRICE_CURVE_V1" } })],
    ["JS number quantity", (v) => ({ ...v, quantity: 100_000 })],
  ];
  for (const [name, mutate] of invalid) {
    it(`rejects ${name}`, () => {
      assert.throws(() => buildConservativeBuyBudget(mutate(source()) as Parameters<typeof buildConservativeBuyBudget>[0]));
    });
  }
  it("rejects a changed quantity scale during replay", () => {
    assert.throws(() => assertBuyOrderReplay({ ...replay(), reportQuantityScale: 100n }), /scale changed/);
  });
  it("rejects replay beyond the budget without clipping the debit", () => {
    assert.throws(() => assertBuyOrderReplay({ ...replay(), maximumDebit: 49_999n }), /exceeds its budget/);
  });
  it("does not admit SELL through a BUY budget", () => {
    assert.throws(() => assertBuyOrderReplay({ ...replay(), action: "SELL" }), /SELL/);
  });
  it("rejects a negative implied fee in replay", () => {
    assert.throws(() => assertBuyOrderReplay({ ...replay(), netCollateral: 49_999n }), /inconsistent/);
  });
  it("does not weaken empty state, stale hash or missing payout rejection", () => {
    const safe = candidate(400n);
    assert.throws(() => verifyArbitrageCandidate({ ...safe, resolutionStateIds: [] }, context(safe)), /empty/);
    assert.throws(() => verifyArbitrageCandidate(safe, { ...context(safe), claimGraphHash: hashCanonical("stale") }), /identity changed/);
    const broken = { ...safe, legs: [{ ...safe.legs[0]!, payoutPerUnitByResolution: { yes: 1000n } }, safe.legs[1]!] };
    assert.throws(() => verifyArbitrageCandidate(broken, context(broken)), /exact resolution partition/);
  });
  it("preserves limit coverage and nondecreasing cost over 1000 deterministic ladders", () => {
    for (let sample = 1; sample <= 1000; sample += 1) {
      const count = 1 + sample % 7;
      const fills = Array.from({ length: count }, (_, i) => {
        const price = BigInt(1 + (sample * 31 + i * 67) % 990);
        const quantity = BigInt(1 + (sample + i) % 73) * 1000n;
        return { levelIdentity: `${sample}:${i}`, price, quantity, collateral: quantity * price / 1000n };
      });
      const quantity = fills.reduce((sum, f) => sum + f.quantity, 0n);
      const grossCollateral = fills.reduce((sum, f) => sum + f.collateral, 0n);
      const feeValue = { flat: 2n, rate: 17n, rateScale: 1000n };
      const value = { ...source(), fills, quantity, grossCollateral, fee: feeValue,
        netCollateral: grossCollateral + 2n + divideCeil(grossCollateral * 17n, 1000n) };
      const budget = buildConservativeBuyBudget(value);
      assert.ok(fills.every((fill) => fill.price <= budget.limitPrice));
      assert.ok(budget.maximumDebit >= value.netCollateral);
      assert.equal(budget.limitPrice % value.priceTick, 0n);
      const moreFees = { ...value, fee: { ...feeValue, flat: 3n }, netCollateral: value.netCollateral + 1n };
      assert.equal(buildConservativeBuyBudget(moreFees).maximumDebit, budget.maximumDebit + 1n);
    }
  });
});
