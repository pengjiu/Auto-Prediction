/** Bounded rule-to-predicate binding, NOT general natural-language inference.
 * Whole-clause identity is opaque: it cannot prove cross-clause implications.
 * Numerical comparison requires every observation dimension, never title words.
 */
import type { WorldPredicateSemanticCore } from "./world-history-ontology.js";

export type NumericCondition = Readonly<{
  kind: "NUMBER"; subject: string; metric: string; comparison: "GT" | "GE" | "LT" | "LE" | "EQ";
  threshold: string; unit: string; source: string | null; startsAt: string | null; endsAt: string | null;
}>;
export type BoundCondition = Readonly<{
  atom: NumericCondition | Readonly<{ kind: "OPAQUE"; text: string }>;
  negated: boolean;
}>;
export type ConditionBinding = Readonly<{
  condition: BoundCondition | null; inverted: boolean;
  blocker: "UNSUPPORTED_COMPLETE_RULE" | "UNSUPPORTED_PREDICATE_STRUCTURE" | "CONDITION_MISMATCH" | null;
}>;

// No case-folding of subjects, units, or source URLs. Whitespace is insignificant
// outside quoted identifiers, whose bytes are deliberately preserved.
const compact = (s: string) => s.trim().split(/("[^"\n]*")/u)
  .map((part, i) => i % 2 ? part : part.replace(/[ \t\r\n]+/gu, " ")).join("");
const DECIMAL = /^-?\d{1,18}(?:\.\d{1,12})?$/u;
export function canonicalDecimal(s: string): string {
  if (!DECIMAL.test(s)) throw new Error("unsupported exact decimal");
  const negative = s.startsWith("-");
  const [whole, fraction = ""] = (negative ? s.slice(1) : s).split(".");
  const w = BigInt(whole!).toString(); const f = fraction.replace(/0+$/u, "");
  return (negative && (w !== "0" || f !== "") ? "-" : "") + w + (f ? `.${f}` : "");
}
export function decimalParts(s: string): readonly [bigint, bigint] {
  const c = canonicalDecimal(s), parts = c.split(".");
  return [BigInt(parts.join("")), 10n ** BigInt(parts[1]?.length ?? 0)];
}
export function compareDecimal(a: string, b: string): number {
  const [an, ad] = decimalParts(a), [bn, bd] = decimalParts(b);
  return an * bd < bn * ad ? -1 : an * bd > bn * ad ? 1 : 0;
}
export function evaluateNumeric(c: NumericCondition, n: bigint, d: bigint = 1n): boolean {
  if (d <= 0n) throw new Error("invalid rational denominator");
  const [v, scale] = decimalParts(c.threshold), left = n * scale, right = v * d;
  switch (c.comparison) {
    case "GT": return left > right; case "GE": return left >= right;
    case "LT": return left < right; case "LE": return left <= right;
    case "EQ": return left === right;
  }
}
export function observationKey(c: NumericCondition): string {
  return JSON.stringify([c.subject, c.metric, c.unit, c.source, c.startsAt, c.endsAt]);
}
const comparisons: Readonly<Record<string, NumericCondition["comparison"]>> = Object.freeze({
  "exceeds": "GT", "is greater than": "GT", "is at least": "GE", "is below": "LT",
  "is less than": "LT", "does not exceed": "LE", "is at most": "LE", "equals": "EQ",
});
const units: Readonly<Record<string, string>> = Object.freeze({
  "Celsius": "Celsius", "degrees Celsius": "Celsius", "°C": "Celsius",
  "Fahrenheit": "Fahrenheit", "degrees Fahrenheit": "Fahrenheit", "°F": "Fahrenheit",
  "USD": "USD", "percent": "percent", "%": "percent",
});
function exactTime(s: string): boolean {
  return !Number.isNaN(Date.parse(s)) && new Date(s).toISOString() === s;
}
function interval(semantic: WorldPredicateSemanticCore): boolean {
  const t = semantic.timeScope;
  return t.startsAt === null && t.endsAt === null ? t.precision === "UNRESOLVED" :
    t.precision === "EXACT_INTERVAL" && t.startsAt !== null && t.endsAt !== null &&
    exactTime(t.startsAt) && exactTime(t.endsAt) && t.startsAt <= t.endsAt;
}
function numeric(text: string, subject: string): NumericCondition | null {
  if (!text.startsWith(subject + " ")) return null;
  // Entire body is consumed. Extra conjuncts, time clauses, source/rounding
  // qualifiers etc cannot disappear into a word-overlap check.
  const m = /^([A-Za-z][A-Za-z0-9 -]{0,150}?) (exceeds|is greater than|is at least|is below|is less than|does not exceed|is at most|equals) (-?\d{1,18}(?:\.\d{1,12})?) (Celsius|degrees Celsius|°C|Fahrenheit|degrees Fahrenheit|°F|USD|percent|%)(?: as reported by "([^"\r\n]{1,300})")?(?: from (\S+) through (\S+))?$/u.exec(text.slice(subject.length + 1));
  if (!m) return null;
  const [, metric, comparison, threshold, unit, source, start, end] = m;
  if (start && (!exactTime(start) || !end || !exactTime(end) || start > end)) return null;
  return Object.freeze({ kind: "NUMBER", subject, metric: metric!, comparison: comparisons[comparison!]!,
    threshold: canonicalDecimal(threshold!), unit: units[unit!]!, source: source ?? null,
    startsAt: start ?? null, endsAt: end ?? null });
}
function unwrap(text: string): { text: string; negated: boolean } {
  let negated = false;
  for (let i = 0; i < 4 && text.startsWith("it is false that "); i++) {
    negated = !negated; text = text.slice("it is false that ".length);
  }
  return { text, negated };
}
function ruleCondition(rules: string): string | null {
  if (!rules || rules.length > 20_000 || /[\u0000-\u0008\u000e-\u001f]/u.test(rules)) return null;
  const text = compact(rules);
  const affirmative = '(?:(?:This|this) (?:market|contract) )?(?:Resolves|resolves|Settles|settles)(?: to)? ["\']?Yes["\']? if ';
  const negative = '(?:Otherwise|otherwise) (?:(?:it|this market|this contract) )?(?:resolves|settles)(?: to)? ["\']?No["\']?\\.';
  // Delimiters, not semantic words, accept case differences.
  const patterns = [new RegExp(`^${affirmative}(.+)\\. ${negative}$`, 'iu'),
    new RegExp(`^${affirmative}(.+) and to ["']?No["']? otherwise\\.$`, 'iu'),
    new RegExp(`^If (.+), then (?:this market|this contract) (?:resolves|settles)(?: to)? ["']?Yes["']?\\. ${negative}$`, 'iu')];
  for (const pattern of patterns) {
    const match = pattern.exec(text);
    if (match && !/\b(?:resolves?|settles?|otherwise)\b/iu.test(match[1]!)) return match[1]!;
  }
  return null;
}
function predicateCondition(s: WorldPredicateSemanticCore): BoundCondition | null {
  if (s.subjects.length !== 1 || !interval(s)) return null;
  const subject = compact(s.subjects[0]!.canonicalLabel);
  if (s.operatorKind === "THRESHOLD" && s.parameters.length > 0) {
    const p = new Map(s.parameters.map(v => [v.name, v]));
    if (p.size !== s.parameters.length || [...p.keys()].some(k => !["comparison", "threshold", "source"].includes(k))) return null;
    const comparison = p.get("comparison"), threshold = p.get("threshold"), source = p.get("source");
    if (!comparison || comparison.unit !== null || !["GT", "GE", "LT", "LE", "EQ"].includes(comparison.value) ||
        !threshold || threshold.unit === null || !(threshold.unit in units) ||
        !DECIMAL.test(threshold.value) || (source && source.unit !== null)) return null;
    return { atom: Object.freeze({ kind: "NUMBER", subject, metric: compact(s.verbPhrase),
      comparison: comparison.value as NumericCondition["comparison"], threshold: canonicalDecimal(threshold.value),
      unit: units[threshold.unit]!, source: source?.value ?? null,
      startsAt: s.timeScope.startsAt, endsAt: s.timeScope.endsAt }), negated: s.polarity === "NEGATED" };
  }
  // Unparsed parameter/time fields are never silently discarded.
  if (s.parameters.length > 0) return null;
  const u = unwrap(compact(`${subject} ${s.verbPhrase}`));
  const n = numeric(u.text, subject);
  if (s.operatorKind === "THRESHOLD" && n === null) return null;
  if (n !== null) {
    if (s.operatorKind !== "THRESHOLD" || n.startsAt !== s.timeScope.startsAt || n.endsAt !== s.timeScope.endsAt) return null;
    return { atom: n, negated: u.negated !== (s.polarity === "NEGATED") };
  }
  if (s.timeScope.startsAt !== null || s.timeScope.endsAt !== null) return null;
  return { atom: Object.freeze({ kind: "OPAQUE", text: u.text }), negated: u.negated !== (s.polarity === "NEGATED") };
}

export function bindSettlementCondition(rules: string, semantic: WorldPredicateSemanticCore): ConditionBinding {
  const text = ruleCondition(rules);
  if (text === null) return { condition: null, inverted: false, blocker: "UNSUPPORTED_COMPLETE_RULE" };
  const predicate = predicateCondition(semantic);
  if (predicate === null) return { condition: null, inverted: false, blocker: "UNSUPPORTED_PREDICATE_STRUCTURE" };
  const u = unwrap(text);
  const atom = predicate.atom.kind === "NUMBER" ? numeric(u.text, predicate.atom.subject) : { kind: "OPAQUE", text: u.text };
  if (atom === null || JSON.stringify(atom) !== JSON.stringify(predicate.atom)) {
    return { condition: null, inverted: false, blocker: "CONDITION_MISMATCH" };
  }
  return { condition: { atom: predicate.atom, negated: u.negated },
    inverted: predicate.negated !== u.negated, blocker: null };
}
