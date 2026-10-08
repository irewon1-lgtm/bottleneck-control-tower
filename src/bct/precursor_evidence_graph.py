"""Auditable multi-document scope resolution and adapter to unchanged EARLY.

Original documents/events are never rewritten. A shared commodity, issuer or
region is not a join key. Each connected edge has literal contract/project or
namespaced model evidence; conflicts invalidate the join instead of being voted
away. Graph metrics, BACKFILL and LIVE findings are separate.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import re

from . import precursor_scope_reader as reader, precursor_temporal as temporal
from . import forecast_discovery as strict, early_forecast as early
from . import precursor_source_search as source_search
from .objective_lock import stamp_export

VERSION = 'source-evidence-graph-1'
FIELDS = reader.FIELDS
UNKNOWN = 'UNKNOWN'


def norm(value):
    return ' '.join(value.casefold().split())


def validate_reference(reference, documents):
    d=documents[reference['document_id']]
    loc=reference['locator']
    if (reference['body_sha256']!=d['body_sha256'] or reference['source_quote']!=early._quote(d,loc)
        or any(reference.get(k)!=d.get(k) for k in ('origin_url','origin_publisher','published_at','acquired_at'))):
        raise ValueError('GRAPH_SOURCE_REFERENCE_MISMATCH')
    return True


def observations(document):
    lines,_=reader.allowed_lines(document)
    out=[]
    for line in reader.sentences(document,lines):
        products=reader._products(document,line);p=reader.bound_product(line,products)
        fields=reader._attributes(document,line,p)
        customer_definition=bool(re.match(r'^(?:This|The) customer is\b',line['quote']))
        if customer_definition:fields={k:f for k,f in fields.items() if k=='customer_group'};products=[];p=None
        if not p:fields.pop('product',None)
        if len({reader.product_key(f['value']) for f in products})>1 and not p:
            fields={};conflict='MULTIPLE_PRODUCTS_NO_EXPLICIT_BINDING'
        else:conflict=None
        anchors=[]
        for token in reader.named_anchors(line['quote']):
            m=re.search(re.escape(token),line['quote'])
            anchors.append({'kind':'CONTRACT' if token.lower().startswith('contract ') else 'PROJECT_OR_FACILITY',
                            'key':norm(token), 'reference':reader.reference(document,line['start']+m.start(),line['start']+m.end())})
        ref=reader.reference(document,line['start'],line['end'])
        relations=[]
        for pattern in (r'\b(?:manufactured|produced|supplied) by\s+('+reader.PARTY+r')(?=[,.;]|\s+(?:for|under|in|at)\b)',
                        r'\b('+reader.PARTY+r')\s+(?:makes|manufactures|produces|supplies)\b'):
            for m in re.finditer(pattern,line['quote']):
                relations.append({'relationship':'PRODUCT_SUPPLIER','entity':reader.field(document,line['start']+m.start(1),line['start']+m.end(1)), 'reference':ref, 'qualified':False})
        if fields.get('supply_pool'):
            relations.append({'relationship':'QUALIFIED_OBSERVED_SUPPLIER','entity':fields['supply_pool'],'reference':ref,'qualified':True})
        if fields.get('customer_group'):
            relations.append({'relationship':'PRODUCT_CUSTOMER_OR_END_USE','entity':fields['customer_group'],'reference':ref,'qualified_supply_for_customer':'UNKNOWN'})
        if p and reader.NAMED_MODEL.fullmatch(p['value']):
            for rel in relations:
                if rel['relationship'] in ('PRODUCT_SUPPLIER','QUALIFIED_OBSERVED_SUPPLIER'):
                    anchors.append({'kind':'NAMESPACED_MODEL','key':'model:'+norm(p['value'])+'|supplier:'+norm(rel['entity']['value']), 'reference':ref})
        stage=[]
        for kind,pattern in [('PROCUREMENT',r'orders?|purchases?|procurement'),('QUALIFICATION_PENDING',r'pending qualification|before qualification|expects? to qualif'),('PRODUCTION',r'manufactur|production|produces?'),('SHIPMENT',r'shipment|deliver(?:y|ies)'),('CONSTRUCTION',r'under construction|commissioning')]:
            if re.search(pattern,line['quote'],re.I):stage.append({'kind':kind,'reference':ref})
        out.append({'observation_id':strict.digest([document['document_id'],line['start'],line['end']]),
                    'document_id':document['document_id'],'locator':ref['locator'],'source_quote':line['quote'],
                    'reference':ref,'fields':fields,'anchors':anchors,'relations':relations,'production_stages':stage,'blocking_reason':conflict})
    # Events can carry an exact within-document anaphor/explicit-label proof
    # established by the scope reader. Do not replace the raw observation.
    for event in document.get('retained_collection_events',[]):
        matching=next((o for o in out if o['locator']==event['locator']),None)
        if matching:
            matching['fields'].update(deepcopy(event['scope']))
            matching.setdefault('event_ids',[]).append(event['event_id'])
        else:
            out.append({'observation_id':strict.digest([document['document_id'],event['locator']]),
                        'document_id':document['document_id'],'locator':deepcopy(event['locator']),
                        'source_quote':event['source_quote'],'reference':reader.reference(document,**event['locator']),
                        'fields':deepcopy(event['scope']), 'anchors':[], 'event_ids':[event['event_id']],
                        'blocking_reason':event.get('scope_unknown_reason')})
    return out


def _conflicts(a,b):
    return [k for k in FIELDS if k in a['fields'] and k in b['fields'] and norm(a['fields'][k]['value'])!=norm(b['fields'][k]['value'])]


def join(a,b):
    if a.get('blocking_reason') or b.get('blocking_reason'):return None
    shared={x['key'] for x in a['anchors']} & {x['key'] for x in b['anchors']}
    if _conflicts(a,b):return None
    complete=all(k in a['fields'] and k in b['fields'] for k in FIELDS)
    if any(x['fields'].get('customer_group',{}).get('customer_identity_status') for x in (a,b)):complete=False
    if not shared and not complete:return None
    # Named anchor with no physical product on either side cannot create one.
    if not (a['fields'].get('product') or b['fields'].get('product')):return None
    return {'left':a['observation_id'],'right':b['observation_id'],
            'kind':'EXACT_NAMED_SOURCE_RELATION' if shared else 'EXACT_COMPLETE_PHYSICAL_SCOPE',
            'keys':sorted(shared),'references':[a['reference'],b['reference']], 'assertion':'SOURCE_BOUND_IDENTITY_LINK'}


def build(documents):
    docs={d['document_id']:d for d in documents};nodes=[];rejected=[]
    for d in documents:
        if hashlib.sha256(d['body'].encode()).hexdigest()!=d['body_sha256']:raise ValueError('GRAPH_BODY_HASH_MISMATCH')
        nodes.extend(observations(d))
    edges=[];adj={n['observation_id']:set() for n in nodes};byid={n['observation_id']:n for n in nodes}
    index={}
    for n in nodes:
        keys=[('anchor',a['key']) for a in n['anchors']]
        if all(k in n['fields'] for k in FIELDS):keys.append(('scope',tuple(norm(n['fields'][k]['value']) for k in FIELDS)))
        for key in keys:index.setdefault(key,[]).append(n)
    seen=set()
    for group in index.values():
        for i,a in enumerate(group):
            for b in group[i+1:]:
                pair=tuple(sorted([a['observation_id'],b['observation_id']]))
                if pair in seen:continue
                seen.add(pair)
                conflicts=_conflicts(a,b)
                if conflicts:rejected.append({'left':pair[0],'right':pair[1],'reason':'PHYSICAL_SCOPE_CONFLICT','fields':conflicts});continue
                edge=join(a,b)
                if edge:
                    edges.append(edge);adj[pair[0]].add(pair[1]);adj[pair[1]].add(pair[0])
    resolved=[]
    for n in nodes:
        reachable={n['observation_id']};front=[n['observation_id']]
        while front:
            for neighbor in adj[front.pop()]:
                if neighbor not in reachable:reachable.add(neighbor);front.append(neighbor)
        group=[byid[k] for k in sorted(reachable)];fields={};unknown={}
        for k in FIELDS:
            candidates=[x['fields'][k] for x in group if k in x['fields']]
            if len({norm(f['value']) for f in candidates})==1:
                fields[k]=deepcopy(candidates[0])
                fields[k]['support_references']=list({strict.digest(r):r for f in candidates for r in [f['reference'],*f.get('support_references',[])]}.values())
            else:unknown[k]='CONNECTED_COMPONENT_CONFLICT' if candidates else 'NO_SOURCE_BOUND_'+k.upper()
        proof=[e for e in edges if e['left'] in reachable and e['right'] in reachable]
        resolved.append({**n,'resolved_fields':fields,'unknowns':unknown,'connected_observations':sorted(reachable),'relationship_proofs':proof})
    references=0
    for n in resolved:
        validate_reference(n['reference'],docs);references+=1
        for f in n['resolved_fields'].values():
            for r in [f['reference'],*f.get('support_references',[])]:validate_reference(r,docs);references+=1
        for e in n['relationship_proofs']:
            for r in e['references']:validate_reference(r,docs);references+=1
    return {'version':VERSION,'observations':resolved,'edges':edges,'rejected_links':rejected,'reference_checks':references}


def _independent(d,s,documents):
    dd,sd=documents[d['document_id']],documents[s['document_id']]
    a={**dd,'excerpt_sha256':strict.digest(d['source_quote'])};b={**sd,'excerpt_sha256':strict.digest(s['source_quote'])}
    if not strict.independent(a,b):return False,'SAME_ORIGINAL_ISSUER_OR_BODY'
    if source_search.copied_body(dd,sd):return False,'DUPLICATE_OR_REPUBLICATION'
    common=set(reader.named_anchors(d['source_quote'])) & set(reader.named_anchors(s['source_quote']))
    if common and any(k.lower().startswith('contract ') for k in common):
        # Buyer and seller restating one order do not create two causal facts.
        if not re.search(r'production capacity|qualified capacity|qualification completes|commissioning|under construction|unreserved',s['source_quote'],re.I):
            return False,'SAME_CONTRACT_EVENT'
    return True,None


def analyze(documents,*,mode='BACKFILL',now=None,new_document_ids=None):
    if mode=='LIVE' and now is not None:raise ValueError('LIVE graph cannot backdate')
    at=strict.clock(now) if now else strict.clock(datetime.now().astimezone().isoformat())
    docs={d['document_id']:d for d in documents};graph=build(documents)
    obs={event_id:o for o in graph['observations'] for event_id in o.get('event_ids',[])}
    groups={};blocked=[]
    for d in documents:
        for e in d.get('precursor_events',[]):
            o=obs.get(e['event_id'])
            if not o:continue
            fields=o['resolved_fields'];scope={k:norm(f['value']) for k,f in fields.items()}
            if len(scope)!=len(FIELDS):continue
            supporting={r['document_id'] for f in fields.values() for r in [f['reference'],*f.get('support_references',[])]}
            supporting.update(r['document_id'] for p in o['relationship_proofs'] for r in p['references'])
            invalid=[]
            for source_id in supporting:
                source=docs[source_id]
                if (source.get('provenance')!='PASS' or not source_search.primary_origin(source,source.get('precursor_events',[]) or [{'source_quote':source['body']}])
                    or strict.PUBLIC_CONFIRMATION.search(source['body'])):
                    invalid.append(source_id)
            if invalid:
                blocked.append({'event_id':e['event_id'],'reason':'SUPPORTING_OR_RELATION_SOURCE_NOT_PREPUBLIC_PRIMARY','document_ids':sorted(invalid)});continue
            if not source_search.primary_origin(d,[e]):
                blocked.append({'event_id':e['event_id'],'reason':'PRIMARY_ISSUER_RELATION_UNVERIFIED'});continue
            try:strict.publication_cutoff(d,at,allow_unknown=True)
            except (ValueError,TypeError,KeyError) as exc:
                blocked.append({'event_id':e['event_id'],'reason':str(exc)});continue
            if strict.PUBLIC_CONFIRMATION.search(d['body']):
                blocked.append({'event_id':e['event_id'],'reason':'PUBLIC_CONFIRMATION_NOT_PRECURSOR'});continue
            # Preserve the existing physical TARGET identity across readers.
            # A new evidence route must not create a second first record.
            tid='precursor-'+strict.digest({k:scope[k] for k in FIELDS})
            item={**deepcopy(e),'scope':scope,'attribute_evidence':fields,'graph_observation':o['observation_id'],
                  'relationship_proofs':o['relationship_proofs']}
            groups.setdefault(tid,{'target_id':tid,'scope':scope,'events':[]})['events'].append(item)
    pairs=[];signals=[];annotations={}
    for tid,g in groups.items():
        demand=[e for e in g['events'] if e['role']=='DEMAND' and e.get('incremental') and e.get('demand_status') in ('COMMITTED','CONFIRMED_PLAN') and e['kind']!='DEMAND_CHANGE']
        supply=[e for e in g['events'] if e['role']=='SUPPLY']
        relief=[e for e in g['events'] if e['kind'] in ('RELIEF','DEMAND_CHANGE') or e.get('temporal_facts',{}).get('relief')]
        unresolved_relief=[]
        for source in documents:
            if source.get('provenance')!='PASS' or not source_search.primary_origin(source,source.get('precursor_events',[])):continue
            for e in source.get('precursor_events',[]):
                kinds={r['kind'] for r in e.get('temporal_facts',{}).get('relief',[])}
                if not kinds & {'QUALIFIED_SUBSTITUTE','UNVERIFIED_SUBSTITUTE','COMPLETED_CAPACITY','INVENTORY','DESIGN_CHANGE','DEMAND_CANCEL_OR_DELAY'}:continue
                fields={k:norm(f['value']) for k,f in e['scope'].items()}
                if not all(fields.get(k)==g['scope'][k] for k in ('product','specification')):continue
                if any(k in fields and fields[k]!=g['scope'][k] for k in ('region','customer_group')):continue
                if fields.get('supply_pool')!=g['scope']['supply_pool'] or any(k not in fields for k in ('region','customer_group')):
                    unresolved_relief.append({'event_id':e['event_id'],'reference':reader.reference(source,**e['locator']), 'reason':'ALTERNATIVE_SUPPLY_ELIGIBILITY_MARKET_OR_COVERAGE_UNVERIFIED'})
        for de in demand:
            for se in supply:
                independent,reason=_independent(de,se,docs)
                if not independent:blocked.append({'demand_event':de['event_id'],'supply_event':se['event_id'],'reason':reason});continue
                comparison=temporal.compare(de,se)
                pair={'target_id':tid,'demand_event':de['event_id'],'supply_event':se['event_id'], 'comparison':comparison,
                      'independent':True,'relief_event_ids':[e['event_id'] for e in relief]}
                pairs.append(pair)
                if unresolved_relief:
                    pair['engine_state']='BLOCKED_UNRESOLVED_ALTERNATIVE_OR_RELIEF';pair['unresolved_relief']=unresolved_relief;continue
                if mode=='LIVE':
                    evidence_ids={de['document_id'],se['document_id']} | {r['document_id'] for e in (de,se) for f in e['attribute_evidence'].values() for r in [f['reference'],*f.get('support_references',[])]}
                    if not evidence_ids & set(new_document_ids or []):
                        pair['engine_state']='NO_NEW_SOURCE_THIS_CYCLE_NOT_LIVE_DISCOVERY';continue
                if comparison['state'] not in ('POSSIBLE_TIMING_GAP','POSSIBLE_QUANTITY_GAP'):continue
                if any(e['kind'] in ('RELIEF','DEMAND_CHANGE') for e in relief):
                    pair['engine_state']='BLOCKED_UNRECONCILED_RELIEF';continue
                need=comparison.get('need')
                if not need or need.get('start')==UNKNOWN:pair['engine_state']='NEED_WINDOW_UNKNOWN';continue
                months=(strict.clock(need['start']+'T00:00:00+00:00')-at).days/30.4375
                if not 12<=months<=36:pair['engine_state']='OUTSIDE_12_36_MONTH_HORIZON';continue
                if not all(e.get('window') for e in (de,se)):
                    pair['engine_state']='PROTECTED_ENGINE_UNSUPPORTED_LITERAL_WINDOW';continue
                try:
                    for e in (de,se):early._window(docs[e['document_id']],e['window'])
                except ValueError:pair['engine_state']='PROTECTED_ENGINE_UNSUPPORTED_LITERAL_WINDOW';continue
                pair['engine_state']='FORWARDED_TO_UNCHANGED_EARLY_ENGINE'
                for e in (de,se):
                    signal={'document_id':e['document_id'],'target_id':tid,'target':' / '.join(g['scope'][k] for k in ('region','customer_group','supply_pool','specification','product')),
                            'specification':g['scope']['specification'],'region':g['scope']['region'],
                            'supply_pool':strict.digest(g['scope']),'role':e['role'],'source_quote':e['source_quote'],
                            'locator':e['locator'],'quantity':e.get('quantity',UNKNOWN),'unit':e.get('unit',UNKNOWN),'basis':e.get('basis',UNKNOWN),
                            'qualified':e.get('qualified',False),'coverage_complete':e.get('coverage_complete',False),
                            'target_relation_verified':True,'target_relation_reference':{**reader.reference(docs[e['document_id']],**e['locator']),'relationship':'SAME_TARGET'},
                            'graph_attribute_evidence':e['attribute_evidence'],'graph_relationship_proofs':e['relationship_proofs'], 'event_id':e['event_id']}
                    if e['role']=='DEMAND':signal.update(signal_type='committed_order',demand_status=e['demand_status'],increase_kind='NEW_ORDER',increase_locator=e['locator'],future_demand_window=e['window'])
                    else:signal.update(signal_type='production_ramp',supply_status='UNDER_CONSTRUCTION' if e.get('pending') else 'AVAILABLE',status_locator=e['locator'],known_supply_window=e['window'])
                    signals.append(signal)
                annotations[tid]={'decisive_UNKNOWN':[{'field':'total_market_qualified_supply','value':UNKNOWN}], 'scope_evidence':g['scope']}
    batch=stamp_export({'mode':mode,'documents':documents,'signals':list({strict.digest(s):s for s in signals}.values()),'candidate_annotations':annotations})
    result=early.discover(batch,mode=mode,now=now)
    graph.update(targets=list(groups.values()),pairs=pairs,blocked=blocked,
                 complete_target_events=sum(len(o['resolved_fields'])==len(FIELDS) and bool(o.get('event_ids')) for o in graph['observations']),
                 independent_pairs=len(pairs),comparable_period_pairs=sum(p['comparison']['state'] not in ('UNKNOWN','RECONCILE_RELIEF') for p in pairs),
                 protected_result=result,protected_batch=batch)
    return graph
