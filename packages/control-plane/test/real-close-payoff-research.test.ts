import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { describe,it,expect } from 'vitest';
import { parseBinanceCloseRule,closeRegionContains,checkNoonET } from '@pmh/venue-polymarket';
import { exportRealClosePayoffResearch } from '../src/real-close-payoff-research.js';
import { bindSettlementCondition } from '../src/settlement-condition.js';

const dir=resolve(import.meta.dirname,'../../../research/payoff-economics/s3/fixtures/real-binance');
const manifest=JSON.parse(readFileSync(resolve(dir,'manifest.json'),'utf8'));
const rawBodies=manifest.records.map((r:{file:string;record:{body_sha256:string}})=>{
  const b=readFileSync(resolve(dir,r.file)); expect(createHash('sha256').update(b).digest('hex')).toBe(r.record.body_sha256);
  return b.toString('utf8');
});
const events=rawBodies.map((b:string)=>JSON.parse(b)[0]);
const above=events.find((e:{slug:string})=>e.slug.includes('-above-'));
const ranges=events.find((e:{slug:string})=>e.slug.includes('-price-'));
const select=manifest.selection.map((s:{event_id:string;market_id:string})=>({eventId:s.event_id,marketId:s.market_id}));
function source() {
  const policy='SYNTHETIC_POLICY_WRAPPER_FOR_UNIT_TEST_ONLY';
  return {schemaVersion:'pmh.polymarket-binance-close-source.v1',
    definitions:manifest.records.map((v:{record:{url:string;body_sha256:string;received_ns:number}},i:number)=>({
      url:v.record.url,sha256:v.record.body_sha256,bodyUtf8:rawBodies[i],
      receivedAt:new Date(Math.floor(v.record.received_ns/1e6)).toISOString()})),
    selected:structuredClone(select),policies:[{url:'https://docs.polymarket.com/concepts/resolution.md',
      bodyUtf8:policy,sha256:createHash('sha256').update(policy).digest('hex'),receivedAt:'2026-10-12T05:12:50.000Z'}]};
}
function mutated(event:any,id:string,change:(m:any,e:any)=>void) {
  const e=structuredClone(event);change(e.markets.find((m:any)=>m.id===id),e);return e;
}

describe('real Binance full-rule conditional adapter',()=>{
  it('parses all four real unabridged selected descriptions but never certifies',()=>{
    for(const s of select) {
      const r=parseBinanceCloseRule(events.find((e:any)=>e.id===s.eventId),s.marketId);
      expect(r.interpretation).toBe('NORMAL_FINAL_CLOSE_ONLY');expect(r.paragraphs).toHaveLength(4);
      expect(r.certificateAuthority).toBe(false);expect(r.unknowns).toContain('MISSING_SOURCE_FALLBACK_NOT_SPECIFIED');
      expect(r.observation.unit).toBe('USDT_PER_BTC');expect(r.observation.closeAt).toBe('2026-10-12T16:00:00.000Z');
    }
  });
  it('does not silently upgrade the original generic exact grammar',()=>{
    expect(bindSettlementCondition(above.markets[0].description,{} as any).blocker).toBe('UNSUPPORTED_COMPLETE_RULE');
  });
  it.each([
    ['source',(m:any)=>{m.resolutionSource='https://www.binance.com/en/trade/BTC_USDC';}],
    ['pair',(m:any)=>{m.description=m.description.replaceAll('BTC/USDT','BTC/USDC');}],
    ['trailing exception',(m:any)=>{m.description+='\n\nIf the exchange fails, all markets resolve Yes.';}],
    ['missing precision',(m:any)=>{m.description=m.description.split('\n\n').slice(0,3).join('\n\n');}],
    ['weak comparison',(m:any)=>{m.description=m.description.replace('higher than','at least');}],
    ['changed title',(m:any)=>{m.question=m.question.replace('$82,000','$82,001');}],
    ['changed date',(m:any)=>{m.endDate='2027-10-12T16:00:00Z';}],
    ['wrong local time',(m:any)=>{m.endDate='2026-10-12T12:00:00Z';}],
    ['wrong label',(m:any)=>{m.groupItemTitle='84,000';}],
    ['native alias',(m:any)=>{m.clobTokenIds='["123","123"]';}],
    ['new protocol',(m:any)=>{m.version='v2';}],
    ['event override',(_:any,e:any)=>{e.description+=' A later clarification overrides this result.';}],
  ])('rejects %s',(_,change)=>{
    expect(()=>parseBinanceCloseRule(mutated(above,'5330077',change as any),'5330077')).toThrow();
  });
  it('requires real adjacent brackets with compatible full rules',()=>{
    const missing=structuredClone(ranges);
    missing.markets=missing.markets.filter((m:any)=>m.groupItemTitle!=='84,000-86,000');
    expect(()=>parseBinanceCloseRule(missing,'5330053')).toThrow(/adjacent/);
    const different=structuredClone(ranges);
    different.markets.find((m:any)=>m.groupItemTitle==='84,000-86,000').description+=' Extra fallback.';
    expect(()=>parseBinanceCloseRule(different,'5330053')).toThrow(/adjacent/);
  });
  it('rejects an adjacent label not supported by its complete question',()=>{
    const e=structuredClone(ranges);
    e.markets.find((m:any)=>m.groupItemTitle==='84,000-86,000').question=
      'Will the price of Bitcoin be between $85,000 and $86,000 on October 12?';
    expect(()=>parseBinanceCloseRule(e,'5330053')).toThrow(/adjacent/);
  });
  it('does not infer an inclusive terminal from a greater-than title',()=>{
    expect(()=>parseBinanceCloseRule(ranges,'5330063')).toThrow(/adjacent/);
  });
  it('price-only refresh preserves semantic identity; full rule changes do not pass',()=>{
    const a=parseBinanceCloseRule(above,'5330077');
    const b=parseBinanceCloseRule(mutated(above,'5330077',m=>{m.bestAsk=0.91;m.volume='999';}),'5330077');
    expect(a.ruleIdentity).toBe(b.ruleIdentity);
  });
  it('uses named zone DST instead of a fixed offset',()=>{
    expect(checkNoonET('2026-01-12T17:00:00Z','2026-01-12')).toBe('2026-01-12T17:00:00.000Z');
    expect(()=>checkNoonET('2026-01-12T16:00:00Z','2026-01-12')).toThrow();
    expect(()=>checkNoonET('2026-10-12T17:00:00Z','2026-10-12')).toThrow();
  });
  it('keeps equality states where naive threshold-minus-range identity fails',()=>{
    const a=parseBinanceCloseRule(above,'5330077'), b=parseBinanceCloseRule(above,'5330080');
    const r=parseBinanceCloseRule(ranges,'5330053');
    const pays=(x:bigint)=>[a,b,r].map(c=>Number(closeRegionContains(c.region,x)));
    expect(pays(82000n)).toEqual([0,0,1]); expect(pays(84000n)).toEqual([1,0,0]);
    expect(pays(83000n)).toEqual([1,0,1]);
  });
  it('matches independent decimal interval evaluation without sampling away endpoints',()=>{
    const r=parseBinanceCloseRule(ranges,'5330053');
    for(let x=8199000;x<=8401000;x+=37) expect(closeRegionContains(r.region,BigInt(x),100n))
      .toBe(x>=8200000 && x<8400000);
  });
  it('exports real source-bound matrix with all 81 independent half outcomes',()=>{
    const out=exportRealClosePayoffResearch(source());
    expect(out.assets).toHaveLength(8);expect(out.states).toHaveLength(7);expect(out.stressStates).toHaveLength(81);
    expect(out.certificateAuthority).toBe(false);expect(out.executionAuthority).toBe(false);
    expect(new Set(out.sources.map(s=>s.eventId)).size).toBe(2);
    for(const s of out.stressStates) for(let i=0;i<4;i++)
      expect(Number(out.assets[2*i]!.stressPayoffs[s])+Number(out.assets[2*i+1]!.stressPayoffs[s])).toBe(1);
  });
  it('rejects changed raw bytes even if the caller supplies old matrix labels',()=>{
    const s=source();s.definitions[0].bodyUtf8+=' ';expect(()=>exportRealClosePayoffResearch(s)).toThrow(/checksum/);
  });
  it('rejects duplicate selected contracts',()=>{
    const s=source();s.selected[1]=s.selected[0];expect(()=>exportRealClosePayoffResearch(s)).toThrow(/duplicate/);
  });
  it('rejects an unbound official-looking source URL',()=>{
    const s=source();s.definitions[0].url='https://gamma-api.polymarket.com/events?slug=other';
    expect(()=>exportRealClosePayoffResearch(s)).toThrow();
  });
  it('rejects missing general resolution policy',()=>{
    const s=source();s.policies=[];expect(()=>exportRealClosePayoffResearch(s)).toThrow();
  });
  it('rejects coherent but different observation years across otherwise valid events',()=>{
    const s=source(); const e=JSON.parse(s.definitions[0].bodyUtf8)[0];
    e.slug=e.slug.replace('2026','2027');e.endDate='2027-10-12T16:00:00Z';
    for(const m of e.markets){m.slug=m.slug.replace('2026','2027');m.endDate=e.endDate;}
    const body=JSON.stringify([e]);s.definitions[0].bodyUtf8=body;s.definitions[0].sha256=createHash('sha256').update(body).digest('hex');
    s.definitions[0].url=s.definitions[0].url.replace('2026','2027');
    expect(()=>exportRealClosePayoffResearch(s)).toThrow(/different/);
  });
});
