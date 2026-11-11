"""Read-only same-six consumed development literal recognition comparison.

Uses the exact unchanged historical input windows, product gold and scorer.
No event/adoption/CPU accuracy inference is made from these literal candidates.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import types

from bct import precursor_scope_reader as current
from bct.v4.comparison_evaluation import score_products
from bct.v4.event_evaluation import metrics

ROOT = Path(__file__).resolve().parents[3]
BASELINE = '23a0615f1a10f2b938cb2b5401706a1995b4d4f2'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    before_source = subprocess.check_output(['git', 'show', BASELINE + ':src/bct/precursor_scope_reader.py'], cwd=ROOT)
    baseline = types.ModuleType('bct.extraction_baseline_scope_reader')
    baseline.__package__ = 'bct'
    exec(compile(before_source, BASELINE + ':precursor_scope_reader.py', 'exec'), baseline.__dict__)
    paths = ['docs/v4/path-comparison/final/inputs.json', 'docs/v4/path-comparison/final/event-gold.json',
             'src/bct/v4/comparison_evaluation.py', 'src/bct/v4/event_evaluation.py']
    integrity = []
    for relative in paths:
        payload = (ROOT / relative).read_bytes()
        assert payload == subprocess.check_output(['git', 'show', BASELINE + ':' + relative], cwd=ROOT)
        integrity.append({'path': relative, 'sha256': sha(payload), 'unchanged_from_baseline': True})
    rows = json.loads((ROOT / paths[0]).read_text())['documents']
    gold = {d['document_id']: d for d in json.loads((ROOT / paths[1]).read_text())['documents']}
    result = []
    for row in rows:
        document = row['doc']
        did = row['document_id']
        assert sha(document['body'].encode()) == document['body_sha256'] == gold[did]['body_sha256']
        windows = row['source']['windows']
        assert all(document['body'][w['start']:w['end']] == w['text'] for w in windows)
        variants = {}
        for name, reader in [('before', baseline), ('after', current)]:
            predictions = []
            for window in windows:
                for line in reader.allowed_lines(document)[0]:
                    start, end = max(window['start'], line['start']), min(window['end'], line['end'])
                    if start >= end:
                        continue
                    clipped = {'start': start, 'end': end, 'quote': document['body'][start:end]}
                    for statement in reader.sentences(document, [clipped]):
                        for product in reader.literal_fields(document, statement)['product']:
                            assert document['body'][product['locator']['start']:product['locator']['end']] == product['value']
                            predictions.append({'product': {'surface': product['value']}})
            variants[name] = {'metrics': score_products(predictions, gold[did]),
                              'unique_literal_candidates': sorted({p['product']['surface'] for p in predictions})}
        result.append({'document_id': did, 'body_sha256': document['body_sha256'],
                       'unchanged_input_windows': [{'start': w['start'], 'end': w['end'], 'text_sha256': sha(w['text'].encode())} for w in windows],
                       **variants})
    totals = {name: metrics({key: sum(r[name]['metrics'][key] for r in result) for key in ('TP', 'FP', 'FN')})
              for name in ('before', 'after')}
    output = {'scope': 'SIX_ALREADY_CONSUMED_PARTIAL_INPUT_DEVELOPMENT_DOCUMENTS_LITERAL_PRODUCT_GRAMMAR_ONLY',
              'baseline_code_sha': BASELINE, 'baseline_reader_sha256': sha(before_source),
              'current_reader_sha256': sha(Path(current.__file__).read_bytes()),
              'input_and_gold_integrity': integrity, 'documents': result, 'total_metrics': totals,
              'source_requests': 0, 'new_model_inferences': 0, 'HOLDOUT_used': False,
              'historical_AI_CPU_scores_overwritten': False,
              'limitations': ['Literal candidate recognition is not event adoption or source-product/order relation accuracy.',
                              'Unmatched literals are evaluator FP labels in this fixed gold scope; they are not all independently adjudicated false physical products.',
                              'The two repaired audited statements are outside these historical partial input windows.',
                              'This consumed development replay is not independent accuracy or lead performance.']}
    out = ROOT / 'docs/v4/full-pipeline-debug-20261111/extraction-development-six.json'
    out.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(totals))


if __name__ == '__main__':
    main()
