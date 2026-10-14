/** Source binding for ONE reviewed factored relation, never natural-language proof.
 * Keep complete definitions and exceptions. OTHER states and independent oracle
 * stress remain; augmented outcome sets are NOT converted or deemed exhaustive.
 */
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {instantNS} from '../s5/export.ts';
const review=JSON.parse(readFileSync(new URL('./reviewed-factor.json',import.meta.url),'utf8'));
const hash=(x:unknown)=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const ef=['id','title','description','endDate','resolutionSource','version','negRisk','negRiskAugmented'] as const;
const mf=['id','question','slug','createdAt','endDate','groupItemTitle','conditionId','outcomes','clobTokenIds','resolutionSource','version','negRisk','negRiskOther'] as const;
export function compileFactor(raw:unknown){
 if(!Array.isArray(raw)||raw.length!==3)throw Error('exact three original events required');
 if(new Set(raw.map(e=>e?.id)).size!==3)throw Error('duplicate source event');
 const members:any[]=[];
 for(const scope of review.scope){
  const e=raw.find(e=>e?.id===scope.id);if(!e)throw Error('missing fixed event');
  for(const k of ef)if((e[k]??null)!==scope[k])throw Error('event rule identity changed: '+k);
  if(e.version!=='v1'||e.active!==true||e.closed!==false||e.archived!==false||!Array.isArray(e.markets)||e.markets.length>100)throw Error('unsupported/inactive source event');
  if(new Set(e.markets.map((m:any)=>m?.id)).size!==e.markets.length)throw Error('duplicate native member');
  for(const expected of scope.members){
   const m=e.markets.find((m:any)=>m?.id===expected.id);if(!m)throw Error('missing fixed member');
   for(const k of mf)if((m[k]??null)!==expected[k])throw Error('member identity changed: '+k);
   if(m.description!==scope.description||m.active!==true||m.closed!==false||m.archived!==false||m.acceptingOrders!==true||m.enableOrderBook!==true)throw Error('unreviewed/inactive member');
   if(!/^0x[0-9a-fA-F]{64}$/u.test(m.conditionId)||m.version!=='v1'||JSON.stringify(JSON.parse(m.outcomes))!==JSON.stringify(['Yes','No']))throw Error('native binary schema');
   const tokens=JSON.parse(m.clobTokenIds);
   if(!Array.isArray(tokens)||tokens.length!==2||tokens.some((t:unknown)=>typeof t!=='string'||!/^\d{1,100}$/u.test(t)))throw Error('native tokens');
   const start=instantNS(m.createdAt),end=instantNS(m.endDate);if(start>=end)throw Error('interval identity');
   members.push({eventId:e.id,marketId:m.id,conditionId:m.conditionId,tokens,endNS:String(end),question:m.question,ruleHash:hash(m.description)});
  }
 }
 const tokens=members.flatMap(m=>m.tokens);if(new Set(tokens).size!==tokens.length)throw Error('duplicate token');
 if(members.map(m=>m.marketId).join(',')!=='562793,562802,562828,562829')throw Error('factor position identity');
 // Nine latent states, NOT four two-party states. Different latent states can
 // have identical traded truth vectors; retaining them documents the residual.
 const states=[];
 for(const senate of ['D','R','OTHER'])for(const house of ['D','R','OTHER']){
  states.push({senate,house,truth:[senate==='D',house==='D',senate==='D'&&house==='D',senate==='D'&&house==='R']});
 }
 return {schema:'s6.factor-source.v1',sourceHash:hash(raw),reviewScopeHash:hash(review),members,states,
   interpretation:'ASSUMED_COMMON_CHAMBER_CONTROL_DEFINITIONS_WITH_OTHER',
   unknowns:['INDEPENDENT_CONTRACT_ORACLES','ANCILLARY_AND_CLARIFICATION_COMPLETENESS','UNUSUAL_ELECTION_RULE_AMBIGUITY',
     'MATCH_LEVEL_FEE_DEBITS','SETTLEMENT_TIMING_AND_FINANCING','NONATOMIC_ENTRY'],
   certificateAuthority:false,executionAuthority:false,reviewProvenance:review.review};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const [input,output]=process.argv.slice(2);if(!input||!output)throw Error('usage: export.ts input output');
 writeFileSync(output,JSON.stringify(compileFactor(JSON.parse(readFileSync(input,'utf8'))),null,2)+'\n',{flag:'wx'});
}
