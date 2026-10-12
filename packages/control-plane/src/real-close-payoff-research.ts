/** Full real rule-family input to the SAME research matrix format. This path
 * never grants production exact admission and never fabricates canonical prose.
 */
import { createHash } from 'node:crypto';
import { hashCanonical } from '@pmh/domain';
import { parseBinanceCloseRule, closeRegionContains, BINANCE_CLOSE_RULE, parseBinanceCloseSource, parseBinanceEventPage, type CloseSourceRecord } from '@pmh/venue-polymarket';
import { numericCells } from './numeric-payoff-research.js';
import type { NumericCondition } from './settlement-condition.js';

function checked(raw:CloseSourceRecord) {
  if(createHash('sha256').update(raw.bodyUtf8,'utf8').digest('hex')!==raw.sha256)
    throw new Error('raw body checksum mismatch');
  if(Number.isNaN(Date.parse(raw.receivedAt)) || new Date(raw.receivedAt).toISOString()!==raw.receivedAt)
    throw new Error('canonical source timestamp required');
  const url=new URL(raw.url);
  if(url.protocol!=='https:' || url.username || url.password || url.hash || url.port)
    throw new Error('invalid source URL');
  return url;
}

export function exportRealClosePayoffResearch(raw:unknown) {
  const input=parseBinanceCloseSource(raw);
  const events=new Map<string,{body:unknown;raw:CloseSourceRecord}>();
  for(const record of input.definitions) {
    const url=checked(record);
    if(url.origin!=='https://gamma-api.polymarket.com' || url.pathname!=='/events' ||
        [...url.searchParams.keys()].join(',')!=='slug') throw new Error('unbound Gamma source URL');
    const event=parseBinanceEventPage(record.bodyUtf8);
    if(event.slug!==url.searchParams.get('slug') || events.has(event.id)) throw new Error('duplicate/unbound event');
    events.set(event.id,{body:event,raw:record});
  }
  const policyPaths=new Set<string>();
  for(const record of input.policies) {
    const url=checked(record);
    if(url.origin!=='https://docs.polymarket.com' || url.search ||
        !['/concepts/resolution.md','/trading/fees.md'].includes(url.pathname) || policyPaths.has(url.pathname))
      throw new Error('unknown/duplicate policy source');
    policyPaths.add(url.pathname);
  }
  if(!policyPaths.has('/concepts/resolution.md')) throw new Error('missing resolution policy evidence');
  const selected=new Set<string>();
  const rows=input.selected.map(ref=>{
    const key=ref.eventId+':'+ref.marketId;
    if(selected.has(key)) throw new Error('duplicate selected listing'); selected.add(key);
    const event=events.get(ref.eventId); if(!event) throw new Error('selected event missing');
    const rule=parseBinanceCloseRule(event.body,ref.marketId);
    return {rule,raw:event.raw,ref:`polymarket:${rule.conditionId}`};
  });
  const first=rows[0]!.rule.observation;
  if(rows.some(r=>hashCanonical(r.rule.observation)!==hashCanonical(first)))
    throw new Error('different source/pair/time axes');
  const tokens=rows.flatMap(r=>[r.rule.yesToken,r.rule.noToken]);
  if(new Set(tokens).size!==tokens.length || new Set(rows.map(r=>r.ref)).size!==rows.length)
    throw new Error('duplicate native token or condition');
  const cuts=[...new Set(rows.flatMap(r=>[r.rule.region.lower,r.rule.region.upper]).filter((s):s is string=>s!==null))];
  const conditions:NumericCondition[]=cuts.map(threshold=>({kind:'NUMBER',subject:first.subject,
    metric:first.metric,unit:first.unit,source:first.source,startsAt:first.closeAt,endsAt:first.closeAt,
    threshold,comparison:'GE'}));
  const cells=numericCells(conditions), states=cells.map(c=>c.id);
  // Independent 0, 1/2, 1 outcomes per contract, not just one common 50/50 state.
  // Binary extremes already bound every complementary fractional payout in [0,1].
  const stressStates=Array.from({length:3**rows.length},(_,i)=>`independent_${i}`);
  const assets=rows.flatMap((r,i)=>[true,false].map(yes=>({id:yes?r.rule.yesToken:r.rule.noToken,
    venue:'polymarket-global',listingRef:r.ref,instrumentId:r.rule.conditionId,outcome:yes?'YES':'NO',
    payoffs:Object.fromEntries(cells.map(c=>[c.id,closeRegionContains(r.rule.region,BigInt(c.numerator),BigInt(c.denominator))===yes?'1':'0'])),
    stressPayoffs:Object.fromEntries(stressStates.map((s,k)=>{
      const v=Math.floor(k/(3**i))%3; return [s,(yes?['0','0.5','1']:['1','0.5','0'])[v]!];
    }))})));
  const sources=rows.map(r=>({listingRef:r.ref,listingHash:r.rule.ruleIdentity,
    sourceRawHash:'sha256:'+r.raw.sha256,sourceReceivedAt:r.raw.receivedAt,
    protocolIdentity:'polymarket-CTF-v1-CONDITIONAL-COMMON-COLLATERAL',
    eventId:r.rule.eventId,marketId:r.rule.marketId,ruleIdentity:r.rule.ruleIdentity,
    observation:r.rule.observation,region:r.rule.region,paragraphs:r.rule.paragraphs,unknowns:r.rule.unknowns}));
  const body={schemaVersion:'pmh.numeric-payoff-research.v1' as const,compilerIdentity:BINANCE_CLOSE_RULE,
    coverage:'ASSUMED_STATES_ONLY' as const,authority:'RESEARCH_EXPORT_ONLY' as const,
    assumption:'SHARED_OBSERVATION_AND_CONSISTENT_RESOLUTION' as const,
    interpretation:'FULL_DESCRIPTION_NORMAL_BRANCH_ONLY',certificateAuthority:false,executionAuthority:false,
    corpusIdentity:hashCanonical(input.definitions.map(r=>({url:r.url,hash:r.sha256}))),
    familyRuleIdentity:hashCanonical(rows.map(r=>r.rule.ruleIdentity).sort()),
    sources,states,cells,assets,stressStates,
    policySources:input.policies.map(p=>({url:p.url,hash:p.sha256,receivedAt:p.receivedAt})),
    policyPosture:'RETAINED_NOT_PROOF_OF_COMPLETE_VENUE_POLICY',
    stressAssumption:'INDEPENDENT_COMPLEMENTARY_OUTCOMES_WITH_MIXED_HALVES_NOT_TIMING_OR_REFUND_PROOF'};
  return Object.freeze({...body,exportId:hashCanonical(body)});
}
