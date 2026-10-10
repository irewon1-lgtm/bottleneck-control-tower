import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from bct.future_bottleneck import extract_body, public_url, run, screen


def test_closed_failed_source_skips_auto_without_erasing_history_and_new_version_resumes(tmp_path):
    path, output, tracking = tmp_path/'db', tmp_path/'c.json', tmp_path/'t.json'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status)')
        db.execute("INSERT INTO radar_items VALUES('d','t','https://example.com/a','s','2026-10-01','v1','active')")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    version = hashlib.sha256(b'https://example.com/av1').hexdigest()
    tracking.write_text(json.dumps({'runs': [{'id':'closed', 'type':'queue_resolution', 'state':'FAIL',
        'document_id':'d', 'source_version':version, 'lanes':['material'], 'reason':'HTTPError',
        'evidence':{'attempts':3}, 'resume_condition':'changed source'}]}))
    calls = []
    fetch = lambda url: calls.append(url) or '<article><p>Demand for power transformers rises.</p></article>'
    state = run(path, output, tracking_path=tracking, fetcher=fetch)
    assert not calls and state['summary']['closed_failed_sources'] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    with sqlite3.connect(path) as db:
        db.execute("UPDATE radar_items SET updated_at='v2'")
    state = run(path, output, tracking_path=tracking, fetcher=fetch)
    assert len(calls) == 1 and state['summary']['closed_failed_sources'] == 0


@pytest.mark.parametrize("body,target", [
    ("Demand for ammonium perchlorate will rise. Capacity is limited until 2028.", "ammonium perchlorate"),
    ("Power transformers have lead times of 24 months. A new plant is planned.", "power transformers"),
    ("A shortage of sapphire optical windows could delay production.", "sapphire optical windows"),
    ("HBM3 memory orders are accelerating. Suppliers are adding capacity.", "hbm3 memory"),
    ("Supply may recover as advanced packaging expansion ramps up.", "advanced packaging"),
])
def test_broad_candidates_and_explicit_targets(body, target):
    result = screen(body)
    assert result["candidate"]
    assert target in [t["name"].lower() for t in result["targets"]]
    assert result["final_bottleneck"] is None


@pytest.mark.parametrize("body,reason", [
    ("The CPU bottleneck reduces gaming frame rates.", "COMPUTER_PERFORMANCE_ONLY"),
    ("HBM3 memory bandwidth is the performance bottleneck in this algorithm.", "COMPUTER_PERFORMANCE_ONLY"),
])
def test_only_obvious_noise_removed(body, reason):
    result = screen(body)
    assert not result["candidate"]
    assert result["reason"] == reason


def test_mixed_labor_and_physical_shortage_retained():
    assert screen("A shortage of workers and power transformers delays manufacturing.")["candidate"]
    assert screen("A shortage of workers and sapphire optical windows delays production.")["candidate"]
    assert screen("The GPU supply shortage constrains equipment manufacturers.")["candidate"]
    assert not screen("The game is set in 2028.")["candidate"]
    assert screen("Production capacity may become tight.")["target_status"] == "UNRESOLVED"


def test_v33_demand_relief_and_workforce_changes_are_retained():
    # v3.3 deliberately removes the previous shortage and industrial-only gate.
    assert screen("Demand for warehouse automation is growing. A company is expanding production capacity.")["candidate"]
    assert not screen("The plant has production capacity of 100 units. Demand was 90 units.")["candidate"]
    assert 'RELIEF' in screen("Reduced lead times and expanded capacity are improving cross-border operations.")["discovery_paths"]
    assert not screen("Connectivity constraints can slow AI systems and increase latency.")["candidate"]
    assert screen("A shortage of skilled workers is delaying new production capacity.")["candidate"]
    assert screen("Skilled workers are in shortage. The real constraint is execution, capacity and capability.")["candidate"]
    assert screen("A shortage of skilled cybersecurity professionals is limiting workforce capacity.")["candidate"]
    assert not screen("Manual scheduling bottlenecks constrain AI-driven planning workflows.")["candidate"]
    assert screen("Equipment order books are backlogged years out and manufacturing throughput is limited.")["candidate"]
    result = screen("Demand for more specialised care is growing. The provider plans an expansion.")
    assert result["candidate"]
    assert result["decision"] == 'CONTEXT_REVIEW'
    assert result["targets"] == []


def test_live_phrase_errors_do_not_become_targets():
    result = screen('Shortages of diesel, jet fuel and petrochemical feedstocks if it cannot move crude may occur.')
    assert [t['name'] for t in result['targets']] == ['diesel', 'jet fuel', 'petrochemical feedstocks']
    assert screen('Shortages of skilled workers and contractors delay new production.')["candidate"]
    assert not screen('Production of up to 90 units per day is planned.')["targets"]
    assert not screen('Transit capacity for just the second time ever is reduced.')["targets"]
    assert screen('A shortage of treatment slots,” Sleuth said, discussing RLTs.')["targets"][0]['name'] == 'treatment slots'


def test_article_body_excludes_navigation_and_scripts():
    paragraphs = ["Power transformers have long lead times and manufacturers plan to add capacity. " * 4,
                  "A planned production expansion could meet future customer demand for equipment. " * 4]
    html = '<nav><p>GPU bottleneck ' + ('noise ' * 100) + '</p></nav><article>'
    html += ''.join('<p>' + p + '</p>' for p in paragraphs) + '</article>'
    body, method = extract_body(html)
    assert method == "ARTICLE" and "noise" not in body
    ld = '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", "articleBody": '\n'.join(paragraphs)}) + '</script>'
    assert extract_body(ld)[1] == "JSON_LD"
    with pytest.raises(ValueError):
        extract_body('<h1>Power transformer shortage</h1><p>Enable javascript and cookies</p>')


def test_public_urls_reject_private_and_redirect_destinations(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a: [(2, 1, 6, '', ('127.0.0.1', 80))])
    with pytest.raises(ValueError):
        public_url("http://localhost/test")
    with pytest.raises(ValueError):
        public_url("file:///etc/passwd")


def test_read_only_failure_continuation_cache_and_new_articles(tmp_path):
    path, output = tmp_path / 'canonical.db', tmp_path / 'results.json'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,source_type)')
        for i in range(3):
            db.execute("INSERT INTO radar_items VALUES(?,?,?,?,?,?,'active','NEWS')",
                       (str(i), 'Title claims shortage', str(i), 'source', f'2026-09-30T00:00:0{i}', 'v1'))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    calls = []
    def fetch(url):
        calls.append(url)
        if url == '1':
            raise TimeoutError()
        return '<article><p>Demand for power transformers may rise. Capacity is limited.</p></article>'
    state = run(path, output, fetcher=fetch)
    assert state['summary']['processed_this_run'] == 3
    assert state['summary']['body_ok_this_run'] == 2
    assert state['summary']['active_processed_total'] == 3
    assert state['summary']['active_unprocessed_total'] == 0
    assert state['summary']['readable_active_total'] == 2
    assert state['summary']['unavailable_active_total'] == 1
    assert state['summary']['precursor_documents_total'] == 2
    assert state['summary']['paired_precursor_documents_total'] == 2
    assert state['results']['1']['body_status'] == 'UNAVAILABLE'
    assert state['results']['1']['targets'] == []
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert run(path, output, fetcher=fetch)['summary']['processed_this_run'] == 0
    assert len(calls) == 3
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO radar_items VALUES('4','new','4','source','2026-10-01','v1','active','NEWS')")
    assert run(path, output, fetcher=fetch)['summary']['processed_this_run'] == 1
    # Failure is retried automatically after the cooling period; max three attempts.
    state = json.loads(output.read_text())
    state['results']['1']['retry_after'] = ''
    state['results']['1']['attempts'] = 2
    version = state['results']['1']['source_version']
    state['results']['1']['acquisition']['versions'][version]['automatic_attempts'] = 2
    state['results']['1']['acquisition']['versions'][version]['next_retry_at'] = '2020-01-01T00:00:00+00:00'
    output.write_text(json.dumps(state))
    assert run(path, output, fetcher=fetch)['results']['1']['attempts'] == 3
    assert run(path, output, fetcher=fetch)['summary']['processed_this_run'] == 0


def test_filter_rescreen_preserves_existing_body_version_judgment(tmp_path):
    path, output, cache = tmp_path/'db', tmp_path/'results.json', tmp_path/'cache'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status)')
        db.execute("INSERT INTO radar_items VALUES('d','t','https://example.com/a','s','2026-10-01','v1','active')")
    html = '<article>' + ''.join(
        '<p>Demand for power transformers is rising while qualified capacity remains limited.</p>'
        for _ in range(8)) + '</article>'
    first = run(path, output, cache_dir=cache, fetcher=lambda _: html)
    body_hash = first['results']['d']['current_body_sha256']
    preserved = json.loads(json.dumps(first['results']['d']['versions'][body_hash]))

    second = run(path, output, cache_dir=cache, fetcher=lambda _: (_ for _ in ()).throw(
        AssertionError('unchanged cached body must not be fetched')), tracked_terms=('transformers',))

    assert second['results']['d']['versions'][body_hash] == preserved
    assert second['results']['d']['tracking_terms_sha256'] != first['results']['d']['tracking_terms_sha256']


def test_workflow_is_independent_and_never_writes_canonical_database():
    text = Path('.github/workflows/future-bottleneck.yml').read_text()
    assert 'future-bottleneck-results' in text
    assert 'rss-canonical-data' not in text
    assert 'OPENAI_API_KEY' not in text
    assert 'python -m pytest -q' in text
    assert 'for pass in 2 3; do' in text
    assert "get('pending_due',0)" in text
    assert 'body-recovery-v1' in text
    assert "recoverable = {'NO_ARTICLE_CONTENT', 'TimeoutError', 'LEGACY_COMPLETENESS_UNVERIFIED'}" in text
    assert '--trigger SCHEDULED' in text
    assert 'canonical.sqlite3' not in text.split('Publish candidate sidecar only')[1]
