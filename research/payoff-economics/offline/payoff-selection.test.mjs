import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyArbitrageCandidate } from '../.offline-build/dist/verifier.js';
import { hashCanonical } from '../.offline-build/dist/identity.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'source-edits.json'), 'utf8'));
const edits = manifest.edits.find((edit) => edit.path.endsWith('/relation-payoff.ts')).replacements;
// Execute the exact retained production selector and its proposed replacement.
// This isolates selection and the obsolete minimality guard; it is NOT the
// full semantic-admission/compileResearchRelationPayoff integration suite.
const oldSelect = new Function('guaranteed', edits[0].old + '\nreturn portfolios;');
const newSelect = new Function('guaranteed', edits[0].new + '\nreturn portfolios;');
const oldGuard = new Function('artifact', edits[1].old);
const newGuard = new Function('artifact', edits[1].new);
function combinations(n, states) {
  const out = [];
  for (let encoded=1; encoded<3**n; encoded++) {
    let code=encoded; const legs=[];
    for(let i=0;i<n;i++) { const digit=code%3; code=Math.floor(code/3); if(digit)legs.push({listingRef:`x${i}`,outcome:digit===1?'TRUE':'FALSE',index:i}); }
    const payouts=states.map((state)=>legs.reduce((sum,leg)=>sum+Number(state[leg.index]===(leg.outcome==='TRUE')),0));
    const floor=Math.min(...payouts);
    if(floor>=1)out.push({portfolioId:`p${String(encoded).padStart(3,'0')}`,legs,payouts,minimumPayoutUnits:String(floor)});
  }
  return out;
}
const triple = combinations(3, [[true,false,false],[false,true,false],[false,false,true]]);
const allNo = (p) => p.legs.length===3 && p.legs.every((l)=>l.outcome==='FALSE');
function certify(portfolio) {
 const stateIds=portfolio.payouts.map((_,i)=>`s${i}`);
 const candidate={classification:'VENUE_BOUNDED_ARBITRAGE',claimGraphHash:hashCanonical('triple'),resolutionPartitionHash:hashCanonical(stateIds),resolutionStateIds:stateIds,venueAssumptions:['SYNTHETIC_EXACTLY_ONE'],expiresAtEpochMs:2000n,
  legs:portfolio.legs.map((leg,index)=>({id:`l${index}`,venueId:'test',listingId:leg.listingRef,action:'BUY',quantity:1000n,maxQuantity:1000n,quantityScale:1000n,quantityTick:1n,unitPrice:600n,priceTick:1n,fee:{flat:0n,rate:0n,rateScale:1000n},payoutPerUnitByResolution:Object.fromEntries(stateIds.map((s,i)=>[s, i===leg.index?0n:1000n])),listingRuleHash:hashCanonical('rule'+index),feeScheduleHash:hashCanonical('fee'),bookGenerationHash:hashCanonical('gen'),bookStateHash:hashCanonical('book')}))};
 const context={nowEpochMs:1000n,claimGraphHash:candidate.claimGraphHash,resolutionPartitionHash:candidate.resolutionPartitionHash,
 listingRuleHashById:new Map(candidate.legs.map(l=>[l.listingId,l.listingRuleHash])),feeScheduleHashByListingId:new Map(candidate.legs.map(l=>[l.listingId,l.feeScheduleHash])),bookGenerationHashByListingId:new Map(candidate.legs.map(l=>[l.listingId,l.bookGenerationHash])),bookStateHashByListingId:new Map(candidate.legs.map(l=>[l.listingId,l.bookStateHash]))};
 return verifyArbitrageCandidate(candidate,context);
}
describe('exact production selection-block regression (not full pipeline)',()=>{
 it('reproduces old pruning and restores the profitable 3-NO basket',()=>{
  assert.equal(oldSelect(triple).some(allNo),false);
  const restored=newSelect(triple).find(allNo);
  assert.ok(restored); assert.equal(restored.minimumPayoutUnits,'2');
  assert.equal(certify(restored).worstCaseAfterFees,200n);
 });
 it('removes the second minimality veto without modifying the exact payoff verifier',()=>{
  const portfolios=newSelect(triple);
  assert.throws(()=>oldGuard({portfolios}),/dominated/);
  assert.doesNotThrow(()=>newGuard({portfolios}));
 });
 it('preserves every positive-floor basket for all nonempty 2/3-listing partitions and 1024 four-listing partitions',()=>{
  let families=0;
  for(const n of [2,3,4]){
   const universe=Array.from({length:2**n},(_,s)=>Array.from({length:n},(_,i)=>Boolean(s&(1<<i))));
   const masks=n<4?Array.from({length:2**(2**n)-1},(_,i)=>i+1):Array.from({length:1024},(_,i)=>1+((i*7919)%65535));
   for(const mask of masks){
    const states=universe.filter((_,i)=>mask&(1<<i));
    const baskets=combinations(n,states);
    const selected=newSelect(baskets);
    assert.equal(selected.length,baskets.length);
    assert.deepEqual(new Set(selected.map(x=>x.portfolioId)),new Set(baskets.map(x=>x.portfolioId)));
    assert.ok(selected.every(x=>BigInt(x.minimumPayoutUnits)>0n));
    families++;
   }
  }
  assert.equal(families,1294);
 });
 it('does not create positive edge from 200 coherent synthetic probability models',()=>{
  let checked=0;
  for(let seed=1;seed<=200;seed++){
   const n=2+seed%3;
   const states=Array.from({length:n},(_,winner)=>Array.from({length:n},(_,i)=>i===winner));
   const weights=states.map((_,i)=>BigInt(1+(seed*31+i*13)%97));
   const denominator=weights.reduce((s,x)=>s+x,0n);
   const yes=Array.from({length:n},(_,i)=>weights.reduce((s,w,k)=>s+(states[k][i]?w:0n),0n));
   for(const basket of newSelect(combinations(n,states))){
    const cost=basket.legs.reduce((s,l)=>s+(l.outcome==='TRUE'?yes[l.index]:denominator-yes[l.index]),0n);
    assert.ok(BigInt(basket.minimumPayoutUnits)*denominator-cost<=0n); checked++;
   }
  }
  assert.ok(checked>200, 'coherent-price check must not be vacuous');
 });
 it('returns deterministic order without mutating the caller array',()=>{
  const scrambled=[...triple].reverse(); const before=[...scrambled];
  assert.deepEqual(newSelect(scrambled).map(p=>p.portfolioId),newSelect(triple).map(p=>p.portfolioId));
  assert.deepEqual(scrambled,before); assert.ok(Object.isFrozen(newSelect(scrambled)));
 });
 it('keeps the curve-fee certification barrier outside the patch',()=>{
  const promotion=manifest.edits.find(e=>e.path.endsWith('/exact-promotion.ts'));
  assert.ok(promotion.replacements.every(r=>!r.old.includes('request.fee.model === "BINARY_PRICE_CURVE_V1"')));
 });
});
