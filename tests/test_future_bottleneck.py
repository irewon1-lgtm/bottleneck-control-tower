import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from bct.future_bottleneck import extract_body, public_url, run, screen


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
    ("A shortage of nurses is increasing recruitment costs.", "LABOR_ONLY"),
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
    assert not screen("The game launches in 2028.")["candidate"]
    assert screen("Production capacity may become tight.")["target_status"] == "UNRESOLVED"


def test_live_phrase_errors_do_not_become_targets():
    result = screen('Shortages of diesel, jet fuel and petrochemical feedstocks if it cannot move crude may occur.')
    assert [t['name'] for t in result['targets']] == ['diesel', 'jet fuel', 'petrochemical feedstocks']
    assert not screen('Shortages of skilled workers and contractors delay new production.')["candidate"]
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
        return 'Demand for power transformers may rise. Capacity is limited.', 'ARTICLE'
    state = run(path, output, fetcher=fetch)
    assert state['summary']['processed_this_run'] == 3
    assert state['summary']['body_ok_this_run'] == 2
    assert state['results']['1']['body_status'] == 'BODY_UNAVAILABLE'
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
    output.write_text(json.dumps(state))
    assert run(path, output, fetcher=fetch)['results']['1']['attempts'] == 3
    assert run(path, output, fetcher=fetch)['summary']['processed_this_run'] == 0


def test_workflow_is_independent_and_never_writes_canonical_database():
    text = Path('.github/workflows/future-bottleneck.yml').read_text()
    assert 'future-bottleneck-results' in text
    assert 'rss-canonical-data' not in text
    assert 'OPENAI_API_KEY' not in text
    assert 'python -m pytest -q' in text
    assert 'canonical.sqlite3' not in text.split('Publish candidate sidecar only')[1]
