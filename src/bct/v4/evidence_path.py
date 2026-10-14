"""Disabled research alternative: located evidence, not pre-discovered parser events.

Source location, relation acceptance and S stage are deliberately separate.
Oracle review is explicit input, never attributed to automatic extraction.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from .store import sha, encode
from bct.objective_lock import stamp_export

VERSION = 'bct-located-evidence-1'
ROLES = {'DEMAND_INCREASE','SUPPLY_INCREASE','SUPPLY_DECREASE','SUPPLY_DELAY','RELIEF'}
ACTUALITY = {'ACTUAL','PLAN','FORECAST','NEGATED','UNKNOWN'}
TARGET = ('product','specification','region','customer_group','supply_pool')
NUMBER_WORDS = dict(zip(('zero','one','two','three','four','five','six','seven','eight','nine','ten'),map(str,range(11))))


def reference(doc, ref, within=None):
    if not isinstance(ref,dict): raise ValueError('REFERENCE_REQUIRED')
    a,b = ref.get('start'),ref.get('end')
    if type(a) is not int or type(b) is not int or not 0<=a<b<=len(doc['body']): raise ValueError('POSITION_REQUIRED')
    if doc['body'][a:b]!=ref.get('quote'): raise ValueError('EXACT_SOURCE_MISMATCH')
    if within and not within['start']<=a<b<=within['end']: raise ValueError('OUTSIDE_EVENT_CONTEXT')
    return {'document_id':doc['document_id'],'body_sha256':doc['body_sha256'],
            'origin_url':doc['origin_url'],'published_at':doc.get('published_at','UNKNOWN'),
            'acquired_at':doc.get('acquired_at','UNKNOWN'),**deepcopy(ref)}


def value(doc, field, within):
    if field is None:return None
    r=reference(doc,field['reference'],within)
    if field['value']!=r['quote']:raise ValueError('FIELD_MUST_BE_LOCATED_LITERAL')
    return {'surface':field['value'],'normalized':' '.join(field['value'].split()).casefold(),'reference':r}


def normalize_quantity(surface):
    text=surface.strip().casefold()
    rule='NUMBER_WORD' if text in NUMBER_WORDS else 'DECIMAL_LITERAL'
    try:
        number=Decimal(NUMBER_WORDS.get(text,text.replace(',','')))
        if not number.is_finite() or number<0:raise ValueError('NON_PHYSICAL_QUANTITY')
        return {'surface':surface,'normalized':str(number),'rule':rule}
    except InvalidOperation: return {'surface':surface,'normalized':None,'rule':'UNKNOWN_NO_GUESS'}


def relation_check(product, context, role, actuality):
    """Broad verbs/object binding; no product-name or legacy event whitelist."""
    name=product['surface'];escaped=re.escape(name);text=context['quote']
    if re.search(r'\b(?:project|contract|agreement|grant|funding|shares?|services?|software)\b',name,re.I):
        return False,'NON_PHYSICAL_OR_CONTRACT_IDENTITY'
    if not re.search(r'(?<![\w-])'+escaped+r'(?![\w-])',text):return False,'PRODUCT_TOKEN_BOUNDARY'
    # Preserve actual/plan/forecast/negative markers as claims, never upgrade them.
    relevant=[c for c in re.split(r'[.;\n]',text) if name in c or re.match(r'^\s*(?:however,?\s+)?(?:this|the) order\b',c,re.I)]
    neg=any(re.search(r'\b(?:did not|has not|no longer|not ordered|cancelled|canceled)\b',c,re.I) for c in relevant)
    plan=bool(re.search(r'\b(?:plans?|planned|will|intends?|proposed|expected|forecast|may|could)\b',text,re.I))
    if actuality=='ACTUAL' and neg and role!='RELIEF':return False,'NEGATION_CONFLICT'
    if role=='DEMAND_INCREASE':
        ordered=r'(?:\b(?:ordered|purchased|orders?\s+for|orders?\s+of|contract\s+(?:for|to supply))\s+)(?P<object>[^.;\n]{0,140}?)'+escaped+r'(?![\w-])'
        matches=list(re.finditer(ordered,text,re.I))
        expected_end=product['reference']['end']-context['start']
        matches=[m for m in matches if m.end()==expected_end]
        matches=[m for m in matches if not re.search(r'\b(?:for|to|with|from|powering|supporting|enabling|manufacture|produce|production of|used to|used for|maintenance|services?|shares?|bonds?|securities|investment|funding|projects?)\b',m['object'],re.I)]
        if not matches:return False,'ORDER_OBJECT_RELATION_UNPROVEN'
        # Future output in a separate sentence does not nullify a literal actual order.
        sentence=text[max(0,text.rfind('.',0,matches[0].start())+1):matches[0].end()]
        if actuality=='ACTUAL' and re.search(r'\b(?:will|plans?|expects?|may|could|not)\b',sentence,re.I):return False,'ORDER_COMMITMENT_UNPROVEN'
        return True,'LITERAL_ORDERED_OBJECT'
    patterns={
        'SUPPLY_INCREASE':r'\b(?:production|capacity|supply)\b.{0,60}\b(?:increased|expanded|rose|added)\b|\b(?:deliver(?:ed|s)?|provid(?:e|ed|es)|commissioned|opened|started production|entered operation)\b',
        'SUPPLY_DECREASE':r'\b(?:production|supply|capacity|plant|facility|retir)\w*\b.*\b(?:decreased|declined|reduced|closed|retired|shut)\w*\b|\b(?:retired|closed|reduced)\b',
        'SUPPLY_DELAY':r'\b(?:delivery|production|completion|qualification|lead time)\w*\b.*\b(?:delayed|postponed|lengthened)\b',
        'RELIEF':r'\b(?:surplus|shortened|eased|ended|no longer delayed|alternative supply|available capacity)\b|\binventor(?:y|ies)\b.{0,60}\bincreased\b'}
    if role not in patterns or not re.search(patterns[role],text,re.I|re.S):return False,'RELATION_NOT_ESTABLISHED'
    # The directional predicate must share a clause with the product.
    clauses=re.split(r'[.;\n]|\b(?:but|while|whereas)\b',text,flags=re.I)
    if not any(name in clause and re.search(patterns[role],clause,re.I) for clause in clauses):
        return False,'OTHER_PRODUCT_PREDICATE_NOT_TRANSFERABLE'
    if role=='SUPPLY_INCREASE' and re.search(r'\b(?:grant|funding|memorandum|MoU|alliance|partnership)\b',text,re.I):return False,'FUNDING_OR_ALLIANCE_NOT_CAPACITY'
    if actuality=='ACTUAL' and plan:return False,'PLANNED_SUPPLY_NOT_AVAILABLE'
    return True,'SOURCE_VERB_AND_LITERAL_OBJECT_RESEARCH_LIMITED'


def accept(doc, proposal, *, reviewed=False):
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('BODY_HASH_MISMATCH')
    context=reference(doc,proposal['reference'])
    product=value(doc,proposal['product'],context)
    if not product:raise ValueError('PRODUCT_REQUIRED')
    record={'id':sha([VERSION,doc['document_id'],context,proposal]),'version':VERSION,
            'original_proposal':deepcopy(proposal),'context':context,'product':product,
            'discovery_status':'SOURCE_LOCATED','meaning_status':'UNKNOWN','event_status':'DISCOVERY_ONLY',
            'role':proposal.get('role','UNKNOWN'),'actuality':proposal.get('actuality','UNKNOWN'),
            'target':{k:None for k in TARGET},'fields':{},'s_stage':'UNKNOWN','research_only':True}
    record['target']['product']=product
    for k,f in proposal.get('fields',{}).items():
        if f is not None:
            parsed=value(doc,f,context);record['fields'][k]=parsed
            if k in TARGET:record['target'][k]=parsed
    if 'quantity'in record['fields']:
        record['quantity_conversion']=normalize_quantity(record['fields']['quantity']['surface'])
    role,actuality=record['role'],record['actuality']
    if role not in ROLES:return record
    if actuality not in ACTUALITY:raise ValueError('INVALID_ACTUALITY')
    if reviewed:
        review=proposal.get('independent_review')or{}
        if review.get('type')!='SOURCE_ONLY_AI' or review.get('exposed_to_target_outputs')is not False:
            raise ValueError('ORACLE_REQUIRES_SEPARATE_SOURCE_REVIEW')
        record['meaning_status']='SOURCE_ONLY_AI_REVIEWED_NOT_HUMAN';ok,reason=True,'ORACLE_INJECTION_NOT_AUTOMATIC_DISCOVERY'
    else:
        ok,reason=relation_check(product,context,role,actuality)
        record['meaning_status']='LIMITED_RELATION_CHECK_PASS' if ok else 'RELATION_HELD'
    record['relation_check']=reason
    if ok:
        record['event_status']='ADOPTED_RESEARCH_EVENT'
        if actuality=='ACTUAL' and role in ('DEMAND_INCREASE','SUPPLY_DECREASE','SUPPLY_DELAY'):
            record['s_stage']='S1'
            # Missing quantities do not erase orders. S2 needs all five literal fields and time.
            if reviewed and all(record['target'].values()) and record['fields'].get('need_time'):
                record['s_stage']='S2'
    return record


def target_key(record):
    return tuple(record['target'][k]['normalized'] if record['target'][k] else None for k in TARGET)


def analyze(documents, proposals, *, enabled=False, reviewed=False):
    docs={d['document_id']:d for d in documents};records=[];held=[]
    if enabled:
        for did,items in proposals.items():
            for index,p in enumerate(items):
                try:records.append(accept(docs[did],p,reviewed=reviewed))
                except (ValueError,KeyError,TypeError)as e:held.append({'document_id':did,'index':index,'reason':str(e)})
    records=list({r['id']:r for r in records}.values());pairs=[]
    for d in records:
        if d['event_status']!='ADOPTED_RESEARCH_EVENT' or d['role']!='DEMAND_INCREASE' or d['actuality']!='ACTUAL':continue
        for s in records:
            if s['event_status']!='ADOPTED_RESEARCH_EVENT' or s['role']not in ('SUPPLY_DECREASE','SUPPLY_DELAY','SUPPLY_INCREASE'):continue
            key=target_key(d)
            if not all(key) or key!=target_key(s):continue
            if d['context']['document_id']==s['context']['document_id']:continue
            dd,sd=docs[d['context']['document_id']],docs[s['context']['document_id']]
            if dd.get('origin_publisher')==sd.get('origin_publisher')or dd.get('origin_id')==sd.get('origin_id'):continue
            period=d['fields'].get('need_time');ready=s['fields'].get('ready_time')
            if not period or not ready or period['normalized']!=ready['normalized']:continue
            relief=[r['id']for r in records if r['role']=='RELIEF'and r['event_status']=='ADOPTED_RESEARCH_EVENT'and target_key(r)==key]
            pairs.append({'demand':d['id'],'supply':s['id'],'target':key,'related_relief':relief,'s_stage':'UNKNOWN',
                          'reason':'INDEPENDENT_SCOPED_PAIR; TOTAL_QUALIFIED_SUPPLY_AND_RESIDUAL_DEMAND_UNKNOWN'})
    return stamp_export({'version':VERSION,'enabled':enabled,'operational_integration_enabled':False,
       'records':records,'held':held,'pairs':pairs,'candidates':[],'s_stage':'UNKNOWN','forecast_performance':'NOT_RUN',
       'counts':{'discoveries':len(records),'events':sum(r['event_status']=='ADOPTED_RESEARCH_EVENT'for r in records),
       'S1':len({target_key(r)for r in records if r['s_stage']=='S1'}),'S2':len({target_key(r)for r in records if r['s_stage']=='S2'}),'S3':0}})


def save(ledger,documents,proposals,*,enabled=False,reviewed=False):
    run_id='located-'+sha([VERSION,documents,proposals,enabled,reviewed])
    previous=ledger.db.execute('SELECT payload FROM runs WHERE id=?',(run_id,)).fetchone()
    if previous:
        import json
        return json.loads(previous[0])
    for doc in documents:ledger.capture(doc,reading={'original_proposal':proposals.get(doc['document_id']),
                                                'origin':'ORACLE'if reviewed else'MODEL_OR_SOURCE'})
    result=analyze(documents,proposals,enabled=enabled,reviewed=reviewed)
    return ledger.save_run(run_id,result,'BACKFILL')
