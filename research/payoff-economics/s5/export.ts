/** Source-bound temporal research only. This does NOT issue a semantic certificate.
 * The complete reviewed prose is an explicitly assumed event qualification.
 * Never accept a caller's own template, interval table, or review-success label.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
const scopes = JSON.parse(readFileSync(new URL('./reviewed-scopes.json', import.meta.url),'utf8')).scopes;
const norm=(x:unknown):string=>{if(typeof x!=='string')throw Error('text required');return x.replace(/\r\n/gu,'\n').trim();};
const hash=(x:unknown)=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
export function instantNS(x:unknown):bigint {
 if(typeof x!=='string')throw Error('ISO timestamp required');
 const m=/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$/u.exec(x);
 if(!m)throw Error('noncanonical timestamp');
 const t=Date.parse(m[1]+'Z');
 if(!Number.isSafeInteger(t)||new Date(t).toISOString()!==m[1]+'.000Z')throw Error('invalid calendar');
 return BigInt(t)*1000000n+BigInt((m[2]??'').padEnd(9,'0'));
}
function endDateMatchesLabel(end:string,label:string):void {
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(end));
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 if(`${p.hour}:${p.minute}:${p.second}`!=='23:59:00'||![`${p.month} ${p.day}`,`${p.month} ${p.day}, ${p.year}`].includes(label))throw Error('deadline label/ET mismatch');
}
export function compileTemporal(raw:unknown,eid:string) {
 const scope=scopes.find((x:any)=>x.eventId===eid);if(!scope)throw Error('unreviewed source family');
 if(!raw||typeof raw!=='object')throw Error('event required');const e=raw as any;
 if(String(e.id)!==eid||e.title!==scope.title||norm(e.description)!==scope.description||e.version!=='v1'||e.negRisk!==false||e.negRiskAugmented!==false)throw Error('event source/review scope mismatch');
 for(const k of ['active'])if(e[k]!==true)throw Error('event not active');
 for(const k of ['closed','archived'])if(e[k]!==false)throw Error('event unavailable');
 if(!Array.isArray(e.markets)||e.markets.length>250)throw Error('member list required');
 const ids=e.markets.map((m:any)=>String(m.id));if(new Set(ids).size!==ids.length)throw Error('duplicate member');
 const tokens=new Set<string>();
 const members=scope.members.map((expected:any)=>{
  const m=e.markets.find((m:any)=>String(m.id)===expected.id);if(!m)throw Error('missing fixed member');
  for(const k of ['id','question','slug','createdAt','endDate','groupItemTitle','conditionId','outcomes','clobTokenIds'])if(m[k]!==expected[k])throw Error('member identity changed: '+k);
  if(norm(m.description)!==scope.description||m.version!=='v1'||m.negRisk!==false||m.negRiskOther!==false||m.resolutionSource!=='')throw Error('unreviewed complete rules/protocol');
  for(const k of ['active','acceptingOrders','enableOrderBook'])if(m[k]!==true)throw Error('market unavailable');
  for(const k of ['closed','archived'])if(m[k]!==false)throw Error('market unavailable');
  if(!/^0x[0-9a-fA-F]{64}$/u.test(m.conditionId)||JSON.stringify(JSON.parse(m.outcomes))!==JSON.stringify(['Yes','No']))throw Error('unsupported native outcome');
  const tt=JSON.parse(m.clobTokenIds);if(!Array.isArray(tt)||tt.length!==2||tt.some(t=>typeof t!=='string'||!/^\d{1,100}$/u.test(t)||tokens.has(t))||tt[0]===tt[1])throw Error('duplicate/invalid native tokens');tt.forEach(t=>tokens.add(t));
  const start=instantNS(m.createdAt),end=instantNS(m.endDate);if(start>=end)throw Error('empty observation interval');endDateMatchesLabel(m.endDate,m.groupItemTitle);
  return {marketId:m.id,question:m.question,conditionId:m.conditionId,tokens:tt,startNS:String(start),endNS:String(end),endMinuteNS:String(end+59999999999n),fullRuleHash:hash(scope.description)};
 });
 return {schema:'s5.temporal-source.v1',eventId:eid,sourceHash:hash(raw),reviewScopeHash:hash(scope),members,
  qualificationPredicate:scope.description,interpretation:'ASSUMED_IDENTICAL_QUALIFYING_OCCURRENCE_IN_OWN_CREATION_WINDOW',
  unknowns:['CREATED_AT_MATCHES_CONTRACT_MARKET_CREATION','START_BOUNDARY_INCLUSION','FINAL_MINUTE_ENDPOINT','COMPLETE_ANCILLARY_AND_LATER_CLARIFICATIONS','CONSISTENT_INDEPENDENT_RESOLUTION','ACTUAL_FEE_DEBITS','DIFFERENT_SETTLEMENT_MATURITIES_AND_CAPITAL_COST'],
  certificateAuthority:false,executionAuthority:false};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const [input,eid,output]=process.argv.slice(2);if(!input||!eid||!output)throw Error('usage: export.ts input eventId output');
 writeFileSync(output,JSON.stringify(compileTemporal(JSON.parse(readFileSync(input,'utf8')),eid),null,2)+'\n',{flag:'wx'});
}
