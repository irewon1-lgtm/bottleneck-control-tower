"""One offline, common Q2 queue; stored sources remain read-only. No model/API."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from bct.objective_lock import require_objective
from bct.v4 import quantitative_counterpart as q2
from bct.v4.store import Ledger, file_sha


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    products = json.loads(Path('docs/v4/quantitative/product-facts.json').read_text())
    require_objective(products)
    legacy = json.loads(Path('docs/v4/supply-linkage/next-step-inputs.json').read_text())
    paths = [Path('var/v4/supply-linkage/ledger/v4.sqlite3'),
             Path('var/v4/cpu-recovery/ledger/v4.sqlite3'),
             Path('var/v4/cross-industry/ledger/v4.sqlite3')]
    before = {str(p): file_sha(p) for p in paths if p.exists()}
    documents = {}; native = {}
    for path in paths:
        if not path.exists():
            continue
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            for text, in db.execute('SELECT payload FROM documents'):
                doc = json.loads(text); documents.setdefault(doc['document_id'], doc)
                raw = db.execute('SELECT data FROM blobs WHERE id=?', (doc['raw_sha256'],)).fetchone()
                if raw:
                    native.setdefault(doc['document_id'], raw[0])
    # Preserve the old PARTIAL versions. Add separately reviewed recaptures only.
    for path in Path('var/v4/quantitative/q1-quality').glob('*.verified.json'):
        doc = json.loads(path.read_text()); documents[doc['document_id']] = doc
        raw_path = path.with_name(path.name.replace('.verified.json', '.recapture'))
        if raw_path.exists():
            native[doc['document_id']] = raw_path.read_bytes()
    seeds = q2.seeds(products['records'], legacy['records'])
    result = q2.packet(seeds, list(documents.values()), as_of='2026-10-15')
    acquisition = Path('var/v4/quantitative/q2-counterpart/acquisition/v4.sqlite3')
    attempted = {}; captured = set()
    if acquisition.exists():
        with sqlite3.connect(acquisition.resolve().as_uri() + '?mode=ro', uri=True) as db:
            attempted = {json.loads(p)['url']: True for p, in db.execute("SELECT payload FROM events WHERE kind='Q2_COUNTERPART_FETCH_ATTEMPT'")}
            captured = {u for u, in db.execute('SELECT url FROM documents')}
    for row in result['records']:
        links = []
        seed = next(s for s in seeds if s['id'] == row['seed_id'])
        # Existing seed citations only. No general website crawling.
        for doc in documents.values():
            if doc['body_sha256'] != seed['source'].get('body_sha256') or doc['document_id'] not in native:
                continue
            links += q2.linked_sources(row, doc, native[doc['document_id']],
                                       attempted_urls=[d['origin_url'] for d in documents.values()])
        row['official_link_queue'] = list({x['url']: x for x in links}.values())[:3 - len(row['selected_sources'])]
        for link in row['official_link_queue']:
            if link['url'] in attempted:
                link['status'] = 'CAPTURED_SOURCE_REVIEW_HELD' if link['url'] in captured else 'FAILED_LOCAL_EXTRACTION_NO_RETRY'
        row['id'] = q2.sha([q2.VERSION, {k: v for k, v in row.items() if k != 'id'}])
    # Retain metadata/positions only. Original evidence stays in its old store.
    packet = output / 'counterpart-review.json'
    packet.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    ledger = Ledger(output / 'ledger')
    saved = q2.save(ledger, result)
    backup = output / 'backup.sqlite3'; ledger.backup(backup); ledger.close()
    code = ('import json,sys;from bct.v4.store import Ledger,file_sha;'
            'from bct.v4.quantitative_counterpart import save;'
            'L=Ledger(sys.argv[1]);p=json.load(open(sys.argv[2]));'
            'before=file_sha(L.path);r=save(L,p);L.close();'
            'assert r["added"]==0;assert before==file_sha(sys.argv[1]+"/v4.sqlite3");print(r)')
    child = subprocess.run([sys.executable, '-c', code, str(output / 'ledger'), str(packet)],
                           capture_output=True, text=True, timeout=60)
    if child.returncode:
        raise ValueError('COUNTERPART_RESTART_FAILED: ' + child.stderr[-500:])
    restored = output / 'restored'; restored.mkdir(exist_ok=True)
    (restored / 'v4.sqlite3').write_bytes(backup.read_bytes())
    child2 = subprocess.run([sys.executable, '-c', code, str(restored), str(packet)],
                            capture_output=True, text=True, timeout=60)
    if child2.returncode:
        raise ValueError('COUNTERPART_RESTORE_FAILED: ' + child2.stderr[-500:])
    assert all(file_sha(Path(p)) == h for p, h in before.items())
    report = {'stored_documents_examined_by_literal_search': len(documents), 'seed_events': len(seeds),
              'selected_source_pointers': sum(len(r['selected_sources']) for r in result['records']),
              'unique_selected_sources': len({s['body_sha256'] for r in result['records'] for s in r['selected_sources']}),
              'unfetched_official_links': sum(x['status']=='UNFETCHED_OFFICIAL_LINK_NOT_EVIDENCE' for r in result['records'] for x in r['official_link_queue']),
              'new_order_fact_discovery': 'Separate explicit source review; queue hits are not facts',
              'actual_new_capacity_facts': 0, 'confirmed_deadlines': 0,
              'independent_pairs': 0, 'new_S1': 0, 'new_S2': 0, 'new_S3': 0,
              'save': saved, 'new_process_dedup': True, 'backup_restore': True,
              'protected_source_DB_hashes_unchanged': before, 'external_AI_calls': 0,
              'scope': 'Exact-name and role lead search, NOT full document semantic reading or independent accuracy'}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
