"""Literal date/quantity facts with bounds, roles and unresolved anchor reasons.

Calendar bounds are ranges, never fabricated exact need/readiness dates. This
reader does not modify the hash-protected engines or their decision contracts.
"""
import calendar
from datetime import date
import re

from .precursor_scope_reader import reference

VERSION = 'source-temporal-reader-2'
UNKNOWN = 'UNKNOWN'
MONTHS = 'January February March April May June July August September October November December'.split()
MONTH = '|'.join(MONTHS)
EXPR = re.compile(r'\b(?:20\d{2}-\d{2}-\d{2}|(?:'+MONTH+r')\s+(?:\d{1,2},?\s+)?20\d{2}|(?:first|second) half (?:of )?20\d{2}|(?:first|second|third|fourth) quarter (?:of )?20\d{2}|(?:early|late|end of|by the end of)\s+20\d{2}|(?:Q[1-4]|H[12])\s*20\d{2}|20\d{2}\s*(?:Q[1-4]|H[12]|년\s*(?:상반기|하반기|[1-4]분기|말|초))|20\d{2}(?:\s*[–~-]\s*20\d{2})?|(?:\d+|eighteen|twenty-four)\s+months?\s+(?:after|from|until|to)|(?:after|following)\s+(?:customer\s+)?(?:qualification|certification)(?:\s+completion)?)\b', re.I)
KOREAN = re.compile(r'20\d{2}년\s*(?:상반기|하반기|[1-4]분기|말까지|말|초|\d{1,2}월(?:\s*\d{1,2}일)?)|(?:발주|계약\s*(?:발효|체결))\s*후\s*\d+개월|공급\s*준비까지\s*\d+개월|고객\s*인증\s*완료\s*후')
RELATIVE = re.compile(r'\b(?:within|over the next|in)\s+(?:\d+|eighteen|twenty-four)\s+months?\b',re.I)
AMOUNT = re.compile(r'(?<![\w$€£.,-])(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion)?\s*((?:(?:qualified|good)\s+)?(?:MW|GW|MWh|GWh|kg|tonnes|tons|units|cells|wafers|dies|slots|pieces|lasers|isolators|turbines|machines|systems|percent|%)(?:\s*(?:/\s*(?:hour|day|month|year)|per\s+(?:hour|day|month|year)|annually))?)(?!\w)', re.I)


def bounds(text, anchor=None):
    raw = text; t = text.strip(); result = {'text': raw, 'precision': UNKNOWN, 'start': UNKNOWN, 'end': UNKNOWN}
    exact = re.fullmatch(r'20\d{2}-\d{2}-\d{2}', t)
    if exact:
        try: value = date.fromisoformat(t).isoformat()
        except ValueError: return {**result, 'unknown_reason': 'INVALID_CALENDAR_DATE'}
        return {**result, 'precision':'DATE', 'start':value, 'end':value}
    y = re.search(r'20\d{2}', t)
    if not y:
        duration = re.search(r'(\d+|eighteen|twenty-four)\s*(?:months?|개월)', t, re.I)
        if duration:
            months = {'eighteen':18,'twenty-four':24}.get(duration[1].lower()) or int(duration[1])
            result.update(precision='RELATIVE_DURATION', months=months)
            if anchor and anchor.get('precision') == 'DATE' and anchor.get('reference'):
                d = date.fromisoformat(anchor['start']); n = d.year*12+d.month-1+months
                dt = date(n//12,n%12+1,min(d.day,calendar.monthrange(n//12,n%12+1)[1])).isoformat()
                result.update(start=dt,end=dt,anchor=anchor)
                if re.search(r'within|over the next',t,re.I):result.update(precision='RELATIVE_WINDOW',start=anchor['start'])
            else: result['unknown_reason'] = 'REFERENCE_EVENT_DATE_NOT_VERIFIED'
        else: result.update(precision='CONDITIONAL',unknown_reason='QUALIFICATION_COMPLETION_DATE_UNKNOWN')
        return result
    year = int(y[0]); first, last = 1,12; precision = 'YEAR'
    half = re.search(r'H([12])|\b(first|second) half|(?:상반기|하반기)', t, re.I)
    quarter = re.search(r'Q([1-4])|([1-4])분기|\b(first|second|third|fourth) quarter', t, re.I)
    month = next((i+1 for i,m in enumerate(MONTHS) if re.search(r'\b'+m+r'\b',t,re.I)), None)
    korean_month=re.search(r'년\s*(\d{1,2})월(?:\s*(\d{1,2})일)?',t)
    if korean_month:
        month=int(korean_month[1])
        if not 1<=month<=12:return {**result,'unknown_reason':'INVALID_CALENDAR_DATE'}
        if korean_month[2]:
            try:value=date(year,month,int(korean_month[2])).isoformat()
            except ValueError:return {**result,'unknown_reason':'INVALID_CALENDAR_DATE'}
            return {**result,'precision':'DATE','start':value,'end':value}
    if half:
        first = 1 if (half[1]=='1' or (half[2] or '').lower()=='first' or half[0]=='상반기') else 7; last=first+5; precision='HALF'
    elif quarter:
        number=int(quarter[1] or quarter[2]) if quarter[1] or quarter[2] else ('first','second','third','fourth').index(quarter[3].lower())+1
        first=(number-1)*3+1;last=first+2;precision='QUARTER'
    elif month:
        first=last=month;precision='MONTH'
        day = re.search(r'\b(?:'+MONTH+r')\s+(\d{1,2}),?\s+20\d{2}', t,re.I)
        if day:
            try: value=date(year,month,int(day[1])).isoformat()
            except ValueError:return {**result,'unknown_reason':'INVALID_CALENDAR_DATE'}
            return {**result,'precision':'DATE','start':value,'end':value}
    elif re.search(r'early|late|end of|말|초',t,re.I):
        return {**result,'precision':'QUALITATIVE_YEAR','start':f'{year}-01-01','end':f'{year}-12-31',
                'qualifier':t[:y.start()]+t[y.end():], 'unknown_reason':'QUALITATIVE_BOUND_NOT_AN_EXACT_DATE'}
    years = re.findall(r'20\d{2}',t); endyear = int(years[-1])
    if endyear<year:return {**result,'unknown_reason':'REVERSED_INTERVAL'}
    return {**result,'precision':precision if len(years)==1 else 'YEAR_RANGE',
            'start':date(year,first,1).isoformat(),'end':date(endyear,last,calendar.monthrange(endyear,last)[1]).isoformat()}


def _kind(q, start, end):
    # Verb proximity prevents a contract date from becoming an availability date.
    before=q[max(0,start-110):start].lower();after=q[end:min(len(q),end+60)].lower()
    clause=re.split(r'[.;]',before)[-1]
    rules = [
        ('DEMAND_CANCELLATION',r'cancel|postpon|defer|demand.{0,25}(?:declin|reduc)'),
        ('QUALIFICATION',r'qualification|certification|customer approval'),
        ('SUPPLY_READY',r'commercial.{0,20}(?:operation|production)|commission|ready|available|start.{0,20}production|production.{0,20}(?:begin|start)|(?:conversion|construction|expansion).{0,30}(?:complet|finish)|complet.{0,30}(?:conversion|construction|expansion)'),
        ('DEMAND_NEED',r'needed|required|deliver|shipment|due'),
        ('CONTRACT_DATE',r'sign|award|contract.{0,25}(?:date|start|effective)|agreement.{0,25}(?:date|start|effective)'),
        ('CAPEX_DEPLOYMENT',r'capex|invest|deploy|construction'),
        ('DEMAND_FORECAST',r'forecast|expect|project|anticipat'),
    ]
    for kind,pattern in rules:
        if re.search(pattern,clause):return kind
    if re.search(r'(?:qualification|certification)',after):return 'QUALIFICATION'
    return 'UNATTRIBUTED_PERIOD'


def extract(doc, event):
    q=event['source_quote'];off=event['locator']['start'];periods=[];amounts=[]
    matches=list(EXPR.finditer(q))+list(KOREAN.finditer(q))+list(RELATIVE.finditer(q))
    # Keep the longest matching expression, never a convenient inner year.
    chosen=[]
    for m in sorted(matches,key=lambda m:(m.start(),-len(m[0]))):
        if any(m.start()<p.end() and m.end()>p.start() for p in chosen):continue
        chosen.append(m)
    for m in chosen:
        periods.append({**bounds(m[0]),'fact_kind':_kind(q,m.start(),m.end()),'reference':reference(doc,off+m.start(),off+m.end())})
    # A relative duration can only use a verified, same-clause named anchor.
    for p in periods:
        if p['precision']=='RELATIVE_DURATION':
            anchors=[x for x in periods if x['fact_kind']=='CONTRACT_DATE' and x['precision']=='DATE']
            if len(anchors)==1 and re.search(r'after (?:the )?(?:contract|order)|(?:발주|계약\s*(?:발효|체결))\s*후',q,re.I):
                p.update(bounds(p['text'],anchors[0]))
    for m in AMOUNT.finditer(q):
        value=float(m[1].replace(',',''));value*= {'million':1e6,'billion':1e9}.get((m[2] or '').lower(),1)
        clause_start=q.rfind(';',0,m.start())+1
        clause_end=q.find(';',m.end());clause_end=len(q) if clause_end<0 else clause_end
        context=q[clause_start:clause_end]
        rate=bool(re.search(r'/|per |annually',m[3],re.I))
        kind='PHYSICAL_AMOUNT'
        if re.search(r'nameplate|nominal|design capacity|planned capacity|expected capacity|capacity expansion',context,re.I):kind='NOMINAL_OR_PLANNED_CAPACITY'
        elif re.search(r'\b(?:unallocated|unreserved|unbooked)\b',context,re.I):kind='UNRESERVED_CAPACITY'
        elif re.search(r'\b(?:reserved|allocated|booked)\b',context,re.I):kind='CUSTOMER_ALLOCATION'
        elif re.search(r'qualified.{0,30}(?:capacity|output|supply)',context,re.I) and not re.search(r'not.{0,10}qualified|pending qualification|expects? to|will be qualified',context,re.I):kind='QUALIFIED_OUTPUT'
        elif event['role']=='DEMAND':kind='FORECAST_QUANTITY' if re.search(r'forecast|expect|potential',context,re.I) else 'ORDER_QUANTITY' if event.get('demand_status')=='COMMITTED' else 'UNCONFIRMED_QUANTITY'
        if m[3].lower() in ('%','percent'):kind='YIELD_OR_PERCENT_REQUIRES_ATTRIBUTION'
        associated=[p for p in periods if off+clause_start<=p['reference']['locator']['start']<off+clause_end and p['fact_kind']!='CONTRACT_DATE']
        amounts.append({'value':int(value) if value.is_integer() else value,'unit':m[3], 'rate':rate,'fact_kind':kind,
                       'qualification_status':'PENDING' if re.search(r'not(?: yet)? qualified|pending qualification|before qualification',context,re.I) else 'SOURCE_ASSERTED' if kind=='QUALIFIED_OUTPUT' else UNKNOWN,
                       'coverage':'COMPLETE' if re.search(r'\b(?:total|all|entire)\b',context,re.I) else 'UNRESERVED' if kind=='UNRESERVED_CAPACITY' else 'OBSERVED_NOT_TOTAL',
                       'reference':reference(doc,off+m.start(),off+m.end()),'period':associated[0] if len(associated)==1 else UNKNOWN})
    financial=[reference(doc,off+m.start(),off+m.end()) for m in re.finditer(r'[$€£]\s*\d[\d,.]*(?:\s*(?:million|billion))?',q,re.I)]
    relief=[]
    for kind,pattern in [('DEMAND_CANCEL_OR_DELAY',r'cancel\w*|postpon\w*|defer\w*'),('QUALIFIED_SUBSTITUTE',r'(?:qualified|certified) (?:substitute|alternative supplier)'),('UNVERIFIED_SUBSTITUTE',r'(?<!qualified )(?<!certified )alternative supplier'),('COMPLETED_CAPACITY',r'(?:already|now) (?:operating|in production)|commercial operations began'),('PENDING_CAPACITY',r'under construction|planned capacity|qualification|commissioning'),('INVENTORY',r'\binventor(?:y|ies)\b'),('PRODUCTIVITY',r'(?:improv|increas).{0,25}(?:yield|throughput|productivity)'),('DESIGN_CHANGE',r'redesign|design change')]:
        if re.search(pattern,q,re.I):relief.append({'kind':kind,'reference':reference(doc,off,off+len(q))})
    return {'version':VERSION,'periods':periods,'quantities':amounts,'financial_amounts_not_output':financial,'relief':relief,
            'unknown_reasons':sorted({p['unknown_reason'] for p in periods if p.get('unknown_reason')} | ({'NO_SOURCE_PERIOD'} if not periods else set()) | ({'NO_PHYSICAL_QUANTITY'} if not amounts else set()))}


def compare(demand, supply):
    """Only source-specific need/readiness facts in identical physical scopes."""
    def scope(event):return {k:(' '.join(v['value'].casefold().split()) if isinstance(v,dict) else v) for k,v in event.get('scope',{}).items()}
    if scope(demand) != scope(supply):return {'state':'UNKNOWN','reason':'SCOPE_MISMATCH'}
    dt=demand.get('temporal_facts',{});st=supply.get('temporal_facts',{})
    if any(r['kind']=='DEMAND_CANCEL_OR_DELAY' for r in dt.get('relief',[])+st.get('relief',[])):
        return {'state':'RECONCILE_RELIEF','reason':'DEMAND_CANCEL_OR_DELAY'}
    if any(r['kind'] in ('QUALIFIED_SUBSTITUTE','COMPLETED_CAPACITY') for r in st.get('relief',[])):
        return {'state':'RECONCILE_RELIEF','reason':'COMPLETED_OR_SUBSTITUTE_CAPACITY_REQUIRES_COVERAGE'}
    needs=[p for p in dt.get('periods',[]) if p['fact_kind']=='DEMAND_NEED']
    ready=[p for p in st.get('periods',[]) if p['fact_kind'] in ('SUPPLY_READY','QUALIFICATION')]
    if len(needs)!=1 or len(ready)!=1:return {'state':'UNKNOWN','reason':'NEED_OR_QUALIFIED_READINESS_NOT_UNIQUE'}
    d,s=needs[0],ready[0]
    if s['fact_kind']=='SUPPLY_READY' and not (supply.get('qualified') or re.search(r'\bqualified\b',supply.get('source_quote',''),re.I)):
        return {'state':'UNKNOWN','reason':'QUALIFIED_READINESS_NOT_ESTABLISHED'}
    dq,sq=dt.get('quantities',[]),st.get('quantities',[])
    if dq and sq and {(x['unit'].casefold(),x['rate']) for x in dq}!={(x['unit'].casefold(),x['rate']) for x in sq}:
        return {'state':'UNKNOWN','reason':'PHYSICAL_UNIT_OR_RATE_MISMATCH'}
    if UNKNOWN in (d['start'],d['end'],s['start'],s['end']):return {'state':'UNKNOWN','reason':'DATE_ANCHOR_UNKNOWN'}
    if d.get('unknown_reason') or s.get('unknown_reason'):return {'state':'UNKNOWN','reason':'QUALITATIVE_TIME_BOUND'}
    usable_d=[q for q in dq if q.get('fact_kind')=='ORDER_QUANTITY' and isinstance(q.get('period'),dict)]
    usable_s=[q for q in sq if q.get('fact_kind') in ('QUALIFIED_OUTPUT','UNRESERVED_CAPACITY') and q.get('qualification_status')!='PENDING' and isinstance(q.get('period'),dict)]
    if len(usable_d)==len(usable_s)==1:
        a,b=usable_d[0],usable_s[0]
        same_period=(a['period']['start'],a['period']['end'])==(b['period']['start'],b['period']['end'])
        covered=b.get('coverage') in ('COMPLETE','UNRESERVED') and (supply.get('qualified') or b.get('qualification_status')=='SOURCE_ASSERTED')
        if same_period and covered and a['value']>b['value']:
            return {'state':'POSSIBLE_QUANTITY_GAP','need':d,'readiness':s,'demand':a,'supply':b,'gap':a['value']-b['value'],'unit':a['unit']}
    if s['start']>d['end']:return {'state':'POSSIBLE_TIMING_GAP','need':d,'readiness':s}
    if s['end']<d['start']:return {'state':'SUPPLY_BEFORE_NEED','reason':'READINESS_PRECEDES_NEED_NOT_A_SHORTAGE','need':d,'readiness':s}
    return {'state':'UNKNOWN','reason':'OVERLAPPING_WINDOWS_DO_NOT_PROVE_LAG','need':d,'readiness':s}
