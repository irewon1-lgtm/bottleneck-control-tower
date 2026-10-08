"""Bounded primary-source search planning and actual-capture relevance checks."""
from copy import deepcopy
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from . import forecast_discovery as strict
from .precursor_scope_reader import valid_product

VERSION = 'missing-primary-evidence-2'
UNKNOWN = 'UNKNOWN'
GENERAL_SITES = frozenset(('wikipedia.org','en.wikipedia.org','dictionary.com','britannica.com','investopedia.com','merriam-webster.com'))
PRIMARY_QUERY = '(site:sec.gov OR site:gov OR "investor relations" OR "official press release")'
MISSING_HINTS = {'customer_group':'customer purchase agreement delivery obligation',
                'specification':'product specification qualification standard',
                'supply_pool':'qualified supplier production facility customer certification',
                'explicit_need_or_qualified_readiness_date':'delivery schedule commercial production qualification date',
                'comparable_quantity_unit_basis_coverage':'unreserved qualified output allocation capacity units period',
                'relief':'qualified alternative inventory expansion cancellation delay'}


def error_status(exc):
    if isinstance(exc, HTTPError):
        return {403:'HTTP_403',429:'HTTP_429',401:'HTTP_401'}.get(exc.code,'HTTP_'+str(exc.code))
    if isinstance(exc,(TimeoutError,socket.timeout)) or (isinstance(exc,URLError) and isinstance(exc.reason,(TimeoutError,socket.timeout))):return 'TIMEOUT'
    if 'Tunnel connection failed: 403' in str(exc):return 'CONNECT_BLOCKED'
    return 'NETWORK_FAILED'


def bounded_plan(plan):
    result=deepcopy(plan);requests=[]
    for r in result['requests']:
        scope=r['scope']
        if not valid_product(r['target']):
            result['blocked'].append({'request_id':r['request_id'],'reason':'INVALID_PRODUCT_NO_QUERY'});continue
        # A short general commodity alone is not enough for an independent
        # program/eligibility search. The seed source must supply another key.
        if len(r['target'].split())<2 and sum(v!=UNKNOWN for v in scope.values())<2:
            result['blocked'].append({'request_id':r['request_id'],'reason':'INSUFFICIENT_VERIFIED_SEARCH_SCOPE'});continue
        if not r['query'].endswith(PRIMARY_QUERY):r['query']+=' '+PRIMARY_QUERY
        hints=' '.join(MISSING_HINTS[k] for k in r.get('missing_fields',[]) if k in MISSING_HINTS)
        if hints:r['query']=r['query'].removesuffix(' '+PRIMARY_QUERY)+' '+hints+' '+PRIMARY_QUERY
        # Preserve a reviewable missing-fields plan, but a multiword product
        # alone is still too broad for an external search. An explicit cited
        # original can be captured without disclosing a general query.
        r['search_scope_ready']=sum(v!=UNKNOWN for v in scope.values())>=2
        if not r['search_scope_ready']:r['search_scope_blocker']='PRODUCT_ONLY_NO_VERIFIED_PROGRAM_SPEC_REGION_OR_PARTY'
        r['search_policy_version']=VERSION
        r['success_definition']='ACQUIRED_BODY_AND_SOURCE_BOUND_NEW_ROLE_EVIDENCE'
        requests.append(r)
    result['requests']=requests
    return result


def rank_url(url):
    host=(urlsplit(url).hostname or '').lower();path=urlsplit(url).path.lower()
    if host=='sec.gov' or host.endswith('.sec.gov'):return 0
    if re.search(r'\.gov(?:\.[a-z]{2})?$',host):return 1
    if re.search(r'(?:investor|/ir/|sec-filings|newsroom|press-release)',url,re.I):return 2
    return 5


def primary_origin(document, matches):
    """A priority URL is a lead; publisher/issuer evidence closes the role."""
    url=document.get('origin_url','');priority=rank_url(url)
    if priority==0:
        return document.get('official_source_reader')=='sec-original-reader-1' and document.get('checks',{}).get('official_accession_row') is True
    if priority==1:return document.get('provenance')=='PASS'
    publisher=document.get('origin_publisher','')
    host=(urlsplit(url).hostname or '').lower()
    tokens=re.findall(r'[a-z0-9]+',publisher.lower())
    # A newsroom/press-release path alone cannot turn a newswire into the
    # issuer. The observed publisher must own the hostname and explicitly
    # identify itself in the matching product/role statement.
    identity=''.join(t for t in tokens if t not in ('inc','ltd','corp','corporation','company','the'))
    owns_host=len(identity)>=3 and identity in re.sub(r'[^a-z0-9]','',host)
    self_statement=any(re.search(r'(?<!\w)'+re.escape(publisher)+r'(?!\w)',e['source_quote'],re.I) for e in matches) if publisher else False
    # Website metadata often adds "Technical Blog" or "Test Systems" to an
    # issuer. Require a distinctive observed brand both in hostname AND in an
    # actual source statement; neither a priority URL nor a copied quote is
    # sufficient. No issuer/target exception table.
    generic={'technical','blog','news','systems','components','semiconductors','advanced','holdings','rights','reserved','aioseo','inc','ltd','corp','corporation','company','the','all'}
    brands=[t for t in tokens if len(t)>=4 and t not in generic and t in re.sub(r'[^a-z0-9]','',host)]
    if not owns_host and brands:
        owns_host=True
        self_statement=any(re.search(r'\b'+re.escape(t)+r'\b',e['source_quote'],re.I) for t in brands for e in matches)
    return owns_host and self_statement


def external_query_allowed(request):
    """External disclosure is explicit and distinct from a source access grant.

    A private collector cache is the default origin. Public-only query builders
    must attach their public source references, or an operator must explicitly
    authorize this particular request. Direct original URLs need no query.
    """
    return (request.get('external_query_authorized') is True or
            (request.get('query_data_classification')=='PUBLIC_ONLY' and request.get('query_private_derived') is False
             and request.get('public_query_verified') is True and bool(request.get('public_query_references'))))


def public_query_request(request,documents,new_document_ids):
    """Construct only from verified primary bodies fetched in THIS cycle.

    Never reuse a private-cache query string, even if it looks public. Static
    search hints plus literal facts independently acquired from a public
    original are the sole payload. Old cached records cannot authorize it.
    """
    docs={d['document_id']:d for d in documents};refs=[]
    for source_id in request['seed_document_ids']:
        if source_id not in new_document_ids or source_id not in docs:return deepcopy(request)
        d=docs[source_id]
        if d.get('provenance')!='PASS' or not primary_origin(d,d.get('precursor_events',[])):return deepcopy(request)
        for e in d.get('precursor_events',[]):
            for k,f in e['scope'].items():
                if k in request['scope'] and request['scope'][k]!=UNKNOWN and ' '.join(f['value'].casefold().split())==request['scope'][k]:
                    ref=f['reference'];loc=ref['locator']
                    if (ref['document_id']!=source_id or ref['body_sha256']!=d['body_sha256'] or d['body'][loc['start']:loc['end']]!=ref['source_quote']):
                        raise ValueError('PUBLIC_QUERY_SOURCE_REFERENCE_MISMATCH')
                    refs.append((k,ref))
    known={k for k,v in request['scope'].items() if v!=UNKNOWN}
    if {k for k,r in refs}!=known:return deepcopy(request)
    hints=' '.join(MISSING_HINTS[k] for k in request.get('missing_fields',[]) if k in MISSING_HINTS)
    query=' '.join('"'+request['scope'][k]+'"' for k in request['scope'] if k in known)
    query+=' '+('purchase orders delivery schedule' if request['role']=='DEMAND' else 'qualified capacity production allocation readiness')+' '+hints+' '+PRIMARY_QUERY
    return {**deepcopy(request),'query':query,'query_data_classification':'PUBLIC_ONLY','query_private_derived':False,'public_query_verified':True,'public_query_references':[r for k,r in refs]}


def select_urls(urls, limit=3):
    clean=[]
    for url in dict.fromkeys(urls):
        host=(urlsplit(url).hostname or '').lower()
        if host in GENERAL_SITES or any(host.endswith('.'+h) for h in GENERAL_SITES):continue
        if any(x in url.lower() for x in ('/dictionary/','/definition/','/wiki/')):continue
        clean.append(url)
    return sorted(clean,key=rank_url)[:limit]


def copied_body(a,b):
    if a['body_sha256']==b['body_sha256']:return True
    # Reposted releases with a different title/footer are still one source.
    def shingles(d):
        words=re.findall(r'\w+',d['body'].casefold())
        return {tuple(words[i:i+8]) for i in range(max(0,len(words)-7))}
    x,y=shingles(a),shingles(b)
    return len(x)>40 and len(y)>40 and len(x & y)/min(len(x),len(y))>=0.85


def validate_capture(request, document, documents):
    result={'state':'INVALID_OR_UNAVAILABLE','new_evidence':0,'role':request['role'],
            'publisher':document.get('origin_publisher'), 'published_at':document.get('published_at'),
            'acquired_at':document.get('acquired_at'),'origin_url':document.get('origin_url'),
            'body_sha256':document.get('body_sha256'),'source_priority':rank_url(document.get('origin_url',''))}
    if document.get('provenance')!='PASS':return {**result,'reason':'SOURCE_ACCESS_OR_PROVENANCE_BLOCKED'}
    seeds=[d for d in documents if d['document_id'] in request['seed_document_ids']]
    if any(copied_body(document,d) for d in documents if d['document_id']!=document['document_id']):return {**result,'state':'DUPLICATE_OR_REPUBLICATION','reason':'COPIED_OR_SAME_BODY'}
    independent_seeds=[d for d in seeds if strict.independent({**document,'excerpt_sha256':document['body_sha256']},{**d,'excerpt_sha256':d['body_sha256']})]
    if seeds and not independent_seeds:return {**result,'state':'SAME_ORIGIN','reason':'NO_INDEPENDENT_ORIGIN'}
    matches=[]
    for e in document.get('precursor_events',[]):
        scope={k:' '.join(f['value'].casefold().split()) for k,f in e['scope'].items()}
        if scope.get('product')!=request['scope']['product']:continue
        if any(v!=UNKNOWN and scope.get(k,UNKNOWN)!=UNKNOWN and scope[k]!=v for k,v in request['scope'].items()):continue
        if e['role']!=request['role'] or e['kind']=='CONFIRMATION':continue
        matches.append(e)
    if not matches:return {**result,'state':'BODY_ACQUIRED_NO_MATCHING_EVIDENCE','reason':'ROLE_OR_PRODUCT_OR_SPECIFICATION_MISMATCH'}
    # A secondary article is an origin-finding lead. The actual primary body,
    # not the count of independently worded articles, must close a missing side.
    primary=primary_origin(document,matches)
    # Preserve the existing explicit source-scope document contract. These
    # originals must declare all five scope dimensions in their own body, not
    # inherit them from a quote, query or another document. Do not label them
    # primary merely because of their format.
    explicit_scope=all(re.search(r'(?im)(?:^|[;\n])\s*'+k.replace('_',r'[ _-]')+r'\s*(?::|=|is|are)\s*\S',document['body']) for k in ('product','specification','region','customer_group','supply_pool'))
    explicit_scope=explicit_scope and any(not e['missing_scope'] for e in matches) and not re.search(r'\baccording to|originally published|reported by|provided by\b',document['body'],re.I)
    valid=primary or explicit_scope
    return {**result,'state':'VALID_PRIMARY_EVIDENCE' if primary else 'VALID_ORIGINAL_SCOPE_EVIDENCE' if explicit_scope else 'SECONDARY_SOURCE_LEAD',
            'new_evidence':len(matches) if valid else 0,'event_ids':[e['event_id'] for e in matches],
            'independent_seed_ids':[d['document_id'] for d in independent_seeds],
            'scope_complete':any(not e['missing_scope'] for e in matches)}
