"""Synthetic DEVELOPMENT input through q.work; not real independent pairs."""
from copy import deepcopy
import json

import pytest

from bct.v4 import cpu_automation as q, cpu_review as review, cpu_resume as resume
from bct.v4.adapters import MODEL, MODEL_REVISION
from bct.v4.store import sha
from test_precursor_source_pipeline import doc
from test_v4_cpu_review import source, receipts
from test_v4_q3_linkage_trace import timing_documents


def context_bundle(cache, sources, roots_by_document, *, complete=True):
    """Literal synthetic bundle following the producer's verified file contract."""
    cache.mkdir(); (cache/'documents').mkdir(); (cache/'raw').mkdir()
    manifest = {'format': 'bct-cpu-source-delta-1', 'graph_context_complete': complete,
                'required_graph_sources': [], 'unavailable_graph_sources': [], 'documents': [], 'files': {}}
    for n, (document, native) in enumerate(sources):
        metadata = json.dumps(document, sort_keys=True).encode()
        member = 'documents/'+str(n)+'.json'; raw_member = 'raw/'+document['raw_sha256']+'.html'
        (cache/member).write_bytes(metadata); (cache/raw_member).write_bytes(native)
        for name, data in [(member, metadata), (raw_member, native)]:
            manifest['files'][name] = {'bytes': len(data), 'sha256': sha(data)}
        roots = roots_by_document.get(document['document_id'], [])
        identity = {k: document[k] for k in ('document_id', 'origin_url', 'body_sha256', 'raw_sha256')}
        manifest['documents'].append({**identity, 'document_member': member, 'native_member': raw_member,
            'metadata_sha256': sha(metadata), 'source_kind': 'RSS', 'root_document_ids': roots})
        if roots: manifest['required_graph_sources'].append({**identity, 'root_document_ids': roots})
    return manifest


class EmptyAdvisoryModel:
    def __init__(self): self.calls = 0
    def extract_windows(self, document, windows, **_):
        self.calls += 1
        return {'status': 'PASS', 'model': MODEL, 'revision': MODEL_REVISION,
                'selected_windows': windows, 'input_sha256': sha(windows), 'spans': []}


def test_actual_worker_hook_delivers_synthetic_timing_pair_and_excludes_unrelated_root(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'now', lambda: '2026-10-08T17:30:00+00:00')
    buyer, supplier = timing_documents(); unrelated = doc('The company held its annual general meeting.', 'unrelated-root')
    sources = [source(d) for d in (buyer, supplier, unrelated)]
    buyer, supplier, unrelated = [d for d, _ in sources]
    roots = {buyer['document_id']: [buyer['document_id'], supplier['document_id']],
             supplier['document_id']: [buyer['document_id'], supplier['document_id']],
             unrelated['document_id']: [unrelated['document_id']]}
    cache = tmp_path/'cache'; manifest = context_bundle(cache, sources, roots)
    ledger = q.open_queue(tmp_path/'queue'); model = EmptyAdvisoryModel()
    with ledger.worker():
        for d, native in sources: q.enqueue(ledger, d, native, {})
        result = q.work(ledger, extractor=model, analysis_context={'cache': cache, 'manifest': manifest})
    rows = {r['document_id']: r for r in q.events(ledger, review.KIND)}
    assert result['new_windows'] == model.calls == 3
    assert rows[buyer['document_id']]['strict_pair_count'] == rows[supplier['document_id']]['strict_pair_count'] == 1
    assert rows[buyer['document_id']]['review_state'] == 'RESEARCH_FORECAST_REVIEW'
    assert rows[unrelated['document_id']]['strict_pair_count'] == rows[unrelated['document_id']]['strict_forecast_candidate_count'] == 0
    assert rows[unrelated['document_id']]['review_state'] == 'NO_VALIDATED_EVENT'
    assert all(r['S2'] == r['S3'] == 0 and r['semantic_review_status'] == 'PENDING_ATTRIBUTED_REVIEW' for r in rows.values())
    ledger.close()


@pytest.mark.parametrize('change', ['incomplete', 'missing', 'metadata', 'native', 'private', 'over_budget'])
def test_missing_or_changed_graph_originals_are_unknown_not_zero(tmp_path, change):
    buyer, supplier = timing_documents(); sources = [source(d) for d in (buyer, supplier)]
    root, _ = sources[0]; other, _ = sources[1]
    cache = tmp_path/'cache'; manifest = context_bundle(cache, sources,
        {root['document_id']: [root['document_id']], other['document_id']: [root['document_id']]})
    if change == 'incomplete': manifest['graph_context_complete'] = False
    elif change == 'missing': manifest['unavailable_graph_sources'] = [manifest['required_graph_sources'][1]]
    elif change == 'metadata': (cache/manifest['documents'][1]['document_member']).write_bytes(b'changed')
    elif change == 'native': (cache/manifest['documents'][1]['native_member']).write_bytes(b'changed')
    elif change == 'private':
        other['confidential'] = True; metadata = json.dumps(other, sort_keys=True).encode()
        entry = manifest['documents'][1]; (cache/entry['document_member']).write_bytes(metadata)
        entry['metadata_sha256'] = sha(metadata)
        manifest['files'][entry['document_member']] = {'bytes': len(metadata), 'sha256': sha(metadata)}
    else:
        # Do not drop the fourth dependency and accidentally erase a conflict.
        for n in range(3): manifest['required_graph_sources'].append({**manifest['required_graph_sources'][1], 'document_id': 'extra-'+str(n)})
    ledger = q.open_queue(tmp_path/'queue')
    with ledger.worker():
        q.enqueue(ledger, *sources[0], {})
        result = q.work(ledger, extractor=EmptyAdvisoryModel(), analysis_context={'cache': cache, 'manifest': manifest})
    row, = q.events(ledger, review.KIND)
    assert result['new_windows'] == 1 and row['read_state'] == 'READ_COMPLETE'
    assert row['review_state'] == 'GRAPH_CONTEXT_PENDING'
    assert row['strict_pair_count'] is row['strict_forecast_candidate_count'] is None
    assert not row['target_review_performed']
    ledger.close()


def test_absent_production_graph_handoff_is_not_silent_empty_context(tmp_path):
    document, native = source(); ledger = q.open_queue(tmp_path/'queue')
    with ledger.worker():
        q.enqueue(ledger, document, native, {})
        q.work(ledger, extractor=EmptyAdvisoryModel())
    row, = q.events(ledger, review.KIND)
    assert row['review_state'] == 'GRAPH_CONTEXT_PENDING' and row['reason_code'] == 'GRAPH_CONTEXT_UNAVAILABLE'
    assert row['strict_pair_count'] is None
    ledger.close()


def test_forged_reuse_pointer_is_isolated_per_document_and_failure_export_stays_valid(tmp_path):
    original, native = source(); alias = deepcopy(original); alias['document_id'] = 'new-alias'
    alias_native = native+b' '; alias['raw_sha256'] = sha(alias_native)
    sources = [(original, native), (alias, alias_native)]
    cache = tmp_path/'cache'; manifest = context_bundle(cache, sources,
        {d['document_id']: [d['document_id']] for d, _ in sources})
    ledger = q.open_queue(tmp_path/'queue')
    with ledger.worker():
        q.enqueue(ledger, original, native, {})
        q.enqueue(ledger, alias, alias_native, {}, analysis_replay=True)
        planned = q.events(ledger, 'CPU_QUEUE_DOCUMENT')
        with ledger.db:
            for item, (document, _) in zip(planned, sources):
                _, rows = receipts(document, [t['window'] for t in item['tasks']])
                for row in rows:
                    if document['document_id'] == alias['document_id']:
                        row.update(restored_receipt_not_new_inference=True, derived_reuse_binding_sha256='f'*64,
                                   original_record_sha256=sha(row), verified_window_input_sha256=sha(row['window']['text'].encode()))
                    ledger.event('CPU_QUEUE_WINDOW_RESULT', row)
        model = EmptyAdvisoryModel()
        result = q.work(ledger, extractor=model, analysis_context={'cache': cache, 'manifest': manifest})
    assert result['new_windows'] == model.calls == 0
    valid, = q.events(ledger, review.KIND); failed, = q.events(ledger, 'CPU_ANALYSIS_FAILURE')
    assert valid['document_id'] == original['document_id'] and valid['review_state'] == 'READ_EVIDENCE_HOLD'
    assert failed['document_id'] == alias['document_id']
    assert failed['CPU_windows_total'] == failed['CPU_windows_success'] == 1
    assert failed['CPU_windows_unread'] == 0
    resume.validate_analysis_failure(failed)
    resume.export_state(ledger.path, tmp_path/'safe'); ledger.close()
    safe = resume.Ledger(tmp_path/'safe')
    try:
        resume.audit(safe)
        assert q.events(safe, review.KIND) == [valid]
        assert q.events(safe, 'CPU_ANALYSIS_FAILURE') == [failed]
    finally: safe.close()
