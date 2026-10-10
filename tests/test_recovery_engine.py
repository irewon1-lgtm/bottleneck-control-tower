import time
from bct.recovery_engine import run, STAGES


def executor(calls, stage, fail=None):
    def execute(attempt):
        calls.append(stage)
        return {'status': 'FAIL' if fail and fail() else 'PASS', 'actual_execution': True,
                'criteria_met': True, 'execution_id': attempt + ':' + str(stage),
                'evidence': 'actual fixture executor', 'reason': 'fixture failure'}
    return execute


def test_fix_restarts_zero_and_requires_three_independent_cycles(tmp_path):
    calls = [];version = [0]
    stages = {s: executor(calls, s, (lambda: version[0] == 0) if s == 3 else None) for s in STAGES}
    def repair(result):
        assert result['stage'] == 3;version[0] += 1
    state = run(stages, fingerprint=lambda: version[0], output=tmp_path/'checkpoint.json', repair=repair)
    assert calls[:5] == [0, 1, 2, 3, 0]
    assert state['status'] == 'PASS' and state['clean_streak'] == 3
    assert len(state['attempts']) == 4
    assert state['prediction_performance'] == 'UNVERIFIED'


def test_unchanged_failure_is_not_retried(tmp_path):
    calls = [];stages = {s: executor(calls, s, (lambda: True) if s == 1 else None) for s in STAGES}
    state = run(stages, fingerprint=lambda:'same', output=tmp_path/'checkpoint.json', repair=lambda _:None)
    assert state['status'] == 'FAIL' and calls == [0, 1]
    again = run(stages, fingerprint=lambda:'same', output=tmp_path/'checkpoint.json')
    assert again['status'] == 'FAIL' and calls == [0, 1]


def test_missing_stage_deadline_and_fabricated_pass_stay_blocked(tmp_path):
    calls = []
    state = run({0:executor(calls, 0)}, fingerprint=lambda:'same', output=tmp_path/'missing.json')
    assert state['status'] == 'BLOCKED' and state['last_stage'] == 1
    state = run({}, fingerprint=lambda:'same', output=tmp_path/'time.json', deadline=time.monotonic()-1)
    assert state['status'] == 'BLOCKED' and state['reason'] == 'RUNNER_DEADLINE'
    state = run({0:lambda _: {'status':'PASS'}}, fingerprint=lambda:'same', output=tmp_path/'fake.json')
    assert state['status'] == 'FAIL' and state['reason'] == 'INVALID_OR_REUSED_EXECUTION_RECEIPT'


def test_reused_success_cannot_count_as_new_operating_execution(tmp_path):
    stages = {s:lambda _,s=s: {'status':'PASS','actual_execution':True,'criteria_met':True,
                               'execution_id':'cached-'+str(s),'evidence':'old'} for s in STAGES}
    state = run(stages, fingerprint=lambda:'same', output=tmp_path/'checkpoint.json')
    assert state['status'] == 'FAIL' and state['clean_streak'] == 0
    assert state['last_stage'] == 0 and len(state['attempts']) == 2


def test_three_distinct_runners_are_required_and_duplicate_run_never_increments(tmp_path):
    calls = []
    stages = {s: executor(calls, s) for s in STAGES}
    output = tmp_path/'external-cycles.json'
    for runner, expected in [('run1',1), ('run1',1), ('run2',2), ('run3',3)]:
        state = run(stages, fingerprint=lambda:'verified-code', output=output,
                    single_cycle=True, execution_identity=runner)
        assert state['clean_streak'] == expected
        assert len(state['attempts']) == expected
    assert len(calls) == 3 * len(STAGES) and state['status'] == 'PASS'


def test_missing_runner_identity_and_a_changed_code_cannot_extend_an_old_clean_streak(tmp_path):
    import pytest
    stages = {s: executor([], s) for s in STAGES}
    output = tmp_path/'external-cycles.json'
    with pytest.raises(ValueError, match='runner execution identity'):
        run(stages, fingerprint=lambda:'version1', output=output, single_cycle=True)
    run(stages, fingerprint=lambda:'version1', output=output, single_cycle=True, execution_identity='run1')
    state = run(stages, fingerprint=lambda:'version2', output=output,
                single_cycle=True, execution_identity='run2')
    assert state['clean_streak'] == 1 and state['status'] != 'PASS'


def test_verified_external_condition_change_restarts_zero_without_cached_pass(tmp_path):
    calls = []
    condition = [False]
    stages = {s: executor(calls, s, (lambda: not condition[0]) if s == 7 else None) for s in STAGES}
    output = tmp_path/'external-block.json'
    state = run(stages, fingerprint=lambda:'same-code', condition=lambda:condition[0],
                output=output, single_cycle=True, execution_identity='before')
    assert state['status'] == 'FAIL' and state['last_stage'] == 7
    length = len(calls)
    run(stages, fingerprint=lambda:'same-code', condition=lambda:condition[0],
        output=output, single_cycle=True, execution_identity='same-condition')
    assert len(calls) == length
    condition[0] = True
    state = run(stages, fingerprint=lambda:'same-code', condition=lambda:condition[0],
        output=output, single_cycle=True, execution_identity='condition-restored')
    assert calls[length] == 0 and state['clean_streak'] == 1
