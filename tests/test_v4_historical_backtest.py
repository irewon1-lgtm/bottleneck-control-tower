"""Synthetic isolation/metric checks; not real lead-performance evidence."""
from copy import deepcopy
import pytest
from bct.v4 import historical_backtest as h
from bct.v4.store import Ledger,sha


def data():
    body='Atlas ordered novel pumps. Alternative supply is now operating.'
    d={'document_id':'original','body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(body.encode()),
       'origin_url':'https://official.example/report.pdf','origin_id':'original-edition','origin_publisher':'Atlas',
       'backtest_role':'INPUT','provenance':'PASS','primary_source_verified':True,'published_at':'2018-12',
       'publication_precision':'MONTH','acquired_at':'2026-10-15T00:00:00+00:00',
       'historical_version_proof':{'status':'VERIFIED_DATED_EDITION','body_sha256':sha(body.encode()),
          'raw_sha256':sha(body.encode()),'file_modified_at':'2018-12-19T00:00:00+00:00'}}
    s={'document_id':d['document_id'],'start':0,'end':len(body),'body_sha256':d['body_sha256'],'excerpt_sha256':sha(body.encode())}
    c={'id':'case','cutoff':'2019-01-01T00:00:00+00:00','inputs':[s],
       'target':{'product':'pumps','specification':'A','region':'US','customer_group':'Atlas','supply_pool':'Pool'},'split':'DEVELOPMENT'}
    return d,s,c


def test_conservative_month_interval_preserves_true_acquisition_and_relief():
    d,s,c=data();old=deepcopy(d);v=h.input_view(d,s,c['cutoff'])
    assert d==old and v['backtest_projection']['source_published_at']=='2018-12'
    assert v['available_at']=='2018-12-31T23:59:59+00:00'
    assert 'Alternative supply is now operating.'in v['body']
    with pytest.raises(ValueError,match='INTERVAL'):h.input_view(d,s,'2018-12-20T00:00:00+00:00')


@pytest.mark.parametrize('mutate,reason',[
 (lambda d,s:d.update(backtest_role='OUTCOME'),'OUTCOME'),
 (lambda d,s:d.update(published_at='2021-01'),'INTERVAL'),
 (lambda d,s:d.update(provenance='BLOCKED'),'PROVENANCE'),
 (lambda d,s:d['historical_version_proof'].update(status='UNKNOWN'),'VERSION'),
 (lambda d,s:d['historical_version_proof'].update(file_modified_at='2020-01-01T00:00:00Z'),'LATER_VERSION'),
 (lambda d,s:s.update(body_sha256='foreign'),'SELECTION_SOURCE'),
 (lambda d,s:s.update(excerpt_sha256='false'),'EXCERPT_HASH')])
def test_leakage_and_source_version_fail_closed(mutate,reason):
    d,s,c=data();mutate(d,s)
    with pytest.raises(ValueError,match=reason):h.input_view(d,s,c['cutoff'])


def test_only_input_ledger_reaches_unchanged_engine_and_requotes_are_not_counted(tmp_path,monkeypatch):
    d,s,c=data();l=Ledger(tmp_path/'INPUT');l.capture(d)
    other=deepcopy(d);other['document_id']='same-event-reprint';other['origin_url']='https://other.example/report';l.capture(other)
    t=deepcopy(s);t['document_id']=other['document_id'];c['inputs'].append(t)
    observed=[]
    def spy(docs,**kw):
        observed.extend(docs);assert kw['mode']=='BACKFILL'
        return {'candidates':[{'target_id':'early','candidate_class':'EARLY','s_stage':'UNKNOWN'}]}
    monkeypatch.setattr(h,'existing_analyze',spy)
    x=h.execute(c,l);l.close()
    assert len(observed)==1 and 'Alternative supply'in observed[0]['body']
    assert x['S3']==0 and x['timeline'][0]['EARLY_candidates_not_S3']==1
    assert any('DUPLICATE_ORIGIN'in r['reason']for r in x['held'])


def outcome(c,label='POSITIVE'):
    return {'case_id':c['id'],'target':c['target'],'label':label,'status':'VERIFIED_PRIMARY_SOURCE',
       'occurrence':'2021-02','occurrence_precision':'MONTH','first_in_scope_shortage_report_at':'2021-11-16T00:00:00Z'}


def test_empty_denominator_is_na_and_unknown_is_not_negative():
    _,_,c=data();x={'status':'NOT_RUN_NO_ADMISSIBLE_INPUT','timeline':[]}
    a=h.assess(c,x,outcome(c,'UNKNOWN'),observed_through='2026-10-15')
    assert not a['eligible_for_scoped_metric']
    m=h.summarize([x],[a])['metrics'];assert m['precision']is m['recall']is None and m['negative_denominator']==0


@pytest.mark.parametrize('label,field,value,reason',[
 ('POSITIVE','target',{'product':'other'},'TARGET'),
 ('POSITIVE','occurrence','2023-01','12_36'),
 ('NEGATIVE','coverage_end','2020-01-01','COMPLETE_WINDOW'),
 ('POSITIVE','status','UNVERIFIED','UNVERIFIED')])
def test_wrong_target_date_or_unproven_negative_cannot_score(label,field,value,reason):
    _,_,c=data();o=outcome(c,label);o[field]=value
    r=h.assess(c,{'status':'EXECUTED_BACKTEST','timeline':[]},o,observed_through='2026-10-15')
    assert not r['eligible_for_scoped_metric']and any(reason in x for x in r['held_reasons'])


def test_insufficient_period_scope_blocks_metric_even_when_shortage_is_real():
    _,_,c=data();c['metric_blockers']=['SUMMER_INPUT_NOT_QUALIFIED_WINTER_SUPPLY']
    r=h.assess(c,{'status':'EXECUTED_BACKTEST','timeline':[]},outcome(c),observed_through='2026-10-15')
    assert not r['eligible_for_scoped_metric'] and r['FN']==0


def test_counterexample_s3_after_report_is_not_a_leading_success():
    _,_,c=data();c['cutoff']='2021-12-01T00:00:00Z'
    r=h.assess(c,{'status':'EXECUTED_BACKTEST','timeline':[{'cutoff':c['cutoff'],'explicit_S3_candidates':[{'target':c['target']}]}]},outcome(c),observed_through='2026-10-15')
    assert not r['eligible_for_scoped_metric'] and not r['S3_before_in_scope_report'] and r['TP']==0


def test_correct_scoped_counterexample_scoring_does_not_relabel_development_holdout():
    _,_,c=data();o=outcome(c);x={'status':'EXECUTED_BACKTEST','timeline':[{'cutoff':c['cutoff'],'explicit_S3_candidates':[{'target':c['target']}]}]}
    r=h.assess(c,x,o,observed_through='2026-10-15')
    assert r['TP']==1 and r['S3_before_in_scope_report'] and not r['independent_holdout_eligible']


def test_restore_comparison_ignores_only_execution_uuid_and_detects_evidence_changes():
    import importlib.util
    from pathlib import Path
    p=Path(__file__).resolve().parents[1]/'tools/v4_historical_backtest.py'
    spec=importlib.util.spec_from_file_location('historical_runner',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    x={'results':[{'timeline':[{'engine':{'batch_id':'early-'+'a'*32,'input_sha256':'original','candidates':[]}}]}],'metrics':{'FN':0}}
    y=deepcopy(x);y['results'][0]['timeline'][0]['engine']['batch_id']='early-'+'b'*32
    assert m.decision_sha(x)==m.decision_sha(y) and x['results'][0]['timeline'][0]['engine']['batch_id']=='early-'+'a'*32
    y['results'][0]['timeline'][0]['engine']['input_sha256']='other'
    assert m.decision_sha(x)!=m.decision_sha(y)
