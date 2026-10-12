import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {compileFactor} from './export.ts';
const review=JSON.parse(readFileSync(new URL('./reviewed-factor.json',import.meta.url),'utf8'));
// Explicitly reconstructed SOURCE-FIELD TEST objects, not original network bytes.
function fixture(){return review.scope.map((s:any)=>({...s,active:true,closed:false,archived:false,
 markets:s.members.map((m:any)=>({...m,description:s.description,active:true,closed:false,archived:false,acceptingOrders:true,enableOrderBook:true}))}));}
test('full reviewed definitions compile conditionally and preserve Other',()=>{
 const r=compileFactor(fixture());assert.equal(r.states.length,9);assert.equal(r.members.length,4);
 assert.equal(r.certificateAuthority,false);assert.equal(r.executionAuthority,false);
 assert.ok(r.states.some(s=>s.senate==='D'&&s.house==='OTHER'&&s.truth.join(',')==='true,false,false,false'));
});
for(const field of ['description','title','endDate','negRiskAugmented'])test('reject event mutation '+field,()=>{
 const raw=fixture();raw[0][field]=typeof raw[0][field]==='boolean'?!raw[0][field]:raw[0][field]+' changed';assert.throws(()=>compileFactor(raw));
});
for(const field of ['question','slug','conditionId','clobTokenIds','description','outcomes','version','groupItemTitle'])test('reject member mutation '+field,()=>{
 const raw=fixture();raw[0].markets[0][field]+=' changed';assert.throws(()=>compileFactor(raw));
});
test('reject lost source or duplicated event',()=>{const raw=fixture();assert.throws(()=>compileFactor(raw.slice(1)));raw[1]=raw[0];assert.throws(()=>compileFactor(raw));});
test('reject duplicate members',()=>{const raw=fixture();raw[0].markets.push(raw[0].markets[0]);assert.throws(()=>compileFactor(raw));});
test('reject trading unavailable while keeping source',()=>{const raw=fixture();raw[0].markets[0].acceptingOrders=false;assert.throws(()=>compileFactor(raw));});
test('wrong conjunct cannot be substituted',()=>{const raw=fixture();raw[2].markets[0].question=raw[2].markets[1].question;assert.throws(()=>compileFactor(raw));});
test('source price changes do not change binding',()=>{const raw=fixture();const old=compileFactor(raw);raw[0].markets[0].bestAsk='0.01';const fresh=compileFactor(raw);assert.equal(old.reviewScopeHash,fresh.reviewScopeHash);assert.deepEqual(old.states,fresh.states);});
