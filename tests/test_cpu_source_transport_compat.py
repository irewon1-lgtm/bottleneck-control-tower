"""V4-only source compatibility; the portable transport tests run on main."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile
import yaml

import pytest

from test_cpu_source_transport import ROOT, helper, zipped


def test_full_and_subset_cache_preserve_malformed_missing_and_ambiguous_holds(tmp_path):
    from bct.v4 import cpu_automation as queue
    from test_v4_cpu_automation import document
    module = helper(); cache = tmp_path / 'cache'; (cache / 'documents').mkdir(parents=True); (cache / 'raw').mkdir()
    doc, raw = document(); doc['raw_path'] = 'old-runner/' + doc['raw_sha256'] + '.html'
    (cache / 'documents/one.json').write_text(json.dumps(doc)); (cache / 'documents/duplicate.json').write_text(json.dumps(doc))
    (cache / 'documents/malformed.json').write_bytes(b'{bad metadata')
    (cache / 'raw' / Path(doc['raw_path']).name).write_bytes(raw)
    manifest = {'format': 'bct-new-rss-delta-v1', 'documents': [
        {'document_id': 'missing', 'url': 'https://official.example/missing'},
        {'document_id': doc['document_id'], 'url': doc['origin_url']}]}
    archive = tmp_path / 'cache.zip'; zipped(cache, archive); selected = tmp_path / 'selected'
    module.extract_sources(archive, selected)
    results = []
    for name, source in [('full', cache), ('bounded', selected)]:
        ledger = queue.open_queue(tmp_path / name)
        result = queue.ingest_delta(ledger, manifest, source, upstream_run_id='fixture')
        results.append([(r['status'], r.get('reason')) for r in result]); ledger.close()
    assert results[0] == results[1] == [('HELD_ISOLATED', 'UPSTREAM_BODY_NOT_AVAILABLE_NO_REFETCH'),
                                        ('HELD_ISOLATED', 'UPSTREAM_VERSION_AMBIGUOUS')]


@pytest.mark.parametrize('failed_first', [False, True])
def test_prior_partial_source_and_committed_window_survive_without_date_filter(tmp_path, failed_first):
    from bct.v4 import cpu_automation as queue, cpu_resume as resume
    from test_v4_cpu_resume import make_source, cache_source
    module = helper()
    if failed_first:
        from test_v4_cpu_automation import document, Extractor
        doc, raw = document('Atlas ordered Helios heat pumps.\nA second separate paragraph.')
        ledger = queue.open_queue(tmp_path / 'original'); queue.enqueue(ledger, doc, raw, {})
        queue.work(ledger, extractor=Extractor(fail=True), max_windows=1); ledger.close()
    else:
        doc, raw = make_source(tmp_path, partial=True)
    cache, policy = cache_source(tmp_path, doc, raw); archive = tmp_path / 'cache.zip'; zipped(cache, archive)
    selected = tmp_path / 'selected'; module.extract_sources(archive, selected)
    results = []
    for name, source in [('full', cache), ('bounded', selected)]:
        resume.export_state(tmp_path / 'original/v4.sqlite3', tmp_path / name)
        ledger = queue.open_queue(tmp_path / name)
        result = resume.hydrate(ledger, source, policy)
        results.append((result, queue.state(ledger)['pending_windows'],
                        len(queue.events(ledger, 'CPU_QUEUE_WINDOW_RESULT')))); ledger.close()
    assert results[0] == results[1]
    assert results[0][1:] == (1, 1)


def test_saved_original_raw_fixture_and_metadata_bytes_survive(tmp_path):
    """Reuse one existing frozen native fixture without fetching or CPU work."""
    module = helper(); frozen = ROOT / 'docs/v4/cpu-automation/ledger.sqlite3.gz'
    before = hashlib.sha256(frozen.read_bytes()).hexdigest()
    database = tmp_path / 'original.sqlite3'; database.write_bytes(gzip.decompress(frozen.read_bytes()))
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        payload, raw = db.execute('SELECT d.payload,b.data FROM documents d JOIN blobs b ON b.id=d.raw_id ORDER BY d.id LIMIT 1').fetchone()
    doc = json.loads(payload)
    assert hashlib.sha256(raw).hexdigest() == doc['raw_sha256']
    archive = tmp_path / 'saved.zip'
    with zipfile.ZipFile(archive, 'w') as saved:
        saved.writestr('documents/original.json', payload.encode())
        saved.writestr('raw/' + doc['raw_sha256'] + '.html', raw)
        saved.writestr('evaluations/unrelated.json', b'not CPU input')
    selected = tmp_path / 'selected'; module.extract_sources(archive, selected)
    assert (selected / 'documents/original.json').read_bytes() == payload.encode()
    assert (selected / 'raw' / (doc['raw_sha256'] + '.html')).read_bytes() == raw
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == before

def test_manual_transport_validation_uploads_only_small_receipts_and_does_not_execute_cpu():
    workflow = yaml.load((ROOT / '.github/workflows/v4-cpu-private-research.yml').read_text(), Loader=yaml.BaseLoader)
    job = workflow['jobs']['source-transport-verify']; text = yaml.dump(job)
    assert "inputs.purpose == 'source-transport-verify'" in job['if']
    assert job['timeout-minutes'] == '10'
    assert 'secrets.' not in text and 'pip install' not in text and 'v4_cpu_private.py process' not in text
    assert '018f5bb1aa9d27e2891b9902155cb14107f9b019' in text
    upload = next(s for s in job['steps'] if s.get('uses') == 'actions/upload-artifact@v4')
    assert upload['with']['path'].splitlines() == [
        '${{ runner.temp }}/cpu-source-transport.json', '${{ runner.temp }}/fixed230-copy.json',
        '${{ runner.temp }}/cpu-source-gate6-qa.json']
