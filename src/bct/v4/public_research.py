"""Small public projection of an acknowledged source-separated research state.

The private ledger is never a dashboard input. Only fixed counts, enums and
opaque source identifiers survive this projection; no originals or entities do.
"""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from bct.objective_lock import require_objective, stamp_export
from .store import file_sha

FORMAT = 'bct-public-research-1'
STATES = {'UNREAD', 'PARTIAL', 'FAILED', 'SOURCE_VERIFICATION_PENDING',
          'READ_EVIDENCE_HOLD', 'NO_VALIDATED_EVENT', 'RESEARCH_FORECAST_REVIEW'}
MISSING = {'product', 'specification', 'region', 'customer_group', 'supply_pool',
           'quantity', 'unit', 'need_period', 'ready_period', 'need_time', 'ready_time',
           'independence', 'qualified_supply', 'customer_need_period', 'OTHER_REQUIRED_EVIDENCE'}
REASONS = {'MISSING_TARGET_EVIDENCE', 'UNREAD', 'PARTIAL', 'FAILED',
           'SOURCE_VERIFICATION_PENDING', 'NO_VALIDATED_EVENT',
           'READ_EVIDENCE_HOLD', 'RESEARCH_FORECAST_REVIEW', 'OTHER_RESEARCH_HOLD'}
REASONS.update({'CPU_NOT_READ', 'CPU_READ_INCOMPLETE', 'CPU_WINDOW_VALIDATION_FAILED', 'CPU_CONTEXT_HELD',
                'SOURCE_ORIGINAL_NOT_AVAILABLE', 'SOURCE_VERSION_OR_HASH_MISMATCH', 'SOURCE_PROVENANCE_NOT_VERIFIED',
                'NO_SOURCE_BOUND_EVENT_IN_READ_SCOPE', 'CPU_ENTITY_VALIDATION_REVIEW_PENDING',
                'CPU_ENTITY_ONLY_SEMANTICS_PENDING', 'TARGET_FIELDS_UNKNOWN', 'QUALIFIED_SUPPLY_SCOPE_UNKNOWN',
                'INDEPENDENT_COUNTERPART_NOT_VERIFIED', 'FORECAST_INPUT_NOT_ELIGIBLE',
                'EXISTING_STRICT_FORECAST_CANDIDATE_RESEARCH_ONLY', 'ANALYSIS_DEPENDENCY_FAILED', 'ANALYSIS_RUNTIME_FAILED'})
ISSUES = {'UPSTREAM_BODY_NOT_AVAILABLE_NO_REFETCH', 'UPSTREAM_VERSION_AMBIGUOUS',
          'PRIVATE_ARCHIVAL_OR_PRIVACY_UNREVIEWED', 'SOURCE_PUBLICATION_OR_PROVENANCE_HELD',
          'NATIVE_OR_BODY_HASH_MISMATCH', 'NATIVE_TO_BODY_MISMATCH', 'OTHER_SOURCE_HOLD'}
COUNT_FIELDS = {'new_CPU_documents', 'new_CPU_windows', 'successful_new_CPU_windows',
                'new_CPU_characters', 'pending_windows', 'failed_windows', 'held_inputs',
                'review_pending_windows', 'preserved_windows', 'completed_body_keys',
                'independent_pairs', 'analysis_runtime_failures', 'complete_analyzed_new_CPU_documents'}
ROOT_FIELDS = {'format', 'objective_version', 'objective_sha256', 'generation', 'clocks',
               'counts', 'analysis', 'trace', 'source_issues', 'proof', 'snapshot_sha256', 'last_read_batch'}
GENERATION_FIELDS = {'private_commit', 'checkpoint_commit', 'sqlite_sha256', 'producer_run_id',
                     'producer_attempt', 'workflow_sha', 'execution_sha', 'RSS_run_id', 'acquisition_run_id',
                     'lineage_root', 'ack_sequence'}
CLOCK_FIELDS = {'last_collection_at', 'last_read_at', 'persisted_at', 'data_at'}
TRACE_FIELDS = {'document_id', 'body_sha256', 'raw_sha256', 'source_version', 'review_state',
                'reason_code', 'missing_fields', 'source_verification', 'read_state', 'window_counts'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def seal(value):
    public = stamp_export({k: v for k, v in value.items() if k != 'snapshot_sha256'})
    return {**public, 'snapshot_sha256': digest(public)}


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('PUBLIC_RESEARCH_FIELDS')


def hexadecimal(value, length):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', value):
        raise ValueError('PUBLIC_RESEARCH_HASH_FIELD')


def number(value, *, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not int or not 0 <= value <= 10**12:
        raise ValueError('PUBLIC_RESEARCH_COUNT')


def timestamp(value, *, nullable=True):
    if nullable and value is None:
        return
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    except (ValueError, AttributeError, TypeError):
        raise ValueError('PUBLIC_RESEARCH_TIMESTAMP') from None


def document_id(value):
    # Actual RSS UUIDs and existing hash-addressed source namespaces only.
    if not isinstance(value, str) or not re.fullmatch(
            r'(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|'
            r'(?:v4doc|stage4doc|link-primary|link-reference|new-source|target|source)-[0-9a-f]{16,64})', value):
        raise ValueError('PUBLIC_RESEARCH_DOCUMENT_ID')


def validate_snapshot(public):
    exact(public, ROOT_FIELDS)
    require_objective(public)
    if public['format'] != FORMAT:
        raise ValueError('PUBLIC_RESEARCH_FORMAT')
    if public['snapshot_sha256'] != digest({k: v for k, v in public.items() if k != 'snapshot_sha256'}):
        raise ValueError('PUBLIC_RESEARCH_HASH')
    generation = public['generation']; exact(generation, GENERATION_FIELDS)
    for key in ('private_commit', 'checkpoint_commit', 'workflow_sha', 'execution_sha', 'lineage_root'):
        hexadecimal(generation[key], 40)
    hexadecimal(generation['sqlite_sha256'], 64)
    for key in ('producer_run_id', 'producer_attempt', 'RSS_run_id', 'acquisition_run_id', 'ack_sequence'):
        number(generation[key], nullable=key in ('RSS_run_id', 'acquisition_run_id'))
    if generation['producer_run_id'] < 1 or generation['producer_attempt'] < 1 or generation['ack_sequence'] < 1:
        raise ValueError('PUBLIC_RESEARCH_PRODUCER')
    exact(public['clocks'], CLOCK_FIELDS)
    for key, value in public['clocks'].items():
        timestamp(value, nullable=key != 'persisted_at')
    exact(public['counts'], COUNT_FIELDS)
    for key, value in public['counts'].items():
        number(value, nullable=key == 'independent_pairs')
    exact(public['last_read_batch'], {'consumer_run_id', 'consumer_attempt', 'RSS_run_id', 'acquisition_run_id',
                                     'new_CPU_documents', 'new_CPU_windows', 'successful_new_CPU_windows', 'new_CPU_characters'})
    for key, value in public['last_read_batch'].items():
        number(value, nullable=key in ('consumer_run_id', 'consumer_attempt', 'RSS_run_id', 'acquisition_run_id'))
    exact(public['analysis'], {'states', 'trace_total', 'trace_truncated', 'status'})
    if public['analysis']['status'] not in ('ERROR_PROGRESS_PRESERVED', 'ANALYZED_READ', 'NO_COMPLETE_NEW_ANALYZED_READ'):
        raise ValueError('PUBLIC_RESEARCH_ANALYSIS_STATUS')
    if not isinstance(public['analysis']['states'], dict) or set(public['analysis']['states']) - STATES:
        raise ValueError('PUBLIC_RESEARCH_ANALYSIS_STATES')
    for value in public['analysis']['states'].values():
        number(value)
    number(public['analysis']['trace_total'])
    if type(public['analysis']['trace_truncated']) is not bool:
        raise ValueError('PUBLIC_RESEARCH_ANALYSIS_TRACE')
    if not isinstance(public['trace'], list) or len(public['trace']) > 100:
        raise ValueError('PUBLIC_RESEARCH_TRACE_LIMIT')
    total = public['analysis']['trace_total']
    if (sum(public['analysis']['states'].values()) != total or len(public['trace']) != min(total, 100)
            or public['analysis']['trace_truncated'] != (total > 100)):
        raise ValueError('PUBLIC_RESEARCH_ANALYSIS_TRACE')
    for row in public['trace']:
        exact(row, TRACE_FIELDS); document_id(row['document_id'])
        for key in ('body_sha256', 'raw_sha256', 'source_version'):
            hexadecimal(row[key], 64)
        mismatch = row['source_version'] != row['body_sha256']
        if ((mismatch and not (row['review_state'] == 'SOURCE_VERIFICATION_PENDING'
                              and row['reason_code'] == 'SOURCE_VERSION_OR_HASH_MISMATCH'))
                or row['review_state'] not in STATES
                or row['reason_code'] not in REASONS
                or row['source_verification'] not in ('NOT_VERIFIED', 'EXACT_NATIVE_AND_BODY_HASHES')
                or row['read_state'] not in ('UNREAD', 'PARTIAL', 'FAILED', 'READ_COMPLETE')
                or not isinstance(row['missing_fields'], list)
                or set(row['missing_fields']) - MISSING):
            raise ValueError('PUBLIC_RESEARCH_TRACE_STATUS')
        exact(row['window_counts'], {'total', 'success', 'failed', 'unread'})
        unknown = all(value is None for value in row['window_counts'].values())
        for count in row['window_counts'].values():
            number(count, nullable=unknown and row['reason_code'] == 'ANALYSIS_RUNTIME_FAILED')
        if not unknown and row['window_counts']['total'] != sum(row['window_counts'][key] for key in ('success', 'failed', 'unread')):
            raise ValueError('PUBLIC_RESEARCH_TRACE_WINDOW_COUNTS')
    if not isinstance(public['source_issues'], list) or len(public['source_issues']) > len(ISSUES):
        raise ValueError('PUBLIC_RESEARCH_SOURCE_ISSUES')
    for item in public['source_issues']:
        exact(item, {'reason_code', 'count'})
        if item['reason_code'] not in ISSUES:
            raise ValueError('PUBLIC_RESEARCH_SOURCE_ISSUE_CODE')
        number(item['count'])
    exact(public['proof'], {'remote_restore_verified', 'new_process_restore_verified', 'restored_tables'})
    if public['proof'] != {'remote_restore_verified': True, 'new_process_restore_verified': True, 'restored_tables': 8}:
        raise ValueError('PUBLIC_RESEARCH_RESTORE_PROOF')
    return public


def events(db, kind):
    return [json.loads(row[0]) for row in db.execute('SELECT payload FROM events WHERE kind=? ORDER BY seq', (kind,))]


def build_snapshot(db, acknowledgment, restored, producer):
    receipt = acknowledgment.get('persistence_receipt', {})
    if (acknowledgment.get('remote_restore_verified') is not True or restored.get('restored') is not True
            or restored.get('tables') != 8 or receipt.get('version') != 'bct-private-persistence-1'
            or receipt.get('sqlite_sha256') != restored.get('sqlite_sha256')):
        raise ValueError('PUBLIC_RESEARCH_GENERATION_NOT_RESTORED')
    producer = {**producer, 'run_id': receipt.get('publisher_run_id'),
                'run_attempt': receipt.get('publisher_attempt'),
                'workflow_sha': receipt.get('publisher_workflow_sha'),
                'execution_sha': receipt.get('publisher_execution_sha')}
    databases = db.execute('PRAGMA database_list').fetchall()
    database = next((Path(row[2]) for row in databases if row[1] == 'main' and row[2]), None)
    if database is None or file_sha(database) != receipt['sqlite_sha256']:
        raise ValueError('PUBLIC_RESEARCH_GENERATION_DATABASE_MISMATCH')
    for table in ('blobs', 'documents', 'captures', 'readings', 'runs', 'firsts'):
        if db.execute('SELECT count(*) FROM ' + table).fetchone()[0]:
            raise ValueError('PUBLIC_RESEARCH_SOURCE_SEPARATED_REQUIRED')
    observations = events(db, 'CPU_OPERATION_OBSERVATION'); latest = observations[-1] if observations else {}
    actual_reads = [row for row in observations if row.get('new_CPU_windows', 0) > 0
                    and row.get('actually_read_new_characters', 0) > 0]
    schedule = latest.get('schedule_proof', {})
    analyses = {}
    for kind, payload in db.execute("SELECT kind,payload FROM events WHERE kind IN ('CPU_ANALYSIS_RESULT','CPU_ANALYSIS_FAILURE') ORDER BY seq"):
        record = json.loads(payload)
        if kind == 'CPU_ANALYSIS_FAILURE':
            record = {**record, 'read_state': record.get('read_state', 'FAILED'),
                      'source_validation': 'NOT_VERIFIED', 'missing_fields': [], 'strict_pair_count': None}
        analyses[(record['document_id'], record['body_sha256'])] = record
    trace = []
    for record in analyses.values():
        trace.append({'document_id': record['document_id'], 'body_sha256': record['body_sha256'],
                      'raw_sha256': record['raw_sha256'], 'source_version': record['source_version'],
                      'review_state': record['review_state'],
                      'reason_code': record['reason_code'] if record['reason_code'] in REASONS else 'OTHER_RESEARCH_HOLD',
                      'missing_fields': sorted({field if field in MISSING else 'OTHER_REQUIRED_EVIDENCE'
                                                for field in record.get('missing_fields', [])}),
                      'source_verification': record.get('source_validation', 'NOT_VERIFIED'),
                      'read_state': record['read_state'],
                      'window_counts': {name: record.get('CPU_windows_' + field) for name, field in
                                        [('total', 'total'), ('success', 'success'), ('failed', 'failed'), ('unread', 'unread')]}})
    imports = {row['item_key']: row for row in events(db, 'CPU_QUEUE_IMPORT')}
    issues = Counter(row.get('reason') if row.get('reason') in ISSUES else 'OTHER_SOURCE_HOLD'
                     for row in imports.values() if row.get('status') == 'HELD_ISOLATED')
    pair_counts = [row.get('strict_pair_count') for row in analyses.values()]
    # A per-document positive count is not a deduplicated global pair count.
    pairs = 0 if pair_counts and all(value == 0 for value in pair_counts) else None
    this_producer = (latest.get('consumer_run_id'), latest.get('consumer_attempt')) == (producer['run_id'], producer['run_attempt'])
    last_read = actual_reads[-1] if actual_reads else {}
    def batch(row):
        return {'new_CPU_documents': row.get('CPU_documents_processed', 0), 'new_CPU_windows': row.get('new_CPU_windows', 0),
                'successful_new_CPU_windows': row.get('successful_new_CPU_windows', 0),
                'new_CPU_characters': row.get('actually_read_new_characters', 0)}
    current_counts = batch(latest) if this_producer else batch({})
    public = seal({'format': FORMAT,
        'generation': {'private_commit': acknowledgment['commit'], 'checkpoint_commit': receipt['checkpoint_commit'],
                       'sqlite_sha256': receipt['sqlite_sha256'], 'producer_run_id': producer['run_id'],
                       'producer_attempt': producer['run_attempt'], 'workflow_sha': producer['workflow_sha'],
                       'execution_sha': producer['execution_sha'], 'RSS_run_id': schedule.get('RSS_run_id'),
                       'acquisition_run_id': schedule.get('acquisition_run_id'),
                       'lineage_root': producer['lineage_root'], 'ack_sequence': producer['ack_sequence']},
        'clocks': {'last_collection_at': schedule.get('RSS_actual_created_at'),
                   'last_read_at': actual_reads[-1]['finished_at'] if actual_reads else None,
                   'persisted_at': receipt['remote_restored_at'], 'data_at': latest.get('finished_at')},
        'counts': {**current_counts,
                   'pending_windows': latest.get('CPU_pending', 0),
                   'failed_windows': latest.get('queue', {}).get('failed_windows', 0),
                   'held_inputs': sum(issues.values()), 'review_pending_windows': latest.get('review_pending_windows', 0),
                   'preserved_windows': len({row['key'] for row in events(db, 'CPU_RESUME_WINDOW')}),
                   'completed_body_keys': len({row['body_key'] for row in events(db, 'CPU_QUEUE_LEGACY_COMPLETE')}),
                   'independent_pairs': pairs, 'analysis_runtime_failures': latest.get('analysis_runtime_failures', 0),
                   'complete_analyzed_new_CPU_documents': latest.get('complete_analyzed_new_CPU_documents', 0) if this_producer else 0},
        'last_read_batch': {**batch(last_read), 'consumer_run_id': last_read.get('consumer_run_id'),
                            'consumer_attempt': last_read.get('consumer_attempt'),
                            'RSS_run_id': last_read.get('schedule_proof', {}).get('RSS_run_id'),
                            'acquisition_run_id': last_read.get('schedule_proof', {}).get('acquisition_run_id')},
        'analysis': {'states': dict(Counter(row['review_state'] for row in analyses.values())),
                     'trace_total': len(trace), 'trace_truncated': len(trace) > 100,
                     'status': latest.get('analysis_status', 'NO_COMPLETE_NEW_ANALYZED_READ')},
        'trace': trace[-100:], 'source_issues': [{'reason_code': key, 'count': value} for key, value in sorted(issues.items())],
        'proof': {'remote_restore_verified': True, 'new_process_restore_verified': True, 'restored_tables': 8}})
    return validate_snapshot(public)
