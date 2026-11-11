"""Public writer receipts expose current persisted processing without originals."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from bct.v4.store import Ledger, file_sha


DOC = '855f7732-e05f-4832-b421-0a84e0ca736b'


def input_state(tmp_path, *, observation=True):
    ledger = Ledger(tmp_path / 'state')
    with ledger.db:
        ledger.db.execute("INSERT INTO metadata VALUES('cpu_source_separated_format','bct-source-separated-cpu-1')")
        ledger.db.execute("INSERT INTO metadata VALUES('cpu_queue_format','bct-cpu-research-queue-1')")
        ledger.event('CPU_ANALYSIS_RESULT', {
            'document_id': DOC, 'body_sha256': 'a' * 64, 'raw_sha256': 'b' * 64,
            'source_version': 'a' * 64, 'review_state': 'READ_EVIDENCE_HOLD',
            'read_state': 'READ_COMPLETE', 'source_validation': 'EXACT_NATIVE_AND_BODY_HASHES',
            'reason_code': 'MISSING_TARGET_EVIDENCE', 'missing_fields': ['supply_pool'],
            'CPU_windows_total': 2, 'CPU_windows_success': 2, 'CPU_windows_failed': 0,
            'CPU_windows_unread': 0, 'strict_pair_count': None,
            # Private data is deliberately not copied into the public projection.
            'body': 'PRIVATE ORIGINAL MUST NOT LEAK', 'product': 'Private source surface',
        })
        if observation:
            ledger.event('CPU_OPERATION_OBSERVATION', {
                'finished_at': '2026-11-11T12:00:00+00:00',
                'consumer_run_id': 103, 'consumer_attempt': 1,
                'CPU_documents_processed': 1, 'new_CPU_windows': 2,
                'successful_new_CPU_windows': 2, 'actually_read_new_characters': 520,
                'CPU_pending': 3, 'review_pending_windows': 2,
                'schedule_proof': {'RSS_run_id': 101, 'acquisition_run_id': 102,
                                   'RSS_actual_created_at': '2026-11-11T11:40:00+00:00'},
                'queue': {'failed_windows': 0, 'isolated_imports': 1},
            })
    ledger.close()
    path = tmp_path / 'state/v4.sqlite3'
    acknowledgment = {'commit': 'c' * 40, 'remote_restore_verified': True,
        'persistence_receipt': {'version': 'bct-private-persistence-1',
            'checkpoint_commit': 'd' * 40, 'sqlite_sha256': file_sha(path),
            'remote_restored_at': '2026-11-11T12:01:00+00:00'}}
    proof = {'restored': True, 'tables': 8, 'sqlite_sha256': file_sha(path)}
    producer = {'run_id': 103, 'run_attempt': 1, 'workflow_sha': 'e' * 40,
                'execution_sha': 'f' * 40, 'lineage_root': '1' * 40, 'ack_sequence': 4}
    acknowledgment['persistence_receipt'].update(publisher_run_id=103, publisher_attempt=1,
        publisher_workflow_sha='e' * 40, publisher_execution_sha='f' * 40)
    return path, acknowledgment, proof, producer


def project(tmp_path, *, observation=True):
    from bct.v4.public_research import build_snapshot
    path, acknowledgment, proof, producer = input_state(tmp_path, observation=observation)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        return build_snapshot(db, acknowledgment, proof, producer)


def test_public_projection_is_generation_bound_and_does_not_export_private_text(tmp_path):
    from bct.v4.public_research import validate_snapshot
    public = project(tmp_path)
    assert validate_snapshot(public) == public
    encoded = json.dumps(public)
    assert 'PRIVATE ORIGINAL' not in encoded and 'Private source surface' not in encoded
    assert public['generation']['private_commit'] == 'c' * 40
    assert public['clocks']['data_at'] == '2026-11-11T12:00:00+00:00'
    assert public['clocks']['last_read_at'] == public['clocks']['data_at']
    assert public['counts']['new_CPU_windows'] == 2
    assert public['counts']['independent_pairs'] is None
    assert public['analysis']['states']['READ_EVIDENCE_HOLD'] == 1
    assert public['trace'][0]['document_id'] == DOC
    assert public['trace'][0]['source_verification'] == 'EXACT_NATIVE_AND_BODY_HASHES'
    assert public['trace'][0]['read_state'] == 'READ_COMPLETE'
    assert len(public['trace'][0]['analysis_sha256']) == 64
    assert public['trace'][0]['model'] is None  # absent metadata is never invented


def test_trace_bound_retains_latest_update_of_an_older_source(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, ack, proof, producer = input_state(tmp_path)
    ledger = Ledger(path.parent)
    original = json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='CPU_ANALYSIS_RESULT'").fetchone()[0])
    with ledger.db:
        for index in range(100):
            ledger.event('CPU_ANALYSIS_RESULT', {**original, 'document_id': 'v4doc-' + format(index, '016x')})
        ledger.event('CPU_ANALYSIS_RESULT', {**original, 'reason_code': 'GRAPH_CONTEXT_VERSION_MISMATCH',
                                           'review_state': 'GRAPH_CONTEXT_PENDING'})
    ledger.close(); ack['persistence_receipt']['sqlite_sha256'] = proof['sqlite_sha256'] = file_sha(path)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        public = build_snapshot(db, ack, proof, producer)
    assert public['analysis']['trace_total'] == 101 and public['analysis']['trace_truncated']
    assert public['trace'][-1]['document_id'] == DOC
    assert public['trace'][-1]['reason_code'] == 'GRAPH_CONTEXT_VERSION_MISMATCH'


def test_bootstrap_does_not_relabel_old_research_as_today(tmp_path):
    public = project(tmp_path, observation=False)
    assert public['clocks']['persisted_at'] == '2026-11-11T12:01:00+00:00'
    assert public['clocks']['data_at'] is None and public['clocks']['last_read_at'] is None
    assert public['counts']['new_CPU_windows'] == 0


def test_public_schema_rejects_unknown_nested_fields_and_tampered_hash(tmp_path):
    from bct.v4.public_research import validate_snapshot, seal
    public = project(tmp_path)
    secret = deepcopy(public)
    secret['trace'][0]['quote'] = 'private original'
    with pytest.raises(ValueError, match='FIELDS'):
        validate_snapshot(seal(secret))
    changed = deepcopy(public)
    changed['counts']['new_CPU_windows'] += 1
    with pytest.raises(ValueError, match='HASH'):
        validate_snapshot(changed)


def test_private_ack_and_new_process_restore_must_match_exact_database_generation(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, acknowledgment, proof, producer = input_state(tmp_path)
    proof['sqlite_sha256'] = '0' * 64
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        with pytest.raises(ValueError, match='GENERATION'):
            build_snapshot(db, acknowledgment, proof, producer)


def test_matching_ack_and_restore_claim_cannot_describe_a_different_open_database(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, acknowledgment, proof, producer = input_state(tmp_path)
    acknowledgment['persistence_receipt']['sqlite_sha256'] = proof['sqlite_sha256'] = '0' * 64
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        with pytest.raises(ValueError, match='GENERATION'):
            build_snapshot(db, acknowledgment, proof, producer)


def test_public_document_ids_cannot_be_used_to_smuggle_source_strings(tmp_path):
    from bct.v4.public_research import validate_snapshot, seal
    public = project(tmp_path)
    public['trace'][0]['document_id'] = 'ghp_' + 's' * 36
    with pytest.raises(ValueError, match='DOCUMENT_ID'):
        validate_snapshot(seal(public))


def test_hash_mismatch_is_a_per_source_hold_not_a_failed_publication(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, ack, proof, producer = input_state(tmp_path)
    ledger = Ledger(path.parent)
    with ledger.db:
        ledger.event('CPU_ANALYSIS_RESULT', {
            'document_id': '955f7732-e05f-4832-b421-0a84e0ca736b',
            'body_sha256': '2' * 64, 'raw_sha256': '3' * 64, 'source_version': '4' * 64,
            'review_state': 'SOURCE_VERIFICATION_PENDING', 'read_state': 'UNREAD',
            'source_validation': 'NOT_VERIFIED', 'reason_code': 'SOURCE_VERSION_OR_HASH_MISMATCH',
            'missing_fields': [], 'CPU_windows_total': 1, 'CPU_windows_success': 0,
            'CPU_windows_failed': 0, 'CPU_windows_unread': 1, 'strict_pair_count': None})
    ledger.close(); ack['persistence_receipt']['sqlite_sha256'] = proof['sqlite_sha256'] = file_sha(path)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        public = build_snapshot(db, ack, proof, producer)
    assert len(public['trace']) == 2
    held = public['trace'][1]
    assert held['source_version'] != held['body_sha256']
    assert held['reason_code'] == 'SOURCE_VERSION_OR_HASH_MISMATCH'
    assert held['read_state'] == 'UNREAD' and held['window_counts']['unread'] == 1


def test_recovery_ack_preserves_last_read_but_does_not_claim_old_inference_again(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, ack, proof, producer = input_state(tmp_path)
    producer = {**producer, 'run_id': 104}
    ack['persistence_receipt']['publisher_run_id'] = 104
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        public = build_snapshot(db, ack, proof, producer)
    assert public['counts']['new_CPU_windows'] == 0
    assert public['last_read_batch']['new_CPU_windows'] == 2
    assert public['last_read_batch']['consumer_run_id'] == 103
    assert public['generation']['producer_run_id'] == 104


def test_analysis_exception_has_per_source_failed_pointer_and_never_becomes_hold(tmp_path):
    from bct.v4.public_research import build_snapshot
    path, ack, proof, producer = input_state(tmp_path)
    ledger = Ledger(path.parent)
    with ledger.db:
        ledger.event('CPU_ANALYSIS_FAILURE', {'document_id': DOC, 'body_sha256': 'a' * 64,
            'raw_sha256': 'b' * 64, 'source_version': 'a' * 64,
            'reason_code': 'ANALYSIS_RUNTIME_FAILED', 'review_state': 'FAILED'})
    ledger.close(); ack['persistence_receipt']['sqlite_sha256'] = proof['sqlite_sha256'] = file_sha(path)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        public = build_snapshot(db, ack, proof, producer)
    assert public['analysis']['states'] == {'FAILED': 1}
    assert public['trace'][0]['reason_code'] == 'ANALYSIS_RUNTIME_FAILED'
    assert public['trace'][0]['window_counts']['total'] is None
