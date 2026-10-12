import { readFileSync, writeFileSync } from "node:fs";
import { canonicalJson } from "../../../packages/domain/src/identity.js";
import { buildMarketCorpusSnapshot } from "../../../packages/control-plane/src/market-corpus.js";
import { buildMarketOntologySnapshot } from "../../../packages/control-plane/src/market-ontology.js";
import { assertNumericPayoffResearch, exportNumericPayoffResearch } from "../../../packages/control-plane/src/numeric-payoff-research.js";

import { exportRealClosePayoffResearch } from "../../../packages/control-plane/src/real-close-payoff-research.js";

const [source, destination] = process.argv.slice(2);
if (!source || !destination || process.argv.length !== 4) throw new Error("usage: export.ts source.json output.json");
const raw = JSON.parse(readFileSync(source, "utf8"));
let output;
if (raw.schemaVersion === "pmh.polymarket-binance-close-source.v1") {
  output = exportRealClosePayoffResearch(raw);
} else {
const corpus = buildMarketCorpusSnapshot(raw.corpus);
const input = { corpus, ontology: buildMarketOntologySnapshot(corpus), predicates: raw.predicates,
  listingRefs: raw.listingRefs, venuePolicyEvidence: raw.venuePolicyEvidence ?? [] };
output = exportNumericPayoffResearch(input);
assertNumericPayoffResearch(output, input);
}
// Exclusive creation: a rerun must never overwrite historical evidence.
writeFileSync(destination, canonicalJson(output) + "\n", { flag: "wx" });
