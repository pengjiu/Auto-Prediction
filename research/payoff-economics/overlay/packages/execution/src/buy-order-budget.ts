import { divideCeil } from "@pmh/domain";

/** One observed price-level fill; no inference about underlying match count. */
export type PlannedBuyFill = Readonly<{
  levelIdentity: string;
  price: bigint;
  quantity: bigint;
  collateral: bigint;
}>;

export type AggregateBuyFee = Readonly<{
  model?: "COLLATERAL_RATE_V1";
  flat: bigint;
  rate: bigint;
  rateScale: bigint;
}>;

export type BuyOrderBudget = Readonly<{
  expectedGrossCollateral: bigint;
  expectedNetCollateral: bigint;
  averageUnitPrice: bigint;
  worstFillPrice: bigint;
  limitPrice: bigint;
  maximumNotional: bigint;
  maximumFee: bigint;
  maximumDebit: bigint;
}>;

type BuyFillsInput = Readonly<{
  quantity: bigint;
  quantityScale: bigint;
  collateralScale: bigint;
  grossCollateral: bigint;
  fills: readonly PlannedBuyFill[];
}>;

function positive(value: bigint, label: string): void {
  if (typeof value !== "bigint" || value <= 0n) {
    throw new Error(`${label} must be a positive bigint`);
  }
}

function nonNegative(value: bigint, label: string): void {
  if (typeof value !== "bigint" || value < 0n) {
    throw new Error(`${label} must be a non-negative bigint`);
  }
}

/** Validate accounting, not contract meaning, available liquidity, or fillability. */
function reconcileBuyFills(input: BuyFillsInput): bigint {
  positive(input.quantity, "buy quantity");
  positive(input.quantityScale, "quantity scale");
  positive(input.collateralScale, "collateral scale");
  nonNegative(input.grossCollateral, "gross collateral");
  if (input.fills.length === 0 || input.fills.length > 10_000) {
    throw new Error("buy budget requires bounded, non-empty fills");
  }
  const identities = new Set<string>();
  let quantity = 0n;
  let collateral = 0n;
  let worstPrice = 0n;
  for (const fill of input.fills) {
    if (
      typeof fill.levelIdentity !== "string" || fill.levelIdentity.trim() === "" ||
      identities.has(fill.levelIdentity)
    ) throw new Error("buy fill level identity is missing or duplicated");
    identities.add(fill.levelIdentity);
    positive(fill.quantity, "fill quantity");
    nonNegative(fill.price, "fill price");
    nonNegative(fill.collateral, "fill collateral");
    if (fill.price > input.collateralScale) {
      throw new Error("binary fill price exceeds one collateral unit");
    }
    if (fill.collateral !== divideCeil(fill.quantity * fill.price, input.quantityScale)) {
      throw new Error("buy fill collateral does not reconcile");
    }
    quantity += fill.quantity;
    collateral += fill.collateral;
    if (fill.price > worstPrice) worstPrice = fill.price;
  }
  if (quantity !== input.quantity || collateral !== input.grossCollateral) {
    throw new Error("buy fill totals do not reconcile");
  }
  return worstPrice;
}

/**
 * Conditional BUY cost bound in the admitted aggregate collateral-fee model.
 * The limit covers every planned price; the verifier must use this limit's
 * cost, not VWAP. This does not prove execution, atomicity, or match-level fees.
 * In particular, price-curve fees must not be relabelled as aggregate fees.
 */
export function buildConservativeBuyBudget(input: BuyFillsInput & Readonly<{
  priceTick: bigint;
  netCollateral: bigint;
  fee: AggregateBuyFee;
}>): BuyOrderBudget {
  positive(input.priceTick, "price tick");
  nonNegative(input.netCollateral, "net collateral");
  if (input.fee.model !== undefined && input.fee.model !== "COLLATERAL_RATE_V1") {
    throw new Error("buy budget does not qualify this fee model");
  }
  nonNegative(input.fee.flat, "flat fee");
  nonNegative(input.fee.rate, "fee rate");
  positive(input.fee.rateScale, "fee rate scale");
  if (input.fee.rate >= input.fee.rateScale) {
    throw new Error("buy fee rate must be below its scale");
  }
  const worstFillPrice = reconcileBuyFills(input);
  if (input.priceTick > input.collateralScale) {
    throw new Error("price tick exceeds one collateral unit");
  }
  const limitPrice = divideCeil(worstFillPrice, input.priceTick) * input.priceTick;
  if (limitPrice > input.collateralScale) {
    throw new Error("rounded buy limit exceeds one collateral unit");
  }
  const expectedFee = input.fee.flat +
    divideCeil(input.grossCollateral * input.fee.rate, input.fee.rateScale);
  if (input.netCollateral !== input.grossCollateral + expectedFee) {
    throw new Error("buy report does not match the aggregate fee model");
  }
  const maximumNotional = divideCeil(input.quantity * limitPrice, input.quantityScale);
  // Aggregated levels may round separately. Do not hide a known excess inside
  // a one-order bound, and do not invent an unknown match-count reserve.
  if (input.grossCollateral > maximumNotional) {
    throw new Error("per-level rounding exceeds the single-order notional bound");
  }
  const maximumFee = input.fee.flat +
    divideCeil(maximumNotional * input.fee.rate, input.fee.rateScale);
  return Object.freeze({
    expectedGrossCollateral: input.grossCollateral,
    expectedNetCollateral: input.netCollateral,
    averageUnitPrice: divideCeil(input.grossCollateral * input.quantityScale, input.quantity),
    worstFillPrice,
    limitPrice,
    maximumNotional,
    maximumFee,
    maximumDebit: maximumNotional + maximumFee,
  });
}

/** A valid historical fill is not automatically a fill of the generated order. */
export function assertBuyOrderReplay(input: BuyFillsInput & Readonly<{
  action: "BUY" | "SELL";
  reportQuantityScale: bigint;
  limitPrice: bigint;
  maximumDebit: bigint;
  netCollateral: bigint;
}>): void {
  if (input.action !== "BUY") throw new Error("buy replay does not qualify SELL orders");
  if (input.reportQuantityScale !== input.quantityScale) {
    throw new Error("buy replay quantity scale changed");
  }
  nonNegative(input.limitPrice, "buy limit");
  positive(input.maximumDebit, "maximum debit");
  nonNegative(input.netCollateral, "net collateral");
  const worstFillPrice = reconcileBuyFills(input);
  if (input.limitPrice > input.collateralScale || worstFillPrice > input.limitPrice) {
    throw new Error("planned fill price exceeds the submitted buy limit");
  }
  if (input.netCollateral < input.grossCollateral || input.netCollateral > input.maximumDebit) {
    throw new Error("buy replay debit is inconsistent or exceeds its budget");
  }
}
