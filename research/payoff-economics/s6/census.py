"""Price-independent candidate routing, NOT a semantic or arbitrage verifier.

The input population may have been selected by liquidity. This census measures
coverage within that retained population, not market-wide recall or profitability.
Shared complete blocks retrieve reviews; neither score nor a hash certifies meaning.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
import zipfile

MAX_TOTAL = 256_000_000
MAX_PAGE = 12_000_000
MAX_EVENTS = 2_000
MAX_MARKETS = 100_000
STOP = set('the a an of in on to will by and or vs be is for at after which what who'.split())
SEMANTIC_FIELDS = ('id','question','description','groupItemTitle','createdAt','endDate',
                   'conditionId','clobTokenIds','outcomes','resolutionSource','version',
                   'negRisk','negRiskOther','active','closed','archived','acceptingOrders','enableOrderBook')
EVENT_FIELDS = ('id','title','description','endDate','resolutionSource','version',
                'negRisk','negRiskAugmented','active','closed','archived')

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode()).hexdigest()

def text(value):
    if not isinstance(value,str): raise ValueError('text required')
    return value

def blocks(raw):
    """Offsets address original Unicode text; whitespace normalization is retrieval only."""
    for match in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', text(raw)):
        clause = match.group(0).rstrip()
        if not clause: continue
        norm=' '.join(clause.split())
        if 120 <= len(norm) <= 6000:
            yield norm, {'start':match.start(),'end':match.start()+len(clause),
                         'raw_sha256':sha256(clause.encode()).hexdigest()}

def projection(event):
    if not isinstance(event,dict) or not isinstance(event.get('markets'),list):
        raise ValueError('invalid event')
    ids=[str(m.get('id')) for m in event['markets'] if isinstance(m,dict)]
    if len(ids)!=len(event['markets']) or len(ids)!=len(set(ids)) or any(not x.isdigit() for x in ids):
        raise ValueError('invalid/duplicate native member')
    e={k:event.get(k) for k in EVENT_FIELDS}; e['id']=str(e['id'])
    if not e['id'].isdigit(): raise ValueError('invalid event id')
    for k in ('title','description'): text(e[k])
    e['markets']=sorted(({k:m.get(k) for k in SEMANTIC_FIELDS} for m in event['markets']),key=lambda m:str(m['id']))
    return e

def load_catalog(archive, expected_sha256):
    """Read original ZIP in place, bounded; never extract or take quotes from catalog."""
    archive=Path(archive)
    if archive.stat().st_size>MAX_TOTAL or sha256(archive.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('original archive digest mismatch')
    variants=defaultdict(dict);provenance=defaultdict(list);failures=[];total=0;rows=0
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('duplicate ZIP entry')
        manifests=[n for n in names if n.endswith('/requests.jsonl')]
        if len(manifests)!=1:raise ValueError('one original request manifest required')
        manifest=manifests[0];prefix=manifest.rsplit('/',1)[0]
        if z.getinfo(manifest).file_size>5_000_000:raise ValueError('manifest limit')
        raw_manifest=z.read(manifest);records=[json.loads(x) for x in raw_manifest.splitlines()]
        catalog=[r for r in records if isinstance(r,dict) and str(r.get('label','')).startswith('catalog:')]
        if not 1<=len(catalog)<=200:raise ValueError('catalog page bound')
        if len({r['label'] for r in catalog})!=len(catalog):raise ValueError('duplicate catalog receipt')
        for r in catalog:
            u=urlparse(r.get('url',''));q=parse_qs(u.query)
            if (r.get('method')!='GET' or u.scheme!='https' or u.netloc!='gamma-api.polymarket.com'
                or u.path!='/events' or u.fragment or not q.get('limit') or not q.get('offset')
                or any(type(r.get(k))is not int for k in ('started_ns','received_ns','bytes'))
                or not 0<=r['started_ns']<=r['received_ns']):raise ValueError('catalog receipt identity')
            h=r.get('body_sha256','')
            if not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('unsafe raw identity')
            raw_name=f'{prefix}/raw/{h}.bin'
            if z.getinfo(raw_name).file_size>MAX_PAGE:raise ValueError('page limit')
            raw=z.read(raw_name);total+=len(raw)
            if total>MAX_TOTAL or len(raw)!=r['bytes'] or sha256(raw).hexdigest()!=h:raise ValueError('raw integrity/size')
            if 'error' not in r:raise ValueError('missing status disposition')
            if r['status']!=200 or r['error']is not None:
                failures.append({'label':r['label'],'status':r['status'],'error':r['error']});continue
            page=json.loads(raw,parse_float=str)
            if not isinstance(page,list):raise ValueError('catalog page shape')
            for original in page:
                e=projection(original);rows+=len(e['markets'])
                if rows>MAX_MARKETS:raise ValueError('market bound')
                eid=e['id'];key=digest(e);variants[eid][key]=e
                provenance[eid].append({'page':r['label'],'body_sha256':h,'received_ns':r['received_ns']})
            if len(variants)>MAX_EVENTS:raise ValueError('event bound')
    conflicts=sorted(eid for eid,versions in variants.items() if len(versions)>1)
    events=[next(iter(variants[eid].values())) for eid in sorted(variants) if eid not in conflicts]
    return events,{'archive_sha256':expected_sha256,'request_manifest_sha256':sha256(raw_manifest).hexdigest(),
        'catalog_pages':len(catalog),'unavailable_pages':failures,'distinct_event_ids':len(variants),
        'conflicting_event_ids':conflicts,'event_receipts':dict(provenance),
        'upstream_selection':'LIQUIDITY_RANKED_RETAINED_CATALOG_NOT_RANDOM',
        'available_then_ns':max((x['received_ns'] for xs in provenance.values() for x in xs),default=None)}

def census(events, top_k=32):
    if type(top_k)is not int or not 1<=top_k<=100:raise ValueError('review budget')
    if not events or len(events)>MAX_EVENTS:raise ValueError('event bound')
    events=[projection(e) for e in events];by_id={e['id']:e for e in events}
    if len(by_id)!=len(events):raise ValueError('duplicate event')
    postings=defaultdict(dict);texts=set();market_ids=set();title_tokens={};market_count=0;eligible=0
    for e in events:
        eid=e['id'];docs=[('event',e['description'])]
        for m in e['markets']:
            market_count+=1;market_ids.add(str(m['id']))
            if not isinstance(m.get('description'),str):continue
            texts.add(m['description'])
            if m.get('active')is True and m.get('closed')is False and m.get('archived')is False and m.get('acceptingOrders')is True and m.get('enableOrderBook')is True:
                eligible+=1;docs.append((str(m['id']),m['description']))
        title_tokens[eid]=set(re.findall(r'[a-z0-9]+',e['title'].lower()))-STOP
        for owner,body in sorted(set(docs)):
            for norm,span in blocks(body):
                key=sha256(norm.encode()).hexdigest()
                if eid not in postings[key]:
                    postings[key][eid]={'owner':owner,'text_hash':sha256(body.encode()).hexdigest(),**span,'normalized_text':norm}
    # Extremely frequent shared paragraphs are omitted from routing, never from original evidence.
    max_support=max(2,len(events)//8);scores=defaultdict(int);evidence=defaultdict(list);ignored=0
    for key,ids in postings.items():
        n=len(ids)
        if n<2:continue
        if n>max_support:ignored+=1;continue
        norm=next(iter(ids.values()))['normalized_text']
        weight=min(len(norm),2048)*max(1,len(events)//n)
        for pair in combinations(sorted(ids),2):
            scores[pair]+=weight
            evidence[pair].append({'block_sha256':key,'document_frequency':n,'text':norm,
                 'bindings':[{ 'event_id':eid, **{k:v for k,v in ids[eid].items() if k!='normalized_text'}} for eid in pair]})
    lexical={}
    title_index=defaultdict(set)
    for eid,tokens in title_tokens.items():
        for token in tokens:title_index[token].add(eid)
    seen=set()
    for ids in title_index.values():
        for pair in combinations(sorted(ids),2):
            if pair in seen:continue
            seen.add(pair);a,b=(title_tokens[i] for i in pair)
            if len(a&b)>=2:lexical[pair]=(len(a&b)*1_000_000)//len(a|b)
    def ranked(source,blocks_enabled):
        out=[]
        for pair,score in sorted(source.items(),key=lambda item:(-item[1],item[0]))[:top_k]:
            out.append({'event_ids':list(pair),'titles':[by_id[i]['title'] for i in pair],'routing_score':score,
                'source_identity':digest([by_id[i] for i in pair]),'shared_blocks':evidence[pair] if blocks_enabled else [],
                'status':'REVIEW_REQUIRED','semantic_certificate':False,'execution_authority':False})
        return out
    block_top=ranked(scores,True);title_top=ranked(lexical,False)
    b={tuple(x['event_ids']) for x in block_top};t={tuple(x['event_ids']) for x in title_top}
    return {'schema':'s6.discovery-census.v1','summary':{'events':len(events),'market_records':market_count,
      'unique_market_ids':len(market_ids),'distinct_market_rule_texts':len(texts),'open_orderbook_records':eligible,
      'all_cross_event_pairs':len(events)*(len(events)-1)//2,'shared_block_candidate_pairs':len(scores),
      'title_candidate_pairs':len(lexical),'ignored_high_frequency_blocks':ignored,'review_budget_per_router':top_k,
      'top_pair_overlap':len(b&t),'block_only_top_pairs':len(b-t),'semantic_certificates':0,'economic_tests':0},
      'block_candidates':block_top,'title_candidates':title_top,
      'all_block_pair_ids':[list(pair) for pair in sorted(scores)],
      'limits':['RETRIEVAL_NOT_ENTAILMENT','NO_INDEPENDENT_GOLD_PRECISION_OR_RECALL','NO_QUOTES_OR_PROFIT_ESTIMATES',
                'SOURCE_POPULATION_NOT_FULL_MARKET','SHARED_BOILERPLATE_DIFFERENT_SUBJECTS_ARE_NEGATIVE_CONTROLS']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    events,provenance=load_catalog(a.archive,a.sha256);r=census(events);r['provenance']=provenance
    with a.output.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(r['summary']))
if __name__=='__main__':main()
