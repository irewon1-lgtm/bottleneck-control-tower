"""Execute the frozen holdout on a temporary database; publish metadata only."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from bct.future_bottleneck import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    original = hashlib.sha256(args.db.read_bytes()).hexdigest()
    with sqlite3.connect(f'file:{args.db.resolve()}?mode=ro', uri=True) as source:
        source.row_factory = sqlite3.Row
        selected = []
        for document in manifest['documents']:
            row = source.execute('SELECT id,title,url,source,collected_at,updated_at,status,source_type FROM radar_items WHERE id=?', (document['id'],)).fetchone()
            if row is None or row['url'] != document['url'] or row['updated_at'] != document['updated_at']:
                raise RuntimeError('Frozen holdout document is absent or changed: ' + document['id'])
            selected.append(tuple(row))
    with tempfile.TemporaryDirectory() as directory:
        trial_db = Path(directory) / 'holdout.sqlite3'
        with sqlite3.connect(trial_db) as target:
            target.execute('CREATE TABLE radar_items(id,title,url,source,collected_at,updated_at,status,source_type)')
            target.executemany('INSERT INTO radar_items VALUES(?,?,?,?,?,?,?,?)', selected)
        state = run(trial_db, args.output, limit=len(selected), cache_dir=args.cache_dir)
    if hashlib.sha256(args.db.read_bytes()).hexdigest() != original:
        raise RuntimeError('Original database changed')
    print(json.dumps({'sample_id': manifest['sample_id'], 'database_unchanged': True,
                      'selected_documents': len(selected), 'summary': state['summary']}))


if __name__ == '__main__':
    main()
