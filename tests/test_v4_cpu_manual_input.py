"""Explicit actual input remains distinct from verified scheduled execution."""

import pytest

from bct.v4 import cpu_automation as q,cpu_operations as op
from test_v4_cpu_operations import schedule_context
from test_v4_cpu_automation import document,Extractor


def manual_context():
    value=schedule_context();value['event_name']='workflow_dispatch'
    value['event']={'inputs':{'purpose':'manual-research','acquisition_run':'2'}}
    return value


def test_explicit_manual_read_can_progress_with_scheduled_false_and_no_clock(tmp_path):
    context=manual_context();proof=op.verified_manual_input(context)
    assert proof['verified'] and proof['scheduled'] is False and proof['seven_day_start'] is None
    ledger=q.open_queue(tmp_path);doc,raw=document();q.enqueue(ledger,doc,raw,{})
    from test_v4_cpu_analysis_pipeline import bound_context
    result=op.observe(ledger,trigger='MANUAL_ACTUAL_INPUT_PENDING_PRIVATE_PUBLICATION',execute=True,
        extractor=Extractor(),manual_context=context,persistence_required=True,analysis_context=bound_context(tmp_path/'context',doc,raw))
    assert result['new_CPU_windows']==1 and result['actually_read_new_characters']==len(doc['body'])
    assert result['execution_mode']=='MANUAL_ACTUAL_INPUT' and result['scheduled'] is False
    assert not result['scheduled_execution_verified'] and result['seven_day_start'] is None
    assert result['complete_analyzed_new_CPU_documents']==1
    ledger.close()


@pytest.mark.parametrize('change',[lambda c:c['event']['inputs'].update(purpose='runtime-verify'),
    lambda c:c['event']['inputs'].update(acquisition_run='9'),
    lambda c:c['acquisition_run'].update(head_branch='dev'),
    lambda c:c['rss_run'].update(run_attempt=2),
    lambda c:c.update(acquisition_job_log='RSS_RUN_ID: 9\n')])
def test_manual_input_requires_real_exact_upstream_chain(change):
    value=manual_context();change(value)
    with pytest.raises(ValueError,match='NOT_VERIFIED'):op.verified_manual_input(value)


def test_scheduled_trigger_cannot_consume_a_different_upstream_attempt():
    value=schedule_context();value['acquisition_run']['run_attempt']=2
    with pytest.raises(ValueError,match='NOT_VERIFIED'):op.verified_schedule(value)


def test_model_window_alone_does_not_open_observation_after_analysis_error(tmp_path,monkeypatch):
    from test_v4_cpu_analysis_pipeline import adapter
    def broken(*args,**kwargs):raise RuntimeError('known test failure')
    adapter(monkeypatch,broken)
    ledger=q.open_queue(tmp_path);doc,raw=document();q.enqueue(ledger,doc,raw,{})
    result=op.observe(ledger,trigger='SYNTHETIC_TEST',execute=True,extractor=Extractor(),schedule_context=schedule_context())
    assert result['successful_new_CPU_windows']==1 and result['analysis_status']=='ERROR_PROGRESS_PRESERVED'
    assert result['complete_analyzed_new_CPU_documents']==0 and result['seven_day_start'] is None
    assert not op.eligible_observation(result)
    assert len(q.events(ledger,'CPU_QUEUE_WINDOW_RESULT'))==1
    ledger.close()
