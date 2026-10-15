"""Read-only point-in-time harness around existing V4 engines, not a predictor.

INPUT and OUTCOME have separate ledgers. Outcomes never reach engine execution.
No network/model activation, LIVE run, S-stage promotion or threshold tuning.
"""
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta
import json

from bct.objective_lock import stamp_export
from .store import sha
from .pipeline import analyze as existing_analyze
from .cross_industry import reading_result

VERSION = 'bct-historical-backtest-1'


def clock(text):
    value=datetime.fromisoformat(text.replace('Z','+00:00'))
    if value.tzinfo is None: raise ValueError('TIMEZONE_REQUIRED')
    return value


def date_bounds(value, precision):
    if precision=='DATE':
        d=date.fromisoformat(value);return d,d
    if precision=='MONTH':
        year,month=map(int,value.split('-'));return date(year,month,1),date(year,month,monthrange(year,month)[1])
    raise ValueError('PUBLICATION_PRECISION_UNKNOWN')


def add_months(day,months):
    year=day.year+(day.month-1+months)//12;month=(day.month-1+months)%12+1
    return date(year,month,min(day.day,monthrange(year,month)[1]))


def input_view(doc, selection, cutoff):
    """Exact excerpt with a conservative simulated availability upper bound.

    Acquisition/publication stay unchanged in the source ledger. The engine
    projection is explicitly BACKTEST and never evidence of an old LIVE run.
    """
    if doc.get('backtest_role')!='INPUT':raise ValueError('OUTCOME_OR_UNCLASSIFIED_DOCUMENT_CANNOT_ENTER_ENGINE')
    if sha(doc['body'].encode())!=doc['body_sha256']:raise ValueError('BODY_HASH_MISMATCH')
    if doc.get('provenance')!='PASS':raise ValueError('SOURCE_PROVENANCE_UNVERIFIED')
    proof=doc.get('historical_version_proof',{})
    if proof.get('status')!='VERIFIED_DATED_EDITION' or proof.get('body_sha256')!=doc['body_sha256'] or proof.get('raw_sha256')!=doc['raw_sha256']:
        raise ValueError('HISTORICAL_VERSION_NOT_VERIFIED')
    low,high=date_bounds(doc['published_at'],doc['publication_precision'])
    if high>=clock(cutoff).date():raise ValueError('PUBLICATION_INTERVAL_NOT_STRICTLY_BEFORE_CUTOFF')
    if proof.get('file_modified_at') and clock(proof['file_modified_at'])>clock(cutoff):
        raise ValueError('LATER_VERSION_CANNOT_BE_BACKDATED')
    a,b=selection['start'],selection['end']
    if type(a)is not int or type(b)is not int or not 0<=a<b<=len(doc['body']):raise ValueError('EXACT_INPUT_RANGE_REQUIRED')
    body=doc['body'][a:b]
    if sha(body.encode())!=selection['excerpt_sha256']:raise ValueError('INPUT_EXCERPT_HASH_MISMATCH')
    if selection.get('body_sha256')!=doc['body_sha256']:raise ValueError('SELECTION_SOURCE_VERSION_MISMATCH')
    view=deepcopy(doc)
    view.update(document_id='backtest-view-'+sha([doc['document_id'],a,b,sha(body.encode())]),body=body,body_sha256=sha(body.encode()),
                published_at=high.isoformat(),publication_precision='DATE',available_at=high.isoformat()+'T23:59:59+00:00')
    view['backtest_projection']={'source_document_id':doc['document_id'],'source_body_sha256':doc['body_sha256'],
        'source_range':{'start':a,'end':b},'source_published_at':doc['published_at'],'source_publication_precision':doc['publication_precision'],
        'source_acquired_at':doc['acquired_at'],'simulated_available_at':view['available_at'],
        'policy':'CONSERVATIVE_PUBLICATION_UPPER_BOUND_NOT_ACTUAL_ACQUISITION_OR_LIVE_OBSERVATION'}
    return view


def execute(case, input_ledger):
    """No outcome argument or access to its database. Labels cannot steer input."""
    held=[];views=[];cpu=[];origins=set()
    for sel in case.get('inputs',[]):
        try:
            row=input_ledger.db.execute('SELECT payload FROM documents WHERE id=?',(sel['document_id'],)).fetchone()
            if row is None:raise ValueError('INPUT_SOURCE_NOT_RESTORED')
            doc=json.loads(row[0]);v=input_view(doc,sel,case['cutoff'])
            # A second URL/version of the same event cannot multiply evidence.
            origin=doc.get('origin_event_id')or doc.get('origin_id')
            if not origin or origin=='UNKNOWN':raise ValueError('INPUT_EVENT_ORIGIN_UNKNOWN')
            if origin in origins:raise ValueError('REQUOTATION_OR_DUPLICATE_ORIGIN')
            origins.add(origin);views.append(v)
            reading=sel.get('CPU_reading')
            if reading is not None:
                if (reading.get('input_sha256')!=sha(reading.get('selected_windows',[]))
                    or any(s.get('document_id')!=v['document_id'] for s in reading.get('spans',[]))):
                    raise ValueError('CPU_READING_INPUT_MISMATCH')
                cpu.append(reading_result(v,reading))
        except (KeyError,ValueError,TypeError)as exc:
            held.append({'document_id':sel.get('document_id'),'reason':str(exc)})
    # Invalid cached CPU data cannot erase the source from the original parser;
    # it is held as a separate advisory. No model execution occurs here.
    if not views:return {'case_id':case['id'],'status':'NOT_RUN_NO_ADMISSIBLE_INPUT','held':held,'timeline':[],'S1':0,'S2':0,'S3':0}
    checkpoints=sorted({case['cutoff'],*[v['published_at']+'T23:59:59+00:00' for v in views if v['published_at']+'T23:59:59+00:00'<case['cutoff']]})
    timeline=[]
    for at in checkpoints:
        selected=[v for v in views if date.fromisoformat(v['published_at'])<clock(at).date()]
        if not selected:continue
        # Actual existing domain engine, no outcomes, result dates or external
        # proposals inserted into the original parser's source text.
        engine=existing_analyze(selected,mode='BACKFILL',as_of=at)
        records=[r for x in cpu for r in x.get('records',[]) if r.get('event_status')=='ADOPTED_RESEARCH_EVENT'
                 and r['context']['document_id']in {d['document_id']for d in selected}]
        s3=[c for c in engine.get('candidates',[])if c.get('s_stage')=='S3']
        timeline.append({'cutoff':at,'engine':engine,'CPU_advisory_results':cpu,
          'explicit_S1_record_ids':[r['id']for r in records if r.get('s_stage')=='S1'],
          'explicit_S2_record_ids':[r['id']for r in records if r.get('s_stage')=='S2'],
          'explicit_S3_candidates':s3,
          'EARLY_candidates_not_S3':len([c for c in engine.get('candidates',[])if c.get('s_stage')!='S3']),
          'input_document_ids':[v['document_id']for v in selected]})
    return {'case_id':case['id'],'status':'EXECUTED_BACKTEST','held':held,'timeline':timeline,
      'input_views':[{k:v for k,v in d.items()if k!='body'}for d in views],
      'S1':len({i for t in timeline for i in t['explicit_S1_record_ids']}),
      'S2':len({i for t in timeline for i in t['explicit_S2_record_ids']}),
      'S3':len({c['target_id']for t in timeline for c in t['explicit_S3_candidates']})}


def assess(case, result, outcome, *, observed_through):
    """Scoring happens after execution and cannot mutate its frozen input."""
    label=outcome.get('label','UNKNOWN');reason=[]
    if outcome.get('case_id')!=case['id']:reason.append('OUTCOME_CASE_MISMATCH')
    if outcome.get('target')!=case['target']:reason.append('OUTCOME_TARGET_MISMATCH')
    if outcome.get('status')!='VERIFIED_PRIMARY_SOURCE':reason.append('OUTCOME_UNVERIFIED')
    if case.get('metric_blockers'):reason.extend(case['metric_blockers'])
    start=add_months(clock(case['cutoff']).date(),12);end=add_months(clock(case['cutoff']).date(),36)
    if label=='NEGATIVE' and (date.fromisoformat(observed_through)<end or outcome.get('coverage_end','')<end.isoformat()
                              or not outcome.get('qualified_demand_met_evidence') or not outcome.get('coverage_complete')):
        reason.append('NEGATIVE_NOT_PROVEN_OVER_COMPLETE_WINDOW')
    if label=='POSITIVE':
        try:
            low,high=date_bounds(outcome['occurrence'],outcome['occurrence_precision'])
            if low<start or high>end:reason.append('OUTCOME_NOT_WITHIN_12_36_MONTHS')
        except (KeyError,ValueError):reason.append('OUTCOME_OCCURRENCE_UNKNOWN')
    scored=not reason and label in ('POSITIVE','NEGATIVE') and result['status']=='EXECUTED_BACKTEST'
    s3=[(t['cutoff'],c)for t in result.get('timeline',[])for c in t['explicit_S3_candidates']]
    matched=[(at,c)for at,c in s3 if c.get('target')==case['target']or c.get('scope')==case['target']]
    first=min((at for at,_ in matched),default=None)
    news=outcome.get('first_in_scope_shortage_report_at');lead=None
    if news and clock(case['cutoff'])>=clock(news):
        reason.append('CUTOFF_NOT_BEFORE_SHORTAGE_REPORT');scored=False
    if first and news and clock(first)<clock(news):lead=(clock(news)-clock(first)).days
    return {'case_id':case['id'],'label':label,'eligible_for_scoped_metric':scored,'held_reasons':reason,
        'window_start':start.isoformat(),'window_end':end.isoformat(),'S3_emitted':len(s3),'S3_target_matched':len(matched),
        'TP':int(scored and label=='POSITIVE'and bool(matched)), 'FN':int(scored and label=='POSITIVE'and not matched),
        'FP':int(scored and label=='NEGATIVE'and bool(matched)), 'TN':int(scored and label=='NEGATIVE'and not matched),
        'S3_before_in_scope_report':bool(scored and label=='POSITIVE'and lead is not None),'lead_days':lead,
        'independent_holdout_eligible':bool(scored and case.get('split')=='HOLDOUT'and case.get('development_exposed')is False
                                             and outcome.get('independent_adjudication_verified')is True)}


def summarize(results,assessments):
    tp,fp,fn=[sum(x[k]for x in assessments)for k in ('TP','FP','FN')]
    return stamp_export({'version':VERSION,'mode':'BACKTEST','execution_engine_mode':'BACKFILL',
      'results':results,'assessments':assessments,'candidates':[],
      'metrics':{'TP':tp,'FP':fp,'FN':fn,'precision':tp/(tp+fp)if tp+fp else None,'recall':tp/(tp+fn)if tp+fn else None,
                 'positive_denominator':tp+fn,'negative_denominator':sum(x['label']=='NEGATIVE'and x['eligible_for_scoped_metric']for x in assessments),
                 'S3_leading_cases':sum(x['S3_before_in_scope_report']for x in assessments)},
      'AI_adoption':'FAIL_UNCHANGED','independent_AI_evaluation':'BLOCKED_UNCHANGED','new_LIVE_firsts':0,
      'forecast_performance':'BLOCKED_MINIMUM_COHORT_AND_INDEPENDENCE_NOT_ESTABLISHED'})
