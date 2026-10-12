/** A versioned adapter for two COMPLETE real descriptions, not an exact oracle.
 * Only the stated normal final-close branch is interpreted. Missing-source,
 * revisions, clarifications and oracle independence remain explicit unknowns.
 */
import { z } from "zod";
import { hashCanonical } from "@pmh/domain";

export const BINANCE_CLOSE_RULE = "pmh.polymarket-binance-close-normal.v2";
const SOURCE = "https://www.binance.com/en/trade/BTC_USDT";
const FIRST_ABOVE = 'This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT closing at 12:00 in the ET timezone (noon) on the date specified in the title has a final "Close" price higher than the price specified in the title. Otherwise, this market will resolve to "No".';
const FIRST_RANGE = 'This market will resolve according to the final "Close" price of the Binance 1 minute candle for BTC/USDT closing at 12:00 in the ET timezone (noon) on the date specified in the title. Otherwise, this market will resolve to "No".';
const SOURCE_CLAUSE = 'The resolution source for this market is Binance, specifically the BTC/USDT "Close" prices currently available at https://www.binance.com/en/trade/BTC_USDT with "1m" and "Candles" selected on the top bar.';
const PAIR_CLAUSE = 'Please note that this market is about the price according to Binance BTC/USDT, not according to other exchanges or trading pairs.';
const PRECISION = 'Price precision is determined by the number of decimal places in the source.';
const BOUNDARY = 'If the reported value falls exactly between two brackets, then this market will resolve to the higher range bracket.';
const ABOVE = [FIRST_ABOVE, SOURCE_CLAUSE, PAIR_CLAUSE, PRECISION];
const RANGE = [FIRST_RANGE, SOURCE_CLAUSE, BOUNDARY, PAIR_CLAUSE];
const money = '(?:0|[1-9]\\d{0,2}(?:,\\d{3})*)(?:\\.\\d{1,8})?';
const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const normalize = (s: string) => s.replace(/\r\n/gu, "\n").trim();
const uint = z.string().regex(/^\d{1,100}$/u);
const marketSchema = z.object({
  id: uint, question: z.string(), description: z.string().min(1).max(20000),
  slug: z.string(), conditionId: z.string().regex(/^0x[0-9a-fA-F]{64}$/u),
  resolutionSource: z.literal(SOURCE), endDate: z.string(), outcomes: z.string(),
  clobTokenIds: z.string(), groupItemTitle: z.string(), version: z.literal('v1'),
  active: z.literal(true), closed: z.literal(false), archived: z.literal(false),
  acceptingOrders: z.literal(true), enableOrderBook: z.literal(true),
  negRisk: z.boolean(), negRiskOther: z.literal(false),
}).passthrough();
const eventSchema = z.object({
  id: uint, slug: z.string(), title: z.string(), description: z.string(), endDate: z.string(),
  active: z.literal(true), closed: z.literal(false), archived: z.literal(false),
  version: z.literal('v1'), negRisk: z.boolean(), negRiskAugmented: z.literal(false),
  markets: z.array(z.unknown()).min(1).max(200),
}).passthrough();

export type CloseRegion = Readonly<{ lower: string | null; lowerInclusive: boolean;
  upper: string | null; upperInclusive: false }>;
export type BinanceCloseRule = Readonly<{
  parserIdentity: typeof BINANCE_CLOSE_RULE; eventId: string; marketId: string;
  conditionId: string; yesToken: string; noToken: string; kind: 'ABOVE' | 'RANGE';
  observation: Readonly<{ subject: 'BTC'; metric: 'BINANCE_1M_FINAL_CLOSE';
    unit: 'USDT_PER_BTC'; source: typeof SOURCE; date: string; closeAt: string;
    timezone: 'America/New_York'; localClose: '12:00' }>;
  region: CloseRegion; ruleIdentity: string;
  paragraphs: readonly Readonly<{ index: number; text: string; textHash: string }>[];
  interpretation: 'NORMAL_FINAL_CLOSE_ONLY'; unknowns: readonly string[];
  certificateAuthority: false; executionAuthority: false;
}>;
function decimal(s: string): string {
  const [a, b = ''] = s.replaceAll(',', '').split('.');
  const f = b.replace(/0+$/u, '');
  return BigInt(a!).toString() + (f ? '.' + f : '');
}
function rational(s: string): readonly [bigint,bigint] {
  const [a,b=''] = s.split('.'); return [BigInt(a!+b),10n**BigInt(b.length)];
}
function less(a: string, b: string): boolean {
  const [n,d]=rational(a),[nn,dd]=rational(b); return n*dd<nn*d;
}
/** Slug shorthand is redundant source identity, never an alternate price. */
function slugValueEquals(text: string, value: string): boolean {
  if (!/^\d+(?:\.\d{1,8})?k?$/u.test(text)) return false;
  const kilo=text.endsWith('k'), [n,d]=rational(kilo?text.slice(0,-1):text);
  const [vn,vd]=rational(value);
  return n*(kilo?1000n:1n)*vd===vn*d;
}
function checkPriceSlug(slug: string, kind: 'ABOVE'|'RANGE'|'LESS',
    lower: string, upper: string|null, suffix: string): void {
  const price='(\\d+(?:\\.\\d{1,8})?k?)';
  const prefix=kind==='ABOVE'?'bitcoin-above-':kind==='RANGE'?
    'will-the-price-of-bitcoin-be-between-':'will-the-price-of-bitcoin-be-less-than-';
  const match=new RegExp('^'+prefix+price+(kind==='RANGE'?'-'+price:'')+suffix+'$','u').exec(slug);
  if(!match || !slugValueEquals(match[1]!,lower) ||
      (kind==='RANGE' && (upper===null || !slugValueEquals(match[2]!,upper))))
    throw new Error('slug price disagrees with complete question and group label');
}
/** Validate supplied venue instant against named-zone noon, including DST. */
export function checkNoonET(value: string, day: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.000)?Z$/u.test(value) || Number.isNaN(Date.parse(value)))
    throw new Error('invalid observation instant');
  const instant = new Date(value);
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York',
    year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23' })
    .formatToParts(instant);
  const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
  if (`${p.year}-${p.month}-${p.day}`!==day || `${p.hour}:${p.minute}:${p.second}`!=='12:00:00')
    throw new Error('endDate does not bind stated noon ET');
  return instant.toISOString();
}

export function parseBinanceCloseRule(rawEvent: unknown, marketId: string): BinanceCloseRule {
  const event = eventSchema.parse(rawEvent);
  const ids=event.markets.map(m=>z.object({id:uint}).parse(m).id);
  if(new Set(ids).size!==ids.length) throw new Error('duplicate event member');
  const index=ids.indexOf(marketId); if(index<0) throw new Error('missing selected market');
  const m=marketSchema.parse(event.markets[index]);
  const slug=/^bitcoin-(above|price)-on-([a-z]+)-(\d{1,2})-(20\d{2})$/u.exec(event.slug);
  if(!slug) throw new Error('unsupported event/date');
  const month=months.findIndex(x=>x.toLowerCase()===slug[2])+1, date=Number(slug[3]);
  if(!month || date<1 || date>31) throw new Error('invalid date');
  const day=`${slug[4]}-${String(month).padStart(2,'0')}-${String(date).padStart(2,'0')}`;
  if(new Date(day+'T00:00:00Z').toISOString().slice(0,10)!==day) throw new Error('invalid calendar date');
  const kind=slug[1]==='above'?'ABOVE':'RANGE';
  const dayLabel=`${months[month-1]} ${date}`;
  if(event.title!==`Bitcoin ${kind==='ABOVE'?'above ___':'price'} on ${dayLabel}?` ||
      !m.slug.startsWith(kind==='ABOVE'?'bitcoin-above-':'will-the-price-of-bitcoin-be-between-') || !m.slug.endsWith(`-on-${slug[2]}-${date}-${slug[4]}`))
    throw new Error('title/slug observation disagreement');
  const closeAt=checkNoonET(m.endDate,day);
  if(checkNoonET(event.endDate,day)!==closeAt || event.negRisk !== (kind==='RANGE') || m.negRisk!==event.negRisk)
    throw new Error('event time/protocol disagreement');
  const paragraphs=(kind==='ABOVE'?ABOVE:RANGE);
  const description=normalize(m.description);
  if(description!==paragraphs.join('\n\n') || normalize(event.description)!==description)
    throw new Error('unsupported COMPLETE description or event rule disagreement');
  const pattern = kind==='ABOVE' ? new RegExp(`^Will the price of Bitcoin be above \\$(${money}) on ${dayLabel}\\?$`,'u') :
    new RegExp(`^Will the price of Bitcoin be between \\$(${money}) and \\$(${money}) on ${dayLabel}\\?$`,'u');
  const q=pattern.exec(m.question); if(!q) throw new Error('unsupported complete question');
  const lower=decimal(q[1]!),upper=kind==='RANGE'?decimal(q[2]!):null;
  if(upper!==null && !less(lower,upper)) throw new Error('empty/reversed range');
  if(m.groupItemTitle!==(upper===null?q[1]:`${q[1]}-${q[2]}`)) throw new Error('question/group label disagreement');
  const suffix=`-on-${slug[2]}-${date}-${slug[4]}`;
  checkPriceSlug(m.slug,kind,lower,upper,suffix);
  const labels=z.tuple([z.literal('Yes'),z.literal('No')]).parse(JSON.parse(m.outcomes));
  const tokens=z.tuple([uint,uint]).parse(JSON.parse(m.clobTokenIds));
  if(labels.length!==2 || tokens[0]===tokens[1]) throw new Error('invalid native outcomes');
  const observation={subject:'BTC',metric:'BINANCE_1M_FINAL_CLOSE',unit:'USDT_PER_BTC',source:SOURCE,
    date:day,closeAt,timezone:'America/New_York',localClose:'12:00'} as const;
  const region={lower,lowerInclusive:kind==='RANGE',upper,upperInclusive:false} as const;
  // The higher-bracket convention requires actual adjacent brackets. Retain
  // their complete rules in identity rather than assuming a complete partition.
  const boundarySupport: unknown[]=[];
  if(upper!==null) {
    for(const [point,side] of [[lower,'left'],[upper,'right']] as const) {
      const hits=event.markets.map(x=>marketSchema.parse(x)).filter(other=>{
        if(other.id===m.id) return false;
        const pair=/^(\d[\d,.]*)-(\d[\d,.]*)$/u.exec(other.groupItemTitle);
        if(pair) return decimal(pair[side==='left'?2:1]!)===point;
        const end=/^([<>])(\d[\d,.]*)$/u.exec(other.groupItemTitle);
        return end!==null && end[1]===(side==='left'?'<':'>') && decimal(end[2]!)===point;
      });
      if(hits.length!==1) throw new Error('missing or ambiguous adjacent bracket');
      const other=hits[0]!;
      if(normalize(other.description)!==description || checkNoonET(other.endDate,day)!==closeAt || !other.negRisk)
        throw new Error('adjacent bracket uses different settlement rules');
      const siblingRange=new RegExp(`^(${money})-(${money})$`,'u').exec(other.groupItemTitle);
      // Only explicitly supported complete neighboring questions can establish
      // a shared endpoint. A contradictory terminal '> K' title is not silently
      // interpreted as '>= K'; leave such terminal-boundary families unsupported.
      const siblingLower=new RegExp(`^<(${money})$`,'u').exec(other.groupItemTitle);
      const expectedQuestion=siblingRange
        ? `Will the price of Bitcoin be between $${siblingRange[1]} and $${siblingRange[2]} on ${dayLabel}?`
        : siblingLower ? `Will the price of Bitcoin be less than $${siblingLower[1]} on ${dayLabel}?` : null;
      if(expectedQuestion===null || other.question!==expectedQuestion ||
          (siblingRange && !less(decimal(siblingRange[1]!),decimal(siblingRange[2]!))))
        throw new Error('adjacent bracket question/label ambiguity');
      if(siblingRange) checkPriceSlug(other.slug,'RANGE',decimal(siblingRange[1]!),decimal(siblingRange[2]!),suffix);
      else checkPriceSlug(other.slug,'LESS',decimal(siblingLower![1]!),null,suffix);
      boundarySupport.push({slug:other.slug,id:other.id,conditionId:other.conditionId,question:other.question,
        groupItemTitle:other.groupItemTitle,description:other.description,endDate:other.endDate,
        source:other.resolutionSource});
    }
  }
  const identity={parserIdentity:BINANCE_CLOSE_RULE,eventId:event.id,marketId:m.id,
    conditionId:m.conditionId,yesToken:tokens[0],noToken:tokens[1],observation,region,
    marketSlug:m.slug,eventSlug:event.slug,marketRules:m.description,eventRules:event.description,question:m.question,groupLabel:m.groupItemTitle,
    protocolVersion:m.version,negRisk:m.negRisk,boundarySupport};
  return Object.freeze({parserIdentity:BINANCE_CLOSE_RULE,eventId:event.id,marketId:m.id,
    conditionId:m.conditionId,yesToken:tokens[0],noToken:tokens[1],kind,observation,region,
    ruleIdentity:hashCanonical(identity),paragraphs:Object.freeze(paragraphs.map((text,index)=>
      Object.freeze({index,text,textHash:hashCanonical(text)}))),interpretation:'NORMAL_FINAL_CLOSE_ONLY',
    unknowns:Object.freeze(['MISSING_SOURCE_FALLBACK_NOT_SPECIFIED','FINAL_VALUE_REVISION_CUTOFF_NOT_SPECIFIED',
      'CANDLE_CLOSE_TIMESTAMP_CONVENTION_NOT_INDEPENDENTLY_VERIFIED','ORACLE_OR_CLARIFICATION_OVERRIDE',
      'INDEPENDENT_RESOLUTION_AND_COLLATERAL_TIMING_UNQUALIFIED']),certificateAuthority:false,executionAuthority:false});
}

export function closeRegionContains(region: CloseRegion,n: bigint,d: bigint=1n): boolean {
  if(d<=0n) throw new Error('invalid denominator');
  if(region.lower!==null) { const [ln,ld]=rational(region.lower),cmp=n*ld-ln*d;
    if(cmp<0n || (cmp===0n&&!region.lowerInclusive)) return false; }
  if(region.upper!==null) { const [un,ud]=rational(region.upper); if(n*ud>=un*d) return false; }
  return true;
}


export type CloseSourceRecord = Readonly<{url:string;bodyUtf8:string;sha256:string;receivedAt:string}>;
export type CloseSourceInput = Readonly<{
  schemaVersion:'pmh.polymarket-binance-close-source.v1';
  definitions:readonly CloseSourceRecord[]; policies:readonly CloseSourceRecord[];
  selected:readonly Readonly<{eventId:string;marketId:string}>[];
}>;
const rawSource=z.object({url:z.string(),bodyUtf8:z.string().min(1).max(3_000_000),
  sha256:z.string().regex(/^[0-9a-f]{64}$/u),receivedAt:z.string()}).strict();
export function parseBinanceCloseSource(raw:unknown):CloseSourceInput {
  return z.object({schemaVersion:z.literal('pmh.polymarket-binance-close-source.v1'),
    definitions:z.array(rawSource).min(1).max(4),policies:z.array(rawSource).min(1).max(2),
    selected:z.array(z.object({eventId:uint,marketId:uint}).strict()).min(2).max(4)}).strict().parse(raw);
}
export function parseBinanceEventPage(body:string):Readonly<{id:string;slug:string;[key:string]:unknown}> {
  return z.tuple([z.object({id:uint,slug:z.string()}).passthrough()]).parse(JSON.parse(body))[0];
}
