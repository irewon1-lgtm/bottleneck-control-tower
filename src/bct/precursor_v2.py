"""Evidence-addressed v2 shadow extraction and the sole pair decision gate.

No collection, v1 writes, prospective calls, scoring or industry TARGET dictionary.
Unsupported language is retained as UNKNOWN, never completed by similarity.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import calendar
import hashlib
import json
import re
from functools import lru_cache

from .objective_lock import stamp_export
from .forecast_discovery import publication_cutoff

VERSION = 'BCT_PRECURSOR_V2_SHADOW_2'
UNKNOWN = 'UNKNOWN'
PERIOD = r'(?:20\d{2}-\d{2}-\d{2}|(?:H[12]|[12]H)\s*20\d{2}|20\d{2}\s*H[12]|(?:first|second) half of 20\d{2}|20\d{2})'
ENTITY = {
    'manufacturer': r'\b(?:manufacturer|manufactured by)\s+([A-Za-z][\w-]*)',
    'model': r'\bmodel\s+([A-Za-z][\w./-]*)',
    'specification': r'\b(?:grade|specification|standard)\s+([A-Za-z][\w./-]*)',
    'product': r'\bproduct\s+["“]([^"”]+)["”]',
    'contract': r'\bcontract\s+([A-Za-z0-9][\w./-]*\d[\w./-]*)',
    'facility': r'\b(?:facility|plant)\s+([A-Za-z][\w./-]*\d[\w./-]*)',
    'customer': r'\b(?:for customer|for buyer|customer group)\s+([A-Za-z][\w-]*)',
    'qualification': r'\b(?:certification|certified to|qualification to|requires certification)\s+([A-Za-z][\w./-]*)',
    'region': r'\b(?:for|in) (?:the )?(United States|US|North America|Europe|EU|Canada|United Kingdom|UK|Japan|Germany|France)\b',
}
DIRECT_REQUOTE = re.compile(r'\b(?:according to|via a syndicated|originally published|reported by|provided by)\b', re.I)
SHORTAGE = re.compile(r'\b(?:shortages?|bottlenecks?|scarcity|tight[- ]supply)\b|병목|공급\s*부족', re.I)


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def clock(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.astimezone(timezone.utc)


def normalize(value):
    # Do not erase punctuation, revisions or model suffixes.
    v = ' '.join(value.casefold().split())
    return {'us': 'united states', 'uk': 'united kingdom'}.get(v, v)


def reference(doc, start, end):
    return {'document_id': doc['document_id'], 'body_sha256': doc['body_sha256'],
            'locator': {'start': start, 'end': end}, 'quote': doc['body'][start:end]}


def verify_reference(ref, docs):
    doc = docs[ref['document_id']]; a, b = ref['locator']['start'], ref['locator']['end']
    if (type(a) is not int or type(b) is not int or not 0 <= a < b <= len(doc['body'])
            or ref['body_sha256'] != doc['body_sha256'] or ref['quote'] != doc['body'][a:b]):
        raise ValueError('SOURCE_REFERENCE_MISMATCH')
    return ref['quote']


def validate_document(doc, as_of):
    if digest(doc['body'].encode()) != doc['body_sha256'] or doc.get('version', doc['body_sha256']) != doc['body_sha256']:
        raise ValueError('BODY_VERSION_MISMATCH')
    if doc.get('provenance_verified') is not True or any(doc.get(k) in (None, '', UNKNOWN) for k in ('origin_id', 'origin_url', 'origin_publisher')):
        raise ValueError('PROVENANCE_UNVERIFIED')
    if not re.match(r'https?://[^/]+', doc['origin_url']):
        raise ValueError('SOURCE_URL_INVALID')
    publication_cutoff(doc, clock(as_of), allow_unknown=True)


def period(text):
    """Bounds preserve source precision; they are not invented exact dates."""
    if re.fullmatch(r'20\d{2}-\d{2}-\d{2}', text):
        day = date.fromisoformat(text).isoformat()
        return {'start': day, 'end': day, 'precision': 'DATE', 'text': text}
    m = re.fullmatch(r'(H[12]|[12]H)\s*(20\d{2})|(20\d{2})\s*(H[12])|(first|second) half of (20\d{2})|(20\d{2})', text, re.I)
    if not m:
        raise ValueError('PERIOD_UNSUPPORTED')
    year = int(m[2] or m[3] or m[6] or m[7])
    half = m[1] or m[4] or m[5]
    start_month, end_month = (1, 12) if not half else (1, 6) if half.casefold() in ('h1', '1h', 'first') else (7, 12)
    return {'start': date(year, start_month, 1).isoformat(), 'end': date(year, end_month, calendar.monthrange(year, end_month)[1]).isoformat(),
            'precision': 'HALF' if half else 'YEAR', 'text': text}


def _fields(doc, quote, start):
    fields = {}
    for key, pattern in ENTITY.items():
        matches = list(re.finditer(pattern, quote, re.I))
        if key=='manufacturer':matches += list(re.finditer(r'\b([A-Za-z][\w-]*) manufactures (?:model|product)\b',quote,re.I))
        if key=='model':matches += list(re.finditer(r'\b((?=[\w./-]*\d)[A-Za-z][\w./-]*) model\b',quote,re.I))
        matches=[m for m in matches if _identifier_value(m[1].rstrip('.'),key)]
        if len({normalize(m[1].rstrip('.')) for m in matches}) == 1:
            m = matches[0]
            raw=m[1].rstrip('.')
            fields[key] = {'value': normalize(raw), 'reference': reference(doc, start+m.start(1), start+m.start(1)+len(raw))}
    # Proper model names in ordinary prose need not follow a literal "model".
    models=list(re.finditer(NAMED_MODEL,quote))
    if 'model' not in fields and len({normalize(m[0]) for m in models})==1:
        m=models[0];fields['model']={'value':normalize(m[0]),'reference':reference(doc,start+m.start(),start+m.end()),'named_model':True}
    _site_fields(doc, quote, start, fields)
    return fields


IDENTIFIER_STOP=frozenset('announced announces announcement said says to in for of on by at from with the a an is was are were has have will can may this that following next previous as under'.split())
# Structured casing/numerals, not a list of companies, products or TARGETs.
MODEL_STEM=r'(?:[a-z]+[A-Z][A-Za-z]*|[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}[a-z]*|[A-Z][A-Za-z0-9]*-[A-Za-z0-9]+)'
NAMED_MODEL=r'(?<![\w/-])(?:'+MODEL_STEM+r'(?:\s+(?:Increment|Block|Mark|Series)\s+[0-9]+[A-Za-z]?|\s+(?!20\d{2}\b)[0-9]{2,4}[A-Za-z]?)|[a-z]+[A-Z][A-Za-z]*\s+[A-Z][a-z]+)(?![\w/-])'


def _identifier_value(raw,key):
    if normalize(raw) in IDENTIFIER_STOP:return False
    return bool(re.search(r'[A-Z0-9]',raw)) if key in ('manufacturer','model','specification','contract','facility','customer','qualification') else True


def _identity_refs(field):
    return [field['reference']]+field.get('support_references',[])


def _named_sites(doc):
    """Named installations require explicit owner or contract-production scope.

    A name match alone, a publisher name or an unspecified supply pool is never
    ownership evidence. No product, qualification, quantity or time is inherited.
    """
    name=r'[A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4}'
    pattern=r'\b('+name+r')\s+(Mine|Project|Plant|Facility|Refinery|Factory|Terminal)\b'
    sites=[]
    for line in re.finditer(r'[^\n]+',doc['body']):
        q=line[0]
        matches=list(re.finditer(pattern,q))
        for m in matches:
            raw=m[0];offset=m.start()
            if raw.startswith('The '):raw=raw[4:];offset+=4
            stem=raw.rsplit(' ',1)[0]
            if normalize(stem) in IDENTIFIER_STOP or stem in ('New','Government','National'):continue
            owner=None
            owned=re.search(re.escape(raw)+r"\b[^.!?]{0,120}?\bis\s+("+name+r")[’']s\s+(?:wholly-owned\s+)?(?:asset|mine|project|plant|facility)\b",q)
            owns=re.search(r'\b('+name+r')\s+owns\s+(?:the\s+)?'+re.escape(raw)+r'\b',q)
            contract=re.search(r'\bagreement with\s+('+name+r')(?:\s+(?:plc|Ltd|Inc)\.?)?(?:\s+\([^)]*\))*\s+covering production from\s+(?:the\s+)?'+re.escape(raw)+r'\b',q)
            proof=owned or owns or contract
            if proof:owner=proof[1]
            if not owner:continue
            aliases=[]
            alias=re.search(re.escape(raw)+r'[^.!?]{0,80}?\([“"]('+name+r')[”"]\)',q)
            if alias:aliases.append(alias[1])
            sites.append({'name':normalize(raw),'owner':normalize(owner),'aliases':aliases,
                          'reference':reference(doc,line.start()+offset,line.start()+offset+len(raw)),
                          'ownership_reference':reference(doc,line.start()+proof.start(),line.start()+proof.end())})
    return sites


def _site_fields(doc,quote,start,fields):
    candidates=[]
    for site in _named_sites(doc):
        names=[site['name']]+[normalize(a) for a in site['aliases']]
        mentioned=any(re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',normalize(quote)) for n in names)
        # A titled, uniquely owned project timeline is explicitly page-scoped.
        title=doc['body'].splitlines()[0] if doc['body'].splitlines() else ''
        timeline=doc['body'].find('The Timeline\n')
        page_scoped=(normalize(title)=='project - '+site['name'] and timeline>=0 and start>timeline
                     and len({(s['name'],s['owner']) for s in _named_sites(doc)})==1
                     and re.search(r'\b(?:production|commissioning|ramp|capacity)\b',quote,re.I))
        if mentioned or page_scoped:candidates.append(site)
    if len({(s['name'],s['owner']) for s in candidates})!=1:return
    site=candidates[0]
    fields['facility']={'value':site['owner']+'::'+site['name'],'site_name':site['name'],
                        'site_owner':site['owner'],'named_site':True,'reference':site['reference'],
                        'support_references':[site['ownership_reference'],reference(doc,start,start+len(quote))]}


def _owned_facilities(doc):
    # An owner/product/location definition is a source identity, not nominal
    # capacity or an inferred geographic qualification.
    name=r'[A-Z][\w-]*(?:\s+(?:[A-Z][\w-]*|and|&)){0,4}'
    pattern=r'('+name+r')[’\']s?\s+(?:new\s+)?([a-z][a-z-]*(?:\s+[a-z][a-z-]*){0,2})\s+(?:plant|facility)\s+(?:in|at)\s+('+name+r'(?:,\s*'+name+r')?)'
    out=[]
    for m in re.finditer(pattern,doc['body']):
        out.append({'value':normalize(m[0]),'reference':reference(doc,m.start(),m.end()),
                    'owner':m[1],'product':m[2],'location':m[3]})
    return out


def _bind_source_identity(doc,sentences,index):
    """Bind entity references only; never move periods, quantities or eligibility.

    Named models can be referenced by a named speaker's demonstrative quotation.
    A facility needs a unique explicit owner/product/location plus either that
    owner's named manager or a same-paragraph product/offtake antecedent.
    """
    sentence=sentences[index];q=sentence['quote'];fields=sentence['fields'];body=doc['body']
    name=r'[A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4}'
    if 'model' not in fields:
        alias=list(re.finditer(r'((?:Increment|Block|Mark|Series)\s+[0-9]+[A-Za-z]?)\s+of\s+(?:the\s+)?('+name+r'),\s*(?:or|also known as)\s+('+MODEL_STEM+r')(?!\w)',q))
        if len(alias)==1:
            m=alias[0]
            fields['model']={'value':normalize(m[3]+' '+m[1]),'reference':reference(doc,sentence['start']+m.start(),sentence['start']+m.end()),
                'named_model':True,'derivation':'EXPLICIT_VARIANT_ALIAS','support_references':[reference(doc,sentence['start']+m.start(n),sentence['start']+m.end(n)) for n in (1,2,3)]}
    if 'model' not in fields and re.search(r'\b(?:those|these|that)\s+(?:trucks|vehicles|missiles|satellites|cells|system)\b',q,re.I):
        speaker=re.search(r'\b('+name+r')\s+(?:said|says)\b',q)
        if speaker:
            last=speaker[1].split()[-1];antecedents=[]
            for previous in sentences[max(0,index-2):index]:
                model=previous['fields'].get('model')
                if model and re.search(r'\b'+re.escape(last)+r'\b',previous['quote']):antecedents.append((model,previous))
            if len(antecedents)==1:
                model,previous=antecedents[0]
                fields['model']={**deepcopy(model),'source_bound_coreference':True,
                    'support_references':[reference(doc,previous['start'],previous['start']+len(previous['quote'])),reference(doc,sentence['start'],sentence['start']+len(q))]}
    if 'facility' in fields:return
    facilities=_owned_facilities(doc)
    if len(facilities)!=1:return
    f=facilities[0];supports=[]
    if re.search(r'\b(?:another|different|second)\s+(?:plant|facility|system)|\badditional locations\b',q,re.I):return
    speaker=re.search(r'\b('+name+r')\s+(?:said|says)\b',q)
    if speaker and re.search(r'\b(?:it|the plant|the facility|initial system)\b',q,re.I):
        last=speaker[1].split()[-1]
        for m in re.finditer(r'\b('+name+r'),\s*(?:the\s+)?(?:general manager|chief executive|CEO|president)\s+of\s+('+name+r')',body):
            if m[1].split()[-1]==last and normalize(m[2])==normalize(f['owner']):supports.append(reference(doc,m.start(),m.end()))
        if len(supports)!=1:supports=[]
    if not supports and re.search(r'\bofftake agreement\b',q,re.I) and index:
        prev=sentences[index-1]
        # Explicit "Demand for the <product>" ties this agreement's product to
        # the unique defined installation; adjacency alone is insufficient.
        if re.search(r'\bDemand for the '+re.escape(f['product'])+r'\b',prev['quote'],re.I):
            supports=[reference(doc,prev['start'],prev['start']+len(prev['quote']))]
    if supports:
        fields['facility']={'value':f['value'],'reference':f['reference'],
                            'source_bound_coreference':True,'support_references':supports+[reference(doc,sentence['start'],sentence['start']+len(q))]}


def _additional_precursor_role(q):
    """Previously omitted facts/conditions; no investor/investigator stemming.

    This expands event retention only. Unsupported scope/period stays UNKNOWN
    and the unchanged eligibility gate still requires qualified evidence.
    """
    if re.search(r'forward-looking statements|investor (?:contact|call|conference)|investments? in new factories.*employment data|\b(?:investigators?|investigational|investigation|redemptions|SPAC|bond market|investment gold|junior miners|junior funding|risk capital|per-share|capital allocation plan|non-GAAP|Distributable Cash Flow|Consolidated Adjusted EBITDA|cost of sales|Quarterly Report on Form|Securities and Exchange Commission|associate editor)\b',q,re.I):return None
    if re.search(r'\b(?:purchase of|agreed to purchase|entered into a.{0,80}sale and purchase agreement)\b',q,re.I):return ('DEMAND','PURCHASE_CONTRACT')
    if re.search(r'\bpurchase\b.{0,60}\bexpands\b',q,re.I):return ('CONTEXT','ACQUISITION_SCOPE')
    if re.search(r'\b(?:will (?:be )?deployed|(?:expanding|our) deployment|(?:portion|part) of the deployment)\b',q,re.I):return ('DEMAND','DEPLOYMENT')
    if re.search(r'\b(?:awarded|signed)\b.{0,110}\b(?:IDIQ|indefinite delivery)\b',q,re.I):return ('DEMAND','PURCHASE_CONTRACT')
    if re.search(r'\b(?:stockpiles?)\b',q,re.I) and re.search(r'\b(?:rebuild|rebuilding|drawn down|replenishment)\b',q,re.I):return ('SUPPLY','INVENTORY_CONSTRAINT')
    if re.search(r'\b(?:restrictions?|dependencies|dependence|origin requirements?|export controls?|regulation)\b',q,re.I) and re.search(r'\b(?:access|sovereignty|supply|origin|imports?|exports?|infrastructure|production|vehicles|customers)\b',q,re.I):return ('CONTEXT','SUPPLY_POOL_CONSTRAINT')
    if re.search(r'\bdependencies\b',q,re.I) and re.search(r'\b(?:cut|reduce|remove)\b',q,re.I):return ('CONTEXT','SUPPLY_POOL_CONSTRAINT')
    if re.search(r'\bpartnerships\b',q,re.I) and re.search(r'\b(?:meet the requirement|sovereignty|customers)\b',q,re.I):return ('CONTEXT','APPLICABILITY_CONDITION')
    if re.search(r'\b(?:validation|accreditation)\b',q,re.I) and re.search(r'\b(?:will|before|operational)\b',q,re.I):return ('SUPPLY','QUALIFICATION_ACTIVITY')
    if re.search(r'\b(?:future experiments|Running until)\b',q,re.I) and re.search(r'\b(?:technologies|industrial teams|navigation|campaign)\b',q,re.I):return ('CONTEXT','DEVELOPMENT_ACTIVITY')
    if re.search(r'\b(?:invest|investing|investment|investments|funding)\b',q,re.I):
        physical=re.search(r'\b(?:parts|factories|plant|manufacturing|industrial|mining|processing|refining|missiles|space|space resources|freedom of action|technology|roadwork|traffic|alert systems|strategic partnerships)\b',q,re.I)
        action=re.search(r'\b(?:plan|plans|will|new|support|supports|supporting|secured|includes|aimed|hold off|investing|invest heavily|invest a|accelerate|double|strengthening|strategic|next decade)\b',q,re.I)
        if physical and action:return ('SUPPLY','CAPACITY_INVESTMENT')
    return None


def _same_event(a, b):
    # Adjacency alone and an unnamespaced model token are insufficient.
    if any(k in a and k in b and a[k]['value']!=b[k]['value'] for k in ('contract','facility','model','specification','region','qualification')):
        return False
    for key in ('contract', 'facility', 'model'):
        if (key in a and key in b and a[key]['value'] == b[key]['value']
                and 'manufacturer' in a and 'manufacturer' in b
                and a['manufacturer']['value'] == b['manufacturer']['value']):
            return True
    return False


def extract(doc):
    sentences = []
    for para in re.finditer(r'[^\n]+', doc['body']):
        starts = [0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])', para.group())]+[len(para.group())]
        for a, b in zip(starts, starts[1:]):
            text = para.group()[a:b].strip()
            if not text: continue
            off = para.start()+a+len(para.group()[a:b])-len(para.group()[a:b].lstrip())
            sentences.append({'quote': text, 'start': off, 'fields': _fields(doc, text, off)})
    for i in range(len(sentences)):_bind_source_identity(doc,sentences,i)
    events = []
    for i, sentence in enumerate(sentences):
        q, off = sentence['quote'], sentence['start']; fields = deepcopy(sentence['fields'])
        contexts = [sentence]
        for neighbor in sentences[max(0, i-1):i]+sentences[i+1:i+2]:
            if _same_event(sentence['fields'], neighbor['fields']):
                contexts.append(neighbor)
                for k, v in neighbor['fields'].items():
                    if k not in fields: fields[k] = deepcopy(v)
                    elif fields[k]['value'] != v['value']: fields.pop(k, None)
        has_confirmation = bool(SHORTAGE.search(q))
        negated = bool(re.search(r'\b(?:no|not|without|avoid|avoided|prevent|prevented)\b.{0,45}(?:'+SHORTAGE.pattern+r')', q, re.I)) if has_confirmation else False
        prospective = bool(re.search(r'\b(?:may|might|could|expected|forecast|hypothetical|risk of)\b', q, re.I))
        if has_confirmation:
            role = 'CONFIRMATION'; kind = 'ACTUAL' if not negated and not prospective else 'NEGATED_OR_FORECAST'
        elif re.search(r'\b(?:cancelled|canceled|postponed|deferred)\b', q, re.I): role, kind = 'DEMAND_CHANGE', 'ADVERSE'
        elif re.search(r'\b(?:sufficient qualified|covers all|cover all)\b', q, re.I): role, kind = 'RELIEF', 'SUFFICIENT'
        elif re.search(r'\b(?:orders?|procurement|backlog|offtake|reservation|customer CAPEX|delivery requirement)\b', q, re.I): role, kind = 'DEMAND', 'REQUIREMENT'
        elif re.search(r'\b(?:capacity|production|ramp|commissioning|qualification|inventory|qualified supply)\b', q, re.I): role, kind = 'SUPPLY', 'READINESS_OR_QUANTITY'
        else:
            additional=_additional_precursor_role(q)
            if not additional:continue
            role,kind=additional
        e = {'event_id': digest([VERSION, doc['document_id'], doc['body_sha256'], off, q]), 'document_id': doc['document_id'],
             'role': role, 'kind': kind, 'reference': reference(doc, off, off+len(q)), 'fields': fields,
             'context_references': [reference(doc, s['start'], s['start']+len(s['quote'])) for s in contexts],
             'direct_origin': not bool(DIRECT_REQUOTE.search(q)), 'facts': {}, 'period': None}
        patterns = {'DEMAND': r'\b(?:delivery|required|needed|deployment)\s+(?:on|by|in|during|for)\s+('+PERIOD+r')\b',
                    'SUPPLY': r'\b(?:qualification(?: to [\w./-]+)? (?:completes|completed)|ramp (?:completes|completed)|commissioning (?:completes|completed)|ready|available|qualified capacity)\s+(?:on|from|in|during|by|of \d+ units in)\s+('+PERIOD+r')\b',
                    'RELIEF': r'\b(?:available|ready|qualified supply)\s+(?:on|from|in|by)\s+('+PERIOD+r')\b',
                    'DEMAND_CHANGE': r'\b(?:until|to|in)\s+('+PERIOD+r')\b'}
        for ctx in contexts:
            pat = patterns.get(role)
            if pat:
                matches = list(re.finditer(pat, ctx['quote'], re.I))
                if len(matches) == 1:
                    m = matches[0]; candidate = {**period(m[1]), 'reference': reference(doc, ctx['start']+m.start(1), ctx['start']+m.end(1))}
                    if e['period'] and (e['period']['start'], e['period']['end']) != (candidate['start'], candidate['end']): e['period'] = None; break
                    e['period'] = candidate
        def flag(name, pattern):
            if re.search(pattern, q, re.I): e['facts'][name] = {'value': True, 'reference': e['reference']}
        flag('committed', r'\b(?:signed|awarded|firm|binding|committed|confirmed)\b')
        if re.search(r'\b(?:not|never|not yet)\s+(?:signed|awarded|binding|committed|confirmed)\b',q,re.I):e['facts'].pop('committed',None)
        if re.search(r'\b(?:hypothetical|rumou?r|proposed|plans to sign|expected to sign)\b',q,re.I):e['facts'].pop('committed',None)
        flag('allocated', r'\b(?:allocated|assigned|reserved)\s+(?:to|for)\s+contract\b')
        flag('qualified', r'\bqualified\b(?!\s+(?:later|after))')
        if re.search(r'\b(?:not|not yet|never) qualified\b', q, re.I): e['facts'].pop('qualified', None)
        flag('delayed', r'\b(?:delayed|not ready by|later than demand|after the need window)\b')
        flag('covers_all', r'\b(?:covers all|cover all|sufficient qualified supply for all)\b')
        if re.search(r'\b(?:not|cannot|never)\s+(?:cover|covers)|\bnot sufficient\b',q,re.I):e['facts'].pop('covers_all',None)
        if role=='DEMAND_CHANGE' and re.search(r'\b(?:not|never)\s+(?:cancelled|canceled|postponed|deferred)\b',q,re.I):e['kind']='NEGATED'
        qual=fields.get('qualification',{}).get('value')
        if qual:
            bound=r'\b(?:qualification to '+re.escape(qual)+r' (?:completes|completed)|certified to '+re.escape(qual)+r'|qualified (?:capacity|supply|production) under certification '+re.escape(qual)+r')\b'
            for ctx in contexts:
                if re.search(bound,ctx['quote'],re.I) and not re.search(r'\b(?:not|not yet|never) certified\b',ctx['quote'],re.I):
                    e['facts']['qualification_bound']={'value':True,'reference':reference(doc,ctx['start'],ctx['start']+len(ctx['quote']))};break
        numbers = list(re.finditer(r'(?<![\w$€£])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s+(units|cells|trucks|satellites|tonnes|TEUs|mtpa)(?:\s+(per year|per month))?\b', q, re.I))
        if len(numbers) == 1:
            m = numbers[0]
            e['facts']['quantity'] = {'value': float(m[1].replace(',', '')), 'reference': reference(doc, off+m.start(), off+m.end())}
            e['facts']['unit'] = {'value': normalize(m[2])+((' '+normalize(m[3])) if m[3] else ''), 'reference': e['facts']['quantity']['reference']}
        for basis in ('total', 'additional', 'unallocated'):
            m = re.search(r'\b'+basis+r'\b', q, re.I)
            if m: e['facts']['basis'] = {'value': basis, 'reference': reference(doc, off+m.start(), off+m.end())}; break
        events.append(e)
    return events


def value(event, key):
    return event.get('fields', {}).get(key, {}).get('value', UNKNOWN)


def fact(event, key):
    return event.get('facts', {}).get(key, {}).get('value')


def relationship(a, b, evidence, docs):
    """Equivalence, allocation and required-component edges stay distinct."""
    ma, mb = value(a, 'manufacturer'), value(b, 'manufacturer')
    model_a, model_b = value(a, 'model'), value(b, 'model')
    for field in ('specification', 'region', 'qualification', 'customer', 'contract'):
        av, bv = value(a, field), value(b, field)
        if UNKNOWN not in (av, bv) and av != bv: return {'state': 'INCOMPATIBLE', 'reason': 'DIFFERENT_'+field.upper()}
    refs = []
    if (value(a,'facility')!=UNKNOWN and value(b,'facility')!=UNKNOWN and value(a,'facility')!=value(b,'facility')
            and not (value(a,'contract')==value(b,'contract')!=UNKNOWN and fact(b,'allocated'))):
        return {'state':'INCOMPATIBLE','reason':'DIFFERENT_FACILITIES_WITHOUT_VERIFIED_ALLOCATION'}
    af,bf=a['fields'].get('facility',{}),b['fields'].get('facility',{})
    if (af.get('named_site') and bf.get('named_site') and af['value']==bf['value']
            and af.get('site_owner')==bf.get('site_owner') and af.get('site_name')==bf.get('site_name')
            and not any(UNKNOWN not in (value(a,k),value(b,k)) and value(a,k)!=value(b,k)
                        for k in ('manufacturer','model','product'))):
        return {'state':'VERIFIED','kind':'SAME_FACILITY','references':_identity_refs(af)+_identity_refs(bf)}
    if ma != UNKNOWN and ma == mb and model_a != UNKNOWN and model_a == model_b:
        kind = 'CONTRACT_ALLOCATION' if value(a, 'contract') != UNKNOWN and value(a, 'contract') == value(b, 'contract') and fact(b, 'allocated') else 'SAME_MODEL'
        refs = [a['fields']['manufacturer']['reference'], b['fields']['manufacturer']['reference'], a['fields']['model']['reference'], b['fields']['model']['reference']]
        if kind == 'CONTRACT_ALLOCATION': refs += [a['fields']['contract']['reference'], b['facts']['allocated']['reference']]
        return {'state': 'VERIFIED', 'kind': kind, 'references': refs}
    if ma != UNKNOWN and ma == mb and value(a, 'product') != UNKNOWN and value(a, 'product') == value(b, 'product') and value(a, 'specification') != UNKNOWN and value(a, 'specification') == value(b, 'specification'):
        return {'state': 'VERIFIED', 'kind': 'SAME_PRODUCT', 'references': [a['fields']['product']['reference'], b['fields']['product']['reference'], a['fields']['specification']['reference'], b['fields']['specification']['reference']]}
    # Same-source entity resolution is not independent origin evidence. A
    # namespaced facility or explicit proper model proves identity only; all
    # qualification, applicability and time checks remain in the common gate.
    if a['document_id']==b['document_id'] and not (UNKNOWN not in (ma,mb) and ma!=mb):
        for key,kind in (('facility','SAME_FACILITY'),('model','SAME_MODEL')):
            af,bf=a['fields'].get(key),b['fields'].get(key)
            if af and bf and af['value']==bf['value'] and (key=='facility' and af.get('source_bound_coreference') and bf.get('source_bound_coreference') or key=='model' and af.get('named_model') and bf.get('named_model')):
                return {'state':'VERIFIED','kind':kind,'references':_identity_refs(af)+_identity_refs(bf)}
    for edge in evidence:
        q = verify_reference(edge['reference'], docs)
        # Explicitly named endpoints and namespace must occur in the source.
        if ma == UNKNOWN or mb == UNKNOWN or any(x == UNKNOWN or x not in normalize(q) for x in (ma, mb, model_a, model_b)): continue
        def endpoint(manufacturer,model):
            return r'\bmanufacturer\s+'+re.escape(manufacturer)+r'\s+model\s+'+re.escape(model)+r'(?![\w/-]|\.\w)'
        ea,eb=endpoint(ma,model_a),endpoint(mb,model_b)
        alias_connector=r'\s+(?:is\s+)?(?:also known as|identical to|same model as)\s+'
        if (edge['kind'] == 'EXPLICIT_ALIAS' and ma == mb
                and (re.search(ea+alias_connector+eb,q,re.I) or re.search(eb+alias_connector+ea,q,re.I))):
            return {'state': 'VERIFIED', 'kind': 'SAME_MODEL', 'references': [edge['reference']]}
        if edge['kind'] == 'REQUIRED_COMPONENT' and re.search(eb+r'\s+(?:is required for|is a required component of)\s+'+ea, q, re.I):
            if not edge.get('component_need_period'): continue
            p = edge['component_need_period']; verify_reference(p['reference'], docs)
            if p['text'] not in p['reference']['quote']: raise ValueError('COMPONENT_PERIOD_REFERENCE_MISMATCH')
            return {'state': 'VERIFIED', 'kind': 'REQUIRED_COMPONENT', 'references': [edge['reference'], p['reference']], 'component_need_period': {**period(p['text']), 'reference': p['reference']}}
    if ma != UNKNOWN and mb != UNKNOWN and ma != mb: return {'state': 'INCOMPATIBLE', 'reason': 'DIFFERENT_MANUFACTURERS'}
    if model_a != UNKNOWN and model_b != UNKNOWN and model_a != model_b: return {'state': 'INCOMPATIBLE', 'reason': 'DIFFERENT_MODELS'}
    observed=any(value(a,k)!=UNKNOWN and value(a,k)==value(b,k) for k in ('model','contract','facility','product'))
    return {'state': 'PARTIAL', 'reason': 'IDENTITY_OR_NAMESPACE_UNKNOWN'} if observed else {'state':'UNLINKED','reason':'NO_EXPLICIT_SHARED_IDENTIFIER'}


def _independent(a, b, docs):
    da, db = docs[a['document_id']], docs[b['document_id']]
    if not a['direct_origin'] or not b['direct_origin']: return False
    keys = ('origin_id', 'origin_url', 'origin_publisher', 'body_sha256')
    if any(normalize(str(da[k])) == normalize(str(db[k])) for k in keys): return False
    if da.get('origin_family') and db.get('origin_family') and normalize(da['origin_family']) == normalize(db['origin_family']): return False
    return a['reference']['quote'] != b['reference']['quote']


@lru_cache(maxsize=128)
def _source_events(document_id,body_sha256,body):
    return {e['event_id']:e for e in extract({'document_id':document_id,'body_sha256':body_sha256,'body':body})}


def _validate_event(event, docs):
    doc=docs[event['document_id']]
    rebuilt = _source_events(doc['document_id'],doc['body_sha256'],doc['body'])
    if rebuilt.get(event['event_id']) != event:
        raise ValueError('EVENT_NOT_AUTOMATIC_SOURCE_BOUND_EXTRACTION')


def evaluate_pair_v2(demand, supply, *, documents, as_of, relationships=(), context_events=(), first_frozen_at=None, previous_first=None):
    """Synthesis, counters and shadow freeze consume this sealed decision."""
    docs = {d['document_id']: d for d in documents}; at = clock(as_of)
    for e in (demand, supply):
        validate_document(docs[e['document_id']], as_of); _validate_event(e, docs)
    relation = relationship(demand, supply, relationships, docs)
    out = {'version': VERSION, 'pair_id': digest([demand['event_id'], supply['event_id']]),
           'demand_event_id': demand['event_id'], 'supply_event_id': supply['event_id'], 'evaluated_at': as_of,
           'relation': relation, 'independent': _independent(demand, supply, docs), 'scope_verified': False,
           'comparison': None, 'refuted': False, 'prior_confirmation': 'NONE_OBSERVED', 'reasons': [],
           'decisive_UNKNOWN': [], 'early_eligible': False, 'state': 'DATA_WAIT',
           'evidence': [demand['reference'], supply['reference']]+relation.get('references', []),
           'input_sha256': digest({'documents': documents, 'relationships': list(relationships), 'events': list(context_events)})}
    if relation['state'] != 'VERIFIED':
        out['state'] = 'PARTIAL_SCOPE_PAIR' if relation['state'] == 'PARTIAL' else 'UNLINKED_PAIR' if relation['state']=='UNLINKED' else 'INCOMPATIBLE_PAIR'
        out['reasons'].append(relation['reason'])
    applicable = True
    for key in ('region', 'qualification'):
        av, bv = value(demand, key), value(supply, key)
        if UNKNOWN in (av, bv) or av != bv:
            applicable = False; out['reasons'].append(key.upper()+'_APPLICABILITY_UNKNOWN')
    customer_verified = (value(demand, 'customer') != UNKNOWN and value(demand, 'customer') == value(supply, 'customer'))
    contract_verified = (value(demand, 'contract') != UNKNOWN and value(demand, 'contract') == value(supply, 'contract') and fact(supply, 'allocated'))
    if not customer_verified and not contract_verified:
        applicable = False; out['reasons'].append('CUSTOMER_OR_ALLOCATION_APPLICABILITY_UNKNOWN')
    out['scope_verified'] = relation['state'] == 'VERIFIED' and applicable
    if not fact(supply,'qualification_bound'):
        out['scope_verified']=False;out['reasons'].append('QUALIFIED_READINESS_BINDING_UNVERIFIED')
    if not out['independent']: out['reasons'].append('INDEPENDENT_ORIGINS_MISSING')
    if demand['role'] != 'DEMAND' or not fact(demand, 'committed'): out['reasons'].append('COMMITTED_DEMAND_MISSING')
    if supply['role'] != 'SUPPLY': out['reasons'].append('SUPPLY_EVIDENCE_MISSING')
    dw = relation.get('component_need_period') or demand['period']; sw = supply['period']
    identity = {k:value(demand,k) for k in ('manufacturer','model','product','specification','region','qualification')}
    identity['applicability'] = value(demand,'contract') if contract_verified else value(demand,'customer')
    if relation.get('kind') == 'REQUIRED_COMPONENT':identity.update(manufacturer=value(supply,'manufacturer'),model=value(supply,'model'),product=value(supply,'product'))
    out['target_id']='shadow-v2-'+digest(identity) if out['scope_verified'] else None
    out['target_name']=' / '.join(v for v in identity.values() if v!=UNKNOWN) if out['scope_verified'] else None
    out['provisional_pair_id']=out['pair_id'] if not out['scope_verified'] else None
    first_frozen_at=first_frozen_at or (previous_first or {}).get(out['target_id'])
    out['demand_window'], out['supply_window'] = dw, sw
    if not dw or not sw: out['reasons'].append('EXPLICIT_NEED_OR_READINESS_PERIOD_MISSING')
    elif dw['end'] < at.date().isoformat(): out['reasons'].append('FUTURE_DEMAND_MISSING')
    if dw and sw:
        if sw['start'] > dw['end']:
            out['comparison'] = 'QUALIFIED_READINESS_AFTER_NEED'
        elif (dw['start'], dw['end']) == (sw['start'], sw['end']) and relation.get('kind') != 'REQUIRED_COMPONENT':
            dq, sq = fact(demand, 'quantity'), fact(supply, 'quantity')
            basis = (fact(demand, 'basis'), fact(supply, 'basis'))
            if (dq is not None and sq is not None and fact(demand, 'unit') == fact(supply, 'unit')
                    and fact(demand, 'unit') and fact(supply, 'qualified') and contract_verified
                    and basis in (('total', 'total'), ('additional', 'unallocated'))):
                if dq > sq: out['comparison'] = 'COMPARABLE_QUANTITY_GAP'
                elif fact(supply, 'covers_all'): out['refuted'] = True
        if out['comparison'] is None and not out['refuted']: out['reasons'].append('TIMING_OR_QUANTITY_GAP_UNPROVEN')
    for e in context_events:
        validate_document(docs[e['document_id']], as_of); _validate_event(e, docs)
        related = relationship(demand, e, relationships, docs)
        if e['role'] == 'CONFIRMATION' and e['kind'] == 'ACTUAL':
            if related['state'] == 'INCOMPATIBLE': continue
            if related['state'] != 'VERIFIED':
                # A shared observed identifier is needed even for a possible match.
                if not any(value(demand,k)!=UNKNOWN and value(demand,k)==value(e,k) for k in ('model','contract','product')): continue
                if out['prior_confirmation']!='MISSED_EARLY_DETECTION':out['prior_confirmation'] = 'POSSIBLE_PRIOR_CONFIRMATION'
                out['evidence'].append(e['reference']); continue
            confirmation_applies=(value(demand,'region')==value(e,'region')!=UNKNOWN
                and (value(demand,'contract')==value(e,'contract')!=UNKNOWN or value(demand,'qualification')==value(e,'qualification')!=UNKNOWN))
            if not confirmation_applies:
                if out['prior_confirmation']!='MISSED_EARLY_DETECTION':out['prior_confirmation']='POSSIBLE_PRIOR_CONFIRMATION'
                out['evidence'].append(e['reference']);continue
            if value(demand,'region')!=UNKNOWN and value(e,'region')!=UNKNOWN and value(demand,'region')!=value(e,'region'):continue
            d = docs[e['document_id']]; first = clock(first_frozen_at or as_of)
            if d.get('publication_precision') == 'DATE':
                lo = datetime.combine(date.fromisoformat(d['published_at']), datetime.min.time(), timezone.utc); hi = lo+timedelta(days=1)
            elif d.get('published_at'):
                lo = hi = clock(d['published_at'])
            else:
                out['prior_confirmation'] = 'POSSIBLE_PRIOR_CONFIRMATION';out['evidence'].append(e['reference']);continue
            status = 'MISSED_EARLY_DETECTION' if hi <= first else 'CONFIRMED' if lo > first and first_frozen_at else 'POSSIBLE_PRIOR_CONFIRMATION'
            priority={'NONE_OBSERVED':0,'CONFIRMED':1,'POSSIBLE_PRIOR_CONFIRMATION':2,'MISSED_EARLY_DETECTION':3}
            if priority[status]>priority[out['prior_confirmation']]:out['prior_confirmation'] = status
            out['evidence'].append(e['reference'])
        if related['state'] != 'VERIFIED': continue
        # Refutation must apply to the same customer/contract and qualifications.
        same_applies = all(value(e,k)!=UNKNOWN and value(e,k)==value(demand,k) for k in ('region','qualification')) and (value(e,'customer')==value(demand,'customer')!=UNKNOWN or value(e,'contract')==value(demand,'contract')!=UNKNOWN)
        if not same_applies: continue
        # A second qualified, allocated source can disprove a late-facility gap
        # with directly comparable quantities, without the phrase "covers all".
        if (e['role']=='SUPPLY' and fact(e,'qualified') and fact(e,'qualification_bound')
                and fact(e,'allocated') and value(e,'contract')==value(demand,'contract')!=UNKNOWN
                and relation.get('kind')!='REQUIRED_COMPONENT' and dw and e['period']
                and (dw['start'],dw['end'])==(e['period']['start'],e['period']['end'])
                and fact(demand,'unit')==fact(e,'unit') and fact(e,'unit')
                and (fact(demand,'basis'),fact(e,'basis')) in (('total','total'),('additional','unallocated'))
                and fact(demand,'quantity') is not None and fact(e,'quantity') is not None
                and fact(e,'quantity')>=fact(demand,'quantity')):
            out['refuted']=True;out['evidence'].append(e['reference'])
        if (e['role']=='SUPPLY' and e['event_id']!=supply['event_id'] and fact(e,'qualification_bound')
                and e['period'] and sw and (e['period']['start'],e['period']['end'])!=(sw['start'],sw['end'])
                and value(e,'facility')==value(supply,'facility')!=UNKNOWN):
            out['reasons'].append('CONFLICTING_SAME_FACILITY_READINESS');out['evidence'].append(e['reference'])
        if e['role'] == 'RELIEF' and fact(e,'qualified') and fact(e,'qualification_bound') and fact(e,'covers_all') and e['period'] and dw and e['period']['end'] <= dw['start']:
            out['refuted'] = True;out['evidence'].append(e['reference'])
        elif e['role'] == 'DEMAND_CHANGE' and e['kind']=='ADVERSE':
            if re.search(r'\b(?:cancelled|canceled)\b',e['reference']['quote'],re.I):out['refuted']=True
            elif e['period'] and sw and e['period']['start'] >= sw['end']:out['refuted']=True
            else:out['reasons'].append('DEMAND_CHANGE_REQUIRES_RECONCILIATION')
            out['evidence'].append(e['reference'])
    out['decisive_UNKNOWN'] = [k for k in ('total_demand','total_supply') if fact(demand if k=='total_demand' else supply,'quantity') is None or fact(demand if k=='total_demand' else supply,'basis')!='total']
    if out['prior_confirmation'] == 'MISSED_EARLY_DETECTION':out['state']='MISSED_EARLY_DETECTION'
    elif out['prior_confirmation'] == 'POSSIBLE_PRIOR_CONFIRMATION':out['state']='DATA_WAIT';out['reasons'].append('POSSIBLE_PRIOR_CONFIRMATION')
    elif out['refuted']:out['state']='REFUTED'
    elif out['prior_confirmation']=='CONFIRMED':out['state']='CONFIRMED'
    elif out['scope_verified'] and not out['reasons']:
        out['state']='EARLY_FORECAST_CANDIDATE';out['early_eligible']=True
    out=stamp_export(out)
    out['decision_sha256']=digest(out)
    return out


def relation_edges(documents):
    edges=[]
    for d in documents:
        for m in re.finditer(r'[^\n]+',d['body']):
            q=m.group()
            if re.search(r'\b(?:also known as|identical to|same model as)\b',q,re.I):edges.append({'kind':'EXPLICIT_ALIAS','reference':reference(d,m.start(),m.end())})
            if re.search(r'\b(?:is required for|is a required component of)\b',q,re.I):
                pm=re.search(r'\b(?:component needed|required)\s+(?:on|by|in|during)\s+('+PERIOD+r')\b',q,re.I)
                if pm:edges.append({'kind':'REQUIRED_COMPONENT','reference':reference(d,m.start(),m.end()),'component_need_period':{'text':pm[1],'reference':reference(d,m.start()+pm.start(1),m.start()+pm.end(1))}})
    return edges


def synthesize(documents, *, as_of, previous_first=None):
    valid=[];rejected=[]
    for d in documents:
        try:validate_document(d,as_of);valid.append(d)
        except (KeyError,ValueError,TypeError) as exc:rejected.append({'document_id':d.get('document_id'),'reason':str(exc)})
    if len({d['document_id'] for d in valid})!=len(valid):raise ValueError('DUPLICATE_DOCUMENT_IDS')
    events=[e for d in valid for e in extract(d)];edges=relation_edges(valid);results=[]
    for demand in (e for e in events if e['role']=='DEMAND'):
        for supply in (e for e in events if e['role']=='SUPPLY'):
            results.append(evaluate_pair_v2(demand,supply,documents=valid,as_of=as_of,relationships=edges,context_events=events,previous_first=previous_first))
    return stamp_export({'version':VERSION,'mode':'SHADOW','as_of':as_of,'documents':valid,'events':events,'relationships':edges,'evaluations':results,'document_rejections':rejected})


def counters(prepared):
    evaluations=prepared['evaluations']
    return {'documents_input':len(prepared['documents'])+len(prepared['document_rejections']),
            'documents_valid':len(prepared['documents']),'documents_rejected':len(prepared['document_rejections']),
            'events':len(prepared['events']),'pairs_total':len(evaluations),
            'relationship_verified':sum(e['relation']['state']=='VERIFIED' for e in evaluations),
            'independent_verified':sum(e['relation']['state']=='VERIFIED' and e['independent'] for e in evaluations),
            'scope_verified':sum(e['relation']['state']=='VERIFIED' and e['independent'] and e['scope_verified'] for e in evaluations),
            'gap_verified':sum(e['relation']['state']=='VERIFIED' and e['independent'] and e['scope_verified'] and bool(e['comparison']) for e in evaluations),
            'early_pairs':sum(e['early_eligible'] for e in evaluations),
            'early_targets':len({e['target_id'] for e in evaluations if e['early_eligible']}),
            'states':{s:sum(e['state']==s for e in evaluations) for s in sorted({e['state'] for e in evaluations})}}
