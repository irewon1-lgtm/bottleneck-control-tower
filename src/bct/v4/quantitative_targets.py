"""Q2 evidence queues and scope checks; reuses TARGET identity, never promotes S stages."""
from collections import defaultdict,Counter
from decimal import Decimal
import json
from urllib.parse import urlsplit
from .evidence_path import TARGET,target_key,normalize_quantity
from .quantitative import research_export,CheckpointBudget,LIMIT
from .store import sha,now

KIND='QUANTITATIVE_TARGET_REVIEW'


def comparable(demand,supply):
    """Eligibility for a later existing-engine comparison, not a shortage rule."""
    a,b=target_key(demand),target_key(supply)
    if a[0]and b[0]and a[0]!=b[0]:return False,'PRODUCT_MISMATCH'
    if not all(a)or not all(b):return False,'TARGET_FIELDS_UNKNOWN'
    if a!=b:return False,'DIFFERENT_TARGET'
    if demand.get('lineage')==supply.get('lineage'):return False,'SAME_OR_UNKNOWN_SOURCE_LINEAGE'
    if not demand.get('lineage')or not supply.get('lineage'):return False,'LINEAGE_UNKNOWN'
    if demand.get('unit')!=supply.get('unit')or not demand.get('unit'):return False,'UNIT_MISMATCH_OR_UNKNOWN'
    if demand.get('period')!=supply.get('period')or not demand.get('period'):return False,'PERIOD_MISMATCH_OR_UNKNOWN'
    if demand.get('actuality')!='ACTUAL'or supply.get('actuality')!='ACTUAL':return False,'PLAN_OR_UNCONFIRMED_NOT_AVAILABLE_SUPPLY'
    if not demand.get('source_verified')or not supply.get('source_verified'):return False,'SOURCE_NOT_VERIFIED'
    if demand.get('measurement_type')!='PHYSICAL'or supply.get('measurement_type')!='PHYSICAL':return False,'MONEY_OR_NONPHYSICAL_NOT_QUANTITY'
    if demand.get('quantity')is None or supply.get('quantity')is None:return False,'PHYSICAL_QUANTITY_UNKNOWN'
    return True,'READY_FOR_EXISTING_ENGINE_NOT_A_SHORTAGE_DECISION'


def prepare(ledger,legacy,*,as_of):
    active=research_export(ledger)['observations'];groups=defaultdict(list);latest_eia={};counts=Counter()
    for item in active:
        r=item['record'];source=r['source_id']
        if source=='eia':
            old=latest_eia.get(r['entity_or_facility_id'])
            if old is None or r['period_start']>old['record']['period_start']:latest_eia[r['entity_or_facility_id']]=item
        elif source=='census_trade'and r['measurement_type']=='PHYSICAL':
            groups[('TRADE_SERIES',r['product_or_classification'],r['attributes'].get('trade_direction','UNKNOWN'),r['metric'],r['unit_original'])].append(item)
        elif source=='sec'and r['measurement_type']=='PHYSICAL':
            groups[('SEC_PHYSICAL_CONTEXT',r['product_or_classification'],r['geography'],r['metric'],r['unit_original'])].append(item)
    for item in latest_eia.values():
        r=item['record'];sheet=r['attributes']['sheet']
        groups[('FACILITY_CLASS',r['product_or_classification'],r['geography'],sheet,r['unit_original'])].append(item)
    output=[]
    for key,items in sorted(groups.items()):
        kind,product,region_or_direction,scope,unit=key
        missing=['customer_need_window','actual_product_order_quantity','customer_qualified_supplier_pool','qualified_available_supply','specification_equivalence']
        if kind=='TRADE_SERIES':missing+=['trade_is_not_production_or_customer_order','USGS_Census_lineage_not_independent','country_aggregate_not_specific_supplier']
        elif kind=='FACILITY_CLASS':missing+=['nameplate_is_not_qualified_committed_output']
        else:missing+=['inline_fact_event_relationship_not_reviewed']
        target={k:None for k in TARGET};target['product']={'normalized':product.casefold()}
        if kind=='FACILITY_CLASS':target['region']={'normalized':region_or_direction.casefold()}
        row={'id':sha(['bct-q2-evidence-input-1',key,sorted(x['id']for x in items)]),'kind':kind,'product':product,
             'scope':key[2:],'observation_ids':sorted(x['id']for x in items),'observations':len(items),
             'target':target,'missing':missing,'review_state':'QUANTITATIVE_CONTEXT_ONLY','as_of':as_of,
             'actual_order_quantity':None,'qualified_supply_quantity':None,'s_stage':'UNKNOWN','research_only':True}
        if kind=='FACILITY_CLASS':
            # One latest reporting edition per generator. A nominal MW sum is
            # explicitly not available/qualified supply and never enters S gates.
            row['reported_nameplate_MW_sum']=format(sum((Decimal(x['record']['value_normalized_or_null'])for x in items if x['record']['value_normalized_or_null']is not None),Decimal(0)),'f')
            row['reported_status']=scope
            planned=[]
            for item in items:
                a=item['record']['attributes'];year=a.get('Planned Operation Year');month=a.get('Planned Operation Month')
                try:
                    y,m=int(float(year)),int(float(month))
                    if 1<=m<=12:planned.append(f'{y:04d}-{m:02d}')
                except(TypeError,ValueError):pass
            row['planned_reported_dates_not_supply_guarantees']=sorted(set(planned))
        output.append(row);counts[kind]+=1
    for old in legacy:
        product=old['product'];fields=old.get('fields',{});surface=fields.get('quantity',{}).get('surface')
        converted=normalize_quantity(surface)['normalized']if surface is not None else None
        row={'id':sha(['bct-q2-legacy-input-1',old['id']]),'kind':'EXISTING_EVENT_REVIEW','product':product,
             'scope':[],'observation_ids':[],'observations':0,'target':{k:({'normalized':old['target'][k]['normalized']}if old['target'].get(k)else None)for k in TARGET},
             'missing':['customer_need_window','qualified_available_supply','independent_same_TARGET_counterpart'],
             'review_state':'EXISTING_REVIEW_REUSED_NOT_NEW_DISCOVERY','as_of':as_of,
             'actual_order_quantity':converted,'qualified_supply_quantity':None,'s_stage':'UNKNOWN','research_only':True,
             'legacy_record_id':old['id'],'legacy_s_stage':old.get('s_stage'),'role':old.get('role'),
             'quantity_literal':surface,'publication_date':old.get('context',{}).get('published_at','UNKNOWN')}
        output.append(row);counts['EXISTING_EVENT_REVIEW']+=1
    comparison_reasons=Counter();eligible=0;enriched=[]
    for r in legacy:
        fields=r.get('fields',{});quantity=fields.get('quantity',{}).get('surface')
        enriched.append({'target':r['target'],'role':r.get('role'),'lineage':urlsplit(r.get('context',{}).get('origin_url','')).hostname,'unit':fields.get('unit',{}).get('normalized'),'period':fields.get('need_time',{}).get('normalized'),'actuality':r.get('actuality','UNKNOWN'),'source_verified':r.get('event_status')=='ADOPTED_RESEARCH_EVENT','measurement_type':'PHYSICAL','quantity':normalize_quantity(quantity)['normalized']if quantity else None})
    for demand in [r for r in enriched if r['role']=='DEMAND_INCREASE']:
        for supply in [r for r in enriched if r['role']in {'SUPPLY_DECREASE','SUPPLY_DELAY'}]:
            ok,reason=comparable(demand,supply);eligible+=ok;comparison_reasons[reason]+=1
    from .quantitative_counterpart import seeds,request_for
    products=[json.loads(p)for p, in ledger.db.execute("SELECT payload FROM events WHERE kind='QUANTITATIVE_PRODUCT_FACT'")]
    counterpart_requests=[request_for(s)for s in seeds(products,legacy)]
    return {'records':output,'counterpart_requests':counterpart_requests,'counterpart_policy':'Shared opposite-side requests only; no automatic adoption or scheduled execution',
            'counts':dict(counts),'latest_facility_observations':len(latest_eia),'eligible_independent_pairs':eligible,'actual_comparison_reasons':dict(comparison_reasons),'preserved_relief_events':sum(r.get('role')=='RELIEF'for r in legacy),
            'new_S1':0,'new_S2':0,'new_S3':0,'LIVE':0,'source_body_verification_repeated':False,
            'meaning':'Evidence queue/gap review only. Existing8 S1 remain historical research signals; no demand/supply/shortage inferred from trade or nameplate.'}


def save(ledger,legacy,*,as_of):
    result=prepare(ledger,legacy,as_of=as_of);added=0
    with ledger.db:
        ledger.db.execute("CREATE INDEX IF NOT EXISTS q2_review_id ON events(json_extract(payload,'$.id')) WHERE kind='QUANTITATIVE_TARGET_REVIEW'")
        for record in result['records']:
            if ledger.db.execute("SELECT 1 FROM events WHERE kind='QUANTITATIVE_TARGET_REVIEW'AND json_extract(payload,'$.id')=?",(record['id'],)).fetchone():continue
            ledger.event(KIND,record);added+=1
        if CheckpointBudget().size(ledger.db.serialize())>LIMIT:raise ValueError('Q2_CHECKPOINT_16MIB_LIMIT')
    return {k:v for k,v in result.items()if k!='records'}|{'added_review_records':added,'total_review_records':len(result['records']),
        'sample_reviews':[{'product':r['product'],'kind':r['kind'],'missing':r['missing'],'review_state':r['review_state']}for r in result['records'][:6]],'at':now()}
