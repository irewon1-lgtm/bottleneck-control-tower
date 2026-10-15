"""Forward existing source-reviewed stages and gap decisions, never promote LIVE.

The gap engine remains future_hypothesis.compare_gap. CPU entities/UNKNOWN/EARLY
are not eligible. Scope literals must already be explicit reviewed record fields.
"""
from collections import Counter
from datetime import date
import calendar
from copy import deepcopy

from bct.future_bottleneck import screen
from bct.future_hypothesis import extract_facts, compare_gap
from bct.objective_lock import stamp_export
from .evidence_path import accept, target_key
from .store import sha


def month(day, n):
    y,m = divmod(day.year*12+day.month-1+n,12)
    return date(y,m+1,min(day.day,calendar.monthrange(y,m+1)[1]))


def project(documents, records, *, as_of, synthetic=False):
    """Revalidate existing source reviews, keep old records, return separate probes."""
    clock = date.fromisoformat(as_of)
    docs = {d['document_id']:d for d in documents}
    stages, held, facts, reliefs = [], [], [], []
    for original in records:
        try:
            d = docs[original['context']['document_id']]
            if synthetic != (d.get('synthetic') is True): raise ValueError('SYNTHETIC_SCOPE_MISMATCH')
            if d.get('provenance')!='PASS' or d.get('primary_source_verified') is not True:
                raise ValueError('PRIMARY_SOURCE_NOT_VERIFIED')
            if date.fromisoformat(d['published_at'][:10])>clock: raise ValueError('FUTURE_PUBLICATION')
            review = original.get('source_review',{}).get('original_review')
            if not review: raise ValueError('EXPLICIT_SOURCE_REVIEW_REQUIRED_NOT_CPU')
            r = accept(d,original['original_proposal'],source_review=review)
            if r!=original: raise ValueError('SOURCE_REVIEW_RECORD_CHANGED')
            stages.append({'record_id':r['id'],'stage':r['s_stage'],'role':r['role'],
                'target':target_key(r),'origin':'UNCHANGED_EXISTING_ACCEPT_RETURN', 'promoted':False})
            if r['event_status']!='ADOPTED_RESEARCH_EVENT' or r['actuality']!='ACTUAL': continue
            if r['role']=='RELIEF':
                reliefs.append({'record_id':r['id'],'target':target_key(r)})
                continue
            if not all(r['target'].values()):
                held.append({'record_id':r['id'],'reason':'INCOMPLETE_TARGET5_NO_GAP_COMPARISON'}); continue
            context = r['context']['quote']; offset = r['context']['start']
            parsed = extract_facts(context,screen(context))['scope_facts']
            allowed = {'DEMAND_INCREASE':'DEMAND','SUPPLY_DECREASE':'SUPPLY',
                       'SUPPLY_DELAY':'SUPPLY','SUPPLY_INCREASE':'SUPPLY'}
            for f in parsed:
                if f['role']!=allowed.get(r['role']) or f['target'].casefold()!=r['product']['normalized']: continue
                fields = r['fields']
                # The parser cannot fill unreviewed quantity/time/scope fields.
                required = ('quantity','unit','period','basis')
                if not all(k in fields for k in required):
                    held.append({'record_id':r['id'],'reason':'REVIEWED_GAP_FIELDS_MISSING'}); continue
                from .evidence_path import normalize_quantity
                number = normalize_quantity(fields['quantity']['surface'])['normalized']
                if (number is None or float(number)!=f['quantity'] or fields['unit']['normalized']!=f['unit']
                        or fields['basis']['normalized']!=f['basis'] or not isinstance(f['period'],dict)
                        or fields['period']['surface'] != f['period']['start']+' to '+f['period']['end']
                        or any(r['target'][k]['normalized']!=f[k].casefold() for k in ('specification','region','supply_pool'))):
                    raise ValueError('REVIEWED_FIELDS_PARSER_CONFLICT')
                period = f['period']
                if not month(clock,12)<=date.fromisoformat(period['start'])<=date.fromisoformat(period['end'])<=month(clock,36):
                    held.append({'record_id':r['id'],'reason':'OUTSIDE_12_TO_36_MONTHS'}); continue
                if f['coverage_complete']:
                    field = fields.get('qualified_supply_coverage')
                    if not field or field['surface']!='including all qualified suppliers, usable inventory and alternative suppliers':
                        raise ValueError('QUALIFIED_SUPPLY_RELIEF_SCOPE_NOT_REVIEWED')
                f.update(document_id=d['document_id'],body_sha256=d['body_sha256'],
                         locator={k:v+offset for k,v in f['locator'].items()},record_id=r['id'],
                         customer_group=r['target']['customer_group']['normalized'])
                facts.append(f)
        except (KeyError,ValueError,TypeError) as exc:
            held.append({'record_id':original.get('id'),'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})
    probes = []
    for d in [f for f in facts if f['role']=='DEMAND']:
        for s in [f for f in facts if f['role']=='SUPPLY']:
            dd,sd = docs[d['document_id']],docs[s['document_id']]
            identity = lambda x: tuple(x.get(k) for k in ('target','specification','region','supply_pool','customer_group'))
            if identity(d)!=identity(s) or d['period']!=s['period']: continue
            # Different URLs are insufficient for independence. Require an
            # attributed event/origin and different publishers, not a reprint.
            keys = ('origin_publisher','origin_id','origin_event_id')
            if d['document_id']==s['document_id'] or any(
                    dd.get(k) in (None,'','UNKNOWN') or sd.get(k) in (None,'','UNKNOWN') or dd[k]==sd[k] for k in keys):
                held.append({'record_id':d['record_id'],'reason':'INDEPENDENCE_NOT_VERIFIED'}); continue
            related = [r['record_id'] for r in reliefs if r['target']==(d['target'].casefold(),d['specification'].casefold(),d['region'].casefold(),d['customer_group'],d['supply_pool'].casefold())]
            if related:
                held.append({'record_id':d['record_id'],'reason':'RELIEF_REQUIRES_REVIEWED_SUPPLY_REFRESH','related_relief':related}); continue
            verdict = compare_gap([d,s],now=as_of+'T00:00:00+00:00')
            probes.append({'id':sha([d,s,as_of]),'stage':verdict['stage'],'engine_result':verdict,
                'engine':'bct.future_hypothesis.compare_gap','facts':[deepcopy(d),deepcopy(s)],
                'synthetic':synthetic,'candidate_registration':False,'forecast_success':False})
    return stamp_export({'version':'bct-reviewed-stage-bridge-1','as_of':as_of,
        'record_stages':stages,'gap_probes':probes,'held':held,
        'record_stage_counts':dict(Counter(r['stage'] for r in stages)),
        'gap_stage_counts':dict(Counter(r['stage'] for r in probes)),
        'synthetic':synthetic,'candidates':[],'LIVE_registration':False,'automatic_promotion':False,
        'AI_adoption':'FAIL_UNCHANGED','historical_performance':'BLOCKED_UNCHANGED'})


def save(ledger, documents, records, *, as_of, synthetic=False):
    result = project(documents,records,as_of=as_of,synthetic=synthetic)
    for doc in documents: ledger.capture(doc)
    return ledger.save_run('stage-probe-'+sha(result),result,'SYNTHETIC_STAGE_PROBE' if synthetic else 'RESEARCH_STAGE_PROBE')
