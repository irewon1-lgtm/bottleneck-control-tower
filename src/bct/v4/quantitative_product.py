"""Source-reviewed physical facts; not automatic discovery, supply qualification or S gates."""
import re
from decimal import Decimal
from .store import sha
from .evidence_path import reference,NUMBER_WORDS

KIND='QUANTITATIVE_PRODUCT_FACT'
FIELDS={'id','product','kind','quantity','unit','customer','supplier','specification','region','need_window',
        'qualified_capacity','planned_delivery','actuality','source','references','review','s_stage','research_only'}


def locate(doc,quote):
    body=doc['body'];positions=[m.start()for m in re.finditer(re.escape(quote),body)]
    if len(positions)!=1:raise ValueError('PRODUCT_FACT_CONTEXT_NOT_UNIQUE')
    start=positions[0];return reference(doc,{'start':start,'end':start+len(quote),'quote':quote})


def literal(doc,text,context):
    quote=context['quote'];hits=[m.start()for m in re.finditer(re.escape(text),quote)]
    if len(hits)!=1:raise ValueError('PRODUCT_FACT_LITERAL_NOT_UNIQUE_IN_CONTEXT')
    start=context['start']+hits[0]
    r=reference(doc,{'start':start,'end':start+len(text),'quote':text},context)
    # Own derived values/positions only; do not copy article sentences/contacts.
    return {'value':text,'start':r['start'],'end':r['end']}


def review(doc,spec):
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('PRODUCT_FACT_BODY_HASH')
    if doc.get('body_status')!='FULL'or doc.get('provenance')!='PASS':raise ValueError('PRODUCT_FACT_SOURCE_BLOCKED')
    context=locate(doc,spec['context']);product=literal(doc,spec['product'],context);kind=spec['kind'];refs={'product':product}
    if kind=='ACTUAL_ORDER':
        text=context['quote']
        if re.search(r'\b(?:not|cancelled|canceled|non-binding|option|options|planned|plans|would|may|could)\b|\bup to\b',text,re.I):raise ValueError('PRODUCT_FACT_ORDER_UNCONFIRMED')
        if not re.search(r'\b(?:signed a contract|finalised an order|finalized an order|placed a firm order|purchased)\b',text,re.I):raise ValueError('PRODUCT_FACT_ORDER_RELATION_UNKNOWN')
        qty=literal(doc,spec['quantity_literal'],context);refs['quantity']=qty
        raw=qty['value'].casefold();normalized=NUMBER_WORDS.get(raw,raw)
        if not re.fullmatch(r'\d+(?:\.\d+)?',normalized)or Decimal(normalized)<=0:raise ValueError('PRODUCT_FACT_QUANTITY_UNKNOWN')
        unit=spec['unit'];literal(doc,unit,context)
        if re.search(r'USD|EUR|dollar|million|billion|\$',unit,re.I):raise ValueError('PRODUCT_FACT_MONEY_NOT_QUANTITY')
        relation=re.escape(qty['value'])+r'\s+(?:'+re.escape(spec['supplier'])+r'\s+)?'+re.escape(product['value'])+r'\s+'+re.escape(unit)
        if not re.search(relation,text,re.I):raise ValueError('PRODUCT_FACT_QUANTITY_OBJECT_NOT_LINKED')
        if re.search(r'\b(?:to produce|to manufacture|production of)\s+'+relation,text,re.I):raise ValueError('PRODUCT_FACT_OUTPUT_NOT_ORDERED_OBJECT')
        actuality='ACTUAL'
    elif kind=='EXPECTED_DELIVERY':
        if not re.search(r'expected to ship',context['quote'],re.I):raise ValueError('PRODUCT_FACT_SHIP_RELATION_UNKNOWN')
        refs['planned_delivery']=literal(doc,spec['planned_delivery'],context)
        normalized=None;unit=None;actuality='PLAN'
    else:raise ValueError('PRODUCT_FACT_KIND')
    for field in ['customer','supplier','specification','region','need_window']:
        if spec.get(field):refs[field]=literal(doc,spec[field],context)
    source={k:doc.get(k,'UNKNOWN')for k in ['document_id','origin_url','origin_publisher','published_at','acquired_at','body_sha256','raw_sha256']}
    source.update(body_status='FULL',provenance='PASS',context_start=context['start'],context_end=context['end'],context_sha256=sha(context['quote'].encode()))
    record={'product':product['value'],'kind':kind,'quantity':normalized,'unit':unit,'customer':spec.get('customer'),
            'supplier':spec.get('supplier'),'specification':spec.get('specification'),'region':spec.get('region'),
            'need_window':spec.get('need_window'),'qualified_capacity':None,'planned_delivery':spec.get('planned_delivery'),
            'actuality':actuality,'source':source,'references':refs,'review':'ASSISTANT_EXPLICIT_SOURCE_REVIEW_NOT_HUMAN_OR_INDEPENDENT','s_stage':'UNKNOWN','research_only':True}
    return {'id':sha(['q2-product-fact-1',record]),**record}


def save(ledger,records):
    added=0
    with ledger.db:
        ledger.db.execute("CREATE INDEX IF NOT EXISTS q2_product_fact_id ON events(json_extract(payload,'$.id'))WHERE kind='QUANTITATIVE_PRODUCT_FACT'")
        for r in records:
            if set(r)!=FIELDS or r['s_stage']!='UNKNOWN'or r['qualified_capacity']is not None:raise ValueError('PRODUCT_FACT_UNREVIEWED_FIELD_OR_PROMOTION')
            if ledger.db.execute("select 1 from events where kind=?and json_extract(payload,'$.id')=?",(KIND,r['id'])).fetchone():continue
            ledger.event(KIND,r);added+=1
    return {'added':added,'reviewed_orders':[{'product':r['product'],'quantity':r['quantity'],'unit':r['unit']}for r in records if r['kind']=='ACTUAL_ORDER'],'qualified_capacity':0,'independent_demand_supply_pairs':0,'new_S2':0,'new_S3':0}
