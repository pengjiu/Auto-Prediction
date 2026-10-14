import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {compileTemporal,instantNS} from './export.ts';
const seed=JSON.parse(readFileSync(new URL('./seed-source.json',import.meta.url),'utf8')).events;
for(const e of seed)test('complete historical scope '+e.id,()=>{const d=compileTemporal(e,e.id);assert.equal(d.members.length,3);assert.equal(d.executionAuthority,false);assert.ok(d.unknowns.includes('CREATED_AT_MATCHES_CONTRACT_MARKET_CREATION'));});
for(const [name,mutate] of [
 ['additional clause',(e:any)=>e.markets[0].description+='\n\nAn extra condition applies.'],
 ['wrong observation start',(e:any)=>e.markets[0].createdAt=e.markets[1].createdAt],
 ['wrong deadline',(e:any)=>e.markets[0].endDate=e.markets[1].endDate],
 ['wrong condition',(e:any)=>e.markets[0].conditionId='0x'+'1'.repeat(64)],
 ['wrong token',(e:any)=>e.markets[0].clobTokenIds='["1","2"]'],
 ['event level clause',(e:any)=>e.description+='\nOverride'],
 ['closed',(e:any)=>e.markets[0].closed=true],
 ['missing member',(e:any)=>e.markets.pop()],
 ['duplicate member',(e:any)=>e.markets.push(e.markets[0])],
 ['protocol changed',(e:any)=>e.version='v2'],
 ['inverse outcomes',(e:any)=>e.markets[0].outcomes='["No","Yes"]'],
] as const)test('reject '+name,()=>{const e=structuredClone(seed[0]);mutate(e);assert.throws(()=>compileTemporal(e,e.id));});
test('retain nanosecond identity',()=>assert.equal(instantNS('2026-08-07T14:23:13.456845Z')%1000000000n,456845000n));
test('invalid calendar',()=>assert.throws(()=>instantNS('2026-02-30T00:00:00Z')));
test('arbitrary source does not acquire authority',()=>assert.throws(()=>compileTemporal(seed[0],'267102')));
