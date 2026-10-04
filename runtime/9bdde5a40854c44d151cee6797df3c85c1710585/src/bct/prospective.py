"""Minimal LIVE wrapper: immutable first records, append-only observations, reports.

Uses the existing discovery engine and private create-if-absent JSON writer.
Never writes canonical data, reviews, hypotheses or prediction ledgers.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from . import forecast_discovery as engine
from .collectors.rss.cli import load_feeds
from .future_manual_review import _private_write
from .objective_lock import objective_binding, require_objective, stamp_export


class Blocked(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _id(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _engine_sha():
    return hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()


@contextmanager
def _lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / '.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield root
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _write(path, document):
    document = stamp_export(document)
    document['record_sha256'] = engine.digest(document)
    _private_write(path, document)  # Atomic link; never overwrite an existing path.
    Path(path).chmod(0o444)
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return document


def _read(path):
    document = json.loads(Path(path).read_text())
    require_objective(document)
    if document.get('mode') != 'LIVE':
        raise Blocked('NON_LIVE_RECORD_IN_PROSPECTIVE_STORE')
    payload = {k: v for k, v in document.items() if k != 'record_sha256'}
    if engine.digest(payload) != document.get('record_sha256'):
        raise Blocked('SNAPSHOT_INTEGRITY_MISMATCH')
    return document


def _session(root):
    session = _read(root / 'session.json')
    if session['mode'] != 'LIVE' or session['engine_sha256'] != _engine_sha():
        raise Blocked('SESSION_MODE_OR_ENGINE_CHANGED')
    return session


def _discovery_scope(feeds_path):
    feeds = load_feeds(Path(feeds_path))
    return {'version': 'bct-operating-discovery-' + engine.digest(feeds)[:16],
            'policy': "Existing BCT radar_items WHERE status='active', all sources; no historical issuer or publisher subset",
            'feeds_sha256': engine.digest(feeds), 'rss_feeds': feeds,
            'input_filtering_by_this_wrapper': False}


def start(root, feeds_path):
    """Start now, once. No caller-supplied or retrospectively backdated timestamp."""
    objective_binding()
    scope = _discovery_scope(feeds_path)
    with _lock(root) as root:
        if (root / 'session.json').exists():
            session = _session(root)
            if session['initial_discovery_source_universe'] != scope:
                raise Blocked('EXISTING_SESSION_SCOPE_DIFFERS; never rewrite session')
            return session
        return _write(root / 'session.json', {
            'format': 'bct-prospective-session-v1', 'mode': 'LIVE', 'started_at': _now(),
            'engine_sha256': _engine_sha(), 'feeds_path': str(Path(feeds_path).resolve()),
            'initial_discovery_source_universe': scope,
            # Separate confirmation scope, based on existing operating publishers.
            # This is NOT the six-issuer historical benchmark universe.
            'confirmation_source_universe': {
                'version': 'bct-operating-confirmation-' + scope['feeds_sha256'][:16],
                'source_domains': sorted({urlsplit(u).hostname for u in scope['rss_feeds'].values()}),
                'definition': 'Explicit same-TARGET original confirmations on frozen existing operating publisher domains from session start',
                'T_global': 'UNKNOWN'},
            'historical_benchmark_universe_used': False})


def _live_input(batch, *, early=False):
    require_objective(batch)
    if batch.get('mode') != 'LIVE' or batch.get('detection_mode', 'LIVE') != 'LIVE':
        raise Blocked('HISTORICAL_OR_BACKFILL_NOT_LIVE')
    if batch.get('layer') == 'CONFIRMATION' or batch.get('format') in ('bct-forecast-discovery-v1', 'bct-early-forecast-v1'):
        raise Blocked('USE_FRESH_PRECURSORS_NOT_OLD_REVIEW_OR_DISCOVERY_OUTPUT')
    if batch.get('confirmations') and not early:
        raise Blocked('USE_SEPARATE_SCOPE_OBSERVATION_NOT_DISCOVERY_LABELS')


def _doc(document):
    if hashlib.sha256(document['body'].encode()).hexdigest() != document['body_sha256']:
        raise Blocked('SOURCE_BODY_HASH_MISMATCH')
    if document.get('published_at') is None and document.get('publication_precision') == 'UNKNOWN':
        if engine.clock(document['public_snapshot_observed_at']) > engine.clock(document['available_at']):
            raise Blocked('PUBLICATION_BOUND_AFTER_AVAILABILITY')
    else:
        engine.clock(document['published_at'])
    return document


def _ref(signal, documents):
    doc = _doc(documents[signal['document_id']])
    loc = signal['locator']; start, end = loc['start'], loc['end']
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(doc['body']):
        raise Blocked('INVALID_EVIDENCE_LOCATOR')
    return {**deepcopy(signal), 'body_sha256': doc['body_sha256'],
            'published_at': doc['published_at'], 'origin_id': doc.get('origin_id'),
            'origin_url': doc.get('origin_url')}


def _candidate_record(candidate, batch, result, scope):
    docs = {x['document_id']: x for x in batch['documents']}
    evidence = deepcopy(candidate['evidence'])
    selected_docs = {e['document_id']: _doc(docs[e['document_id']]) for e in evidence}
    relief = [_ref(s, docs) for s in batch.get('signals', [])
              if s.get('target_id') == candidate['target_id']
              and s.get('signal_type') in ('substitute', 'dual_source', 'redesign', 'inventory')]
    annotations = batch.get('candidate_annotations', {}).get(candidate['target_id'], {})
    unknown = list(annotations.get('decisive_UNKNOWN', []))
    for e in evidence:
        if e.get('role') in ('DEMAND', 'SUPPLY') and e.get('quantity') in (None, 'UNKNOWN'):
            unknown.append({'document_id': e['document_id'], 'field': 'quantity', 'value': 'UNKNOWN'})
        if e.get('role') == 'SUPPLY' and e.get('coverage_complete') is not True:
            unknown.append({'document_id': e['document_id'], 'field': 'qualified_supply_coverage', 'value': 'UNKNOWN'})
    return {
        'format': 'bct-prospective-candidate-first-v1', 'mode': 'LIVE',
        'target_id': candidate['target_id'], 'target': candidate['target'], 'scope_id': candidate['scope_id'],
        'candidate_first_detected_at': candidate['candidate_first_detected_at'],
        'source_document_ids': sorted(selected_docs),
        'source_documents': [deepcopy(selected_docs[k]) for k in sorted(selected_docs)],
        'source_publication_timestamps': {k: v['published_at'] for k, v in selected_docs.items()},
        'demand_precursor_evidence': [e for e in evidence if e['role'] == 'DEMAND'],
        'supply_capacity_ramp_precursor_evidence': [e for e in evidence if e['role'] == 'SUPPLY'],
        'substitute_relief_evidence': relief, 'substitute_relief_status': 'RECORDED' if relief else 'UNKNOWN',
        'decisive_UNKNOWN': unknown,
        'refutation_conditions': annotations.get('refutation_conditions') or [
            'Same-scope qualified supply sufficient before demand need date',
            'Confirmed cancellation/reduction of the recorded demand',
            'Available qualified substitutes relieve the recorded gap'],
        'discovery_source_universe': scope, 'engine_sha256': _engine_sha(),
        'first_run_id': result['batch_id'], 'input_sha256': result['input_sha256'],
        'candidate_as_generated': deepcopy(candidate),
        **({k: deepcopy(candidate[k]) for k in ('candidate_class', 'independent_origin_count',
             'future_demand_window', 'known_supply_window', 'refutation_conditions') }
           if candidate.get('candidate_class') == 'EARLY_FORECAST_CANDIDATE' else {})}


def run(root, batch, *, early=False):
    """Invoke unchanged discovery in LIVE mode; no imported old candidate timestamps."""
    _live_input(batch, early=early)
    with _lock(root) as root:
        session = _session(root)
        scope = _discovery_scope(session['feeds_path'])  # Keep current full operating range.
        runs = [_read(p) for p in (root / 'runs').glob('*.json')]
        strict_runs = [r for r in runs if r['engine_result'].get('format') == 'bct-forecast-discovery-v1']
        latest = max(strict_runs, key=lambda x: x['engine_result']['computed_at']) if strict_runs else None
        previous = latest['engine_result'] if latest else None
        if early:
            from . import early_forecast
            result = early_forecast.discover(batch, mode='LIVE')
            result['early_engine_sha256'] = hashlib.sha256(Path(early_forecast.__file__).read_bytes()).hexdigest()
            for candidate in result['candidates']:
                path = root / 'candidates' / (_id(candidate['target_id']) + '.json')
                if path.exists():
                    candidate['candidate_first_detected_at'] = _read(path)['candidate_first_detected_at']
            # Refutation/late evidence is history; the original prediction stays intact.
            for outcome in result['outcomes']:
                path = root / 'candidates' / (_id(outcome['target_id']) + '.json')
                if path.exists() and not any(c['target_id'] == outcome['target_id'] for c in result['candidates']):
                    first = _read(path)
                    if first.get('candidate_class') == early_forecast.CLASS:
                        result['candidates'].append({**deepcopy(first['candidate_as_generated']),
                                                     'current_state': outcome['state']})
        else:
            result = engine.discover(batch, mode='LIVE', previous=previous)
        if engine.clock(result['computed_at']) < engine.clock(session['started_at']):
            raise Blocked('DETECTION_PRECEDES_PROSPECTIVE_START')
        records = []
        grouped = {}
        for candidate in result['candidates']:
            grouped.setdefault(candidate['target_id'], []).append(candidate)
        for variants in grouped.values():
            candidate = min(variants, key=lambda c: engine.clock(c['candidate_first_detected_at']))
            path = root / 'candidates' / (_id(candidate['target_id']) + '.json')
            if path.exists():
                first = _read(path)
                if engine.clock(candidate['candidate_first_detected_at']) < engine.clock(first['candidate_first_detected_at']):
                    raise Blocked('RETROACTIVE_FIRST_TIMESTAMP')
                records.append((candidate, path, first, None))
            else:
                if candidate['candidate_first_detected_at'] != result['computed_at']:
                    raise Blocked('OLD_CANDIDATE_CANNOT_BECOME_NEW_LIVE_FIRST_RECORD')
                record = _candidate_record(candidate, batch, result, scope)
                records.append((candidate, path, None, record))
        counts = {'first_frozen': 0, 'history_appended': 0}
        # Freeze first before publishing the run as previous state. A interrupted
        # run must not leave an old engine timestamp with no first snapshot.
        prepared = []
        for candidate, path, first, record in records:
            new = first is None
            if new:
                first = _write(path, record)
                counts['first_frozen'] += 1
            prepared.append((candidate, first, new))
        stored_run = _write(root / 'runs' / (_id(result['batch_id']) + '.json'), {
            'format': 'bct-prospective-run-v1', 'mode': 'LIVE', 'recorded_at': _now(),
            'engine_result': result, 'discovery_input': deepcopy(batch), 'discovery_source_universe': scope,
            'first_snapshot_references': {c['target_id']: first['record_sha256'] for c, first, new in prepared}})
        for candidate, first, new in prepared:
            if not new:
                _write(root / 'candidate-history' / _id(candidate['target_id']) / (_id(result['batch_id']) + '.json'), {
                    'format': 'bct-prospective-candidate-followup-v1', 'mode': 'LIVE',
                    'target_id': candidate['target_id'], 'observed_at': result['computed_at'],
                    'first_snapshot_sha256': first['record_sha256'],
                    'candidate_followup': deepcopy(candidate), 'discovery_input': deepcopy(batch),
                    'candidate_followups': deepcopy(grouped[candidate['target_id']]),
                    'run_snapshot_sha256': stored_run['record_sha256']})
                counts['history_appended'] += 1
        return {**objective_binding(), **counts, 'run_id': result['batch_id'],
                'engine_state': result['state'], 'evaluation': _report(root)}


def observe(root, observation):
    require_objective(observation)
    if observation.get('mode') != 'LIVE' or observation.get('detection_mode', 'LIVE') != 'LIVE':
        raise Blocked('HISTORICAL_CONFIRMATION_NOT_LIVE')
    with _lock(root) as root:
        session = _session(root)
        doc = _doc(observation['document'])
        published = engine.clock(doc['published_at']); received = engine.clock(_now())
        if not engine.clock(session['started_at']) <= published <= received:
            raise Blocked('CONFIRMATION_OUTSIDE_LIVE_OBSERVATION_WINDOW')
        if doc.get('publication_verified') is not True or doc.get('publication_precision') != 'TIMESTAMP':
            raise Blocked('EXACT_PUBLICATION_TIMESTAMP_NOT_VERIFIED')
        if urlsplit(doc['url']).hostname not in session['confirmation_source_universe']['source_domains']:
            raise Blocked('OUTSIDE_FROZEN_CONFIRMATION_SCOPE')
        match = observation['target_match']
        if (observation.get('explicit') is not True or match.get('confirmed') is not True
                or match.get('target_id') != observation.get('target_id')
                or match.get('target') != observation.get('target') or not match.get('reason')):
            raise Blocked('EXPLICIT_SAME_TARGET_MATCH_REQUIRED')
        loc = observation['locator']; a, b = loc['start'], loc['end']
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(doc['body']):
            raise Blocked('INVALID_CONFIRMATION_LOCATOR')
        if not engine.PUBLIC_CONFIRMATION.search(doc['body'][a:b]):
            raise Blocked('NO_EXPLICIT_CONFIRMATION_IN_LOCATOR')
        key = _id(observation['target_id']); history = root / 'confirmation-history' / key
        oid = engine.digest(observation); history_path = history / (oid + '.json')
        if history_path.exists():
            _read(history_path)
            return {'status': 'ALREADY_APPLIED', 'evaluation': _report(root)}
        first_path = root / 'confirmations' / (key + '.json')
        first = _read(first_path) if first_path.exists() else None
        # A late-discovered earlier source is appended, never silently relabelled as success.
        earlier = bool(first and published < engine.clock(first['first_scope_confirmation_at']))
        record = {'format': 'bct-prospective-scope-confirmation-v1', 'mode': 'LIVE',
                  'target_id': observation['target_id'], 'target': observation['target'],
                  'first_scope_confirmation_at': doc['published_at'], 'publication_timestamp': doc['published_at'],
                  'observed_at': _now(), 'confirmation_document': deepcopy(doc), 'locator': deepcopy(loc),
                  'target_match': deepcopy(match), 'T_global': 'UNKNOWN',
                  'confirmation_source_universe': session['confirmation_source_universe'],
                  'earlier_than_frozen_first_scope_confirmation': earlier}
        if first is None:
            first = _write(first_path, record)
        _write(history_path, {**record, 'first_confirmation_snapshot_sha256': first['record_sha256']})
        return {'status': 'APPLIED', 'evaluation': _report(root)}


def _report(root):
    session = _session(root)
    candidates = {r['target_id']: r for r in map(_read, (root / 'candidates').glob('*.json'))}
    confirmations = {r['target_id']: r for r in map(_read, (root / 'confirmations').glob('*.json'))}
    for p in (root / 'runs').glob('*.json'):
        run_record = _read(p)
        for c in run_record['engine_result']['candidates']:
            first = candidates.get(c['target_id'])
            if not first or first['record_sha256'] != run_record['first_snapshot_references'][c['target_id']]:
                raise Blocked('FIRST_CANDIDATE_SNAPSHOT_CHANGED_OR_MISSING')
    for directory, firsts in [('candidate-history', candidates), ('confirmation-history', confirmations)]:
        for p in (root / directory).glob('*/*.json'):
            if _read(p)['target_id'] not in firsts:
                raise Blocked('FIRST_SNAPSHOT_MISSING')
    early_outcomes = {}
    for run_record in sorted((_read(p) for p in (root / 'runs').glob('*.json')),
                             key=lambda r: r['engine_result']['computed_at']):
        if run_record['engine_result'].get('format') == 'bct-early-forecast-v1':
            for outcome in run_record['engine_result']['outcomes']:
                early_outcomes[outcome['target_id']] = outcome
    rows = []
    for tid in sorted(set(candidates) | set(confirmations) | set(early_outcomes)):
        c, t = candidates.get(tid), confirmations.get(tid)
        for h in (root / 'candidate-history' / _id(tid)).glob('*.json'):
            record = _read(h)
            if not c or record['first_snapshot_sha256'] != c['record_sha256']:
                raise Blocked('FIRST_CANDIDATE_SNAPSHOT_CHANGED_OR_MISSING')
        earlier = False
        for h in (root / 'confirmation-history' / _id(tid)).glob('*.json'):
            record = _read(h)
            if not t or record['first_confirmation_snapshot_sha256'] != t['record_sha256']:
                raise Blocked('FIRST_CONFIRMATION_SNAPSHOT_CHANGED_OR_MISSING')
            earlier |= record['earlier_than_frozen_first_scope_confirmation']
        days = None
        if earlier:
            status = 'BLOCKED_EARLIER_SCOPE_CONFIRMATION'
        elif t and c:
            days = (engine.clock(t['first_scope_confirmation_at']) - engine.clock(c['candidate_first_detected_at'])).total_seconds()/86400
            status = 'SUCCESS' if days > 0 else 'MISSED_EARLY_DETECTION'
        elif t:
            status = 'NO_DETECTION'
        else:
            status = 'OPEN'
        eo = early_outcomes.get(tid, {})
        if status in ('OPEN', 'NO_DETECTION') and eo.get('state') in ('REFUTED', 'MISSED_EARLY_DETECTION'):
            confirmation_at = eo.get('confirmation_at')
            if eo['state'] == 'REFUTED' or not c or (confirmation_at and engine.clock(confirmation_at) <= engine.clock(c['candidate_first_detected_at'])):
                status = eo['state']
        if not c and not t and status == 'OPEN':
            status = eo.get('state', 'DATA_WAIT')
        rows.append({'target_id': tid, 'target': (c or t or eo).get('target', tid),
                     'candidate_first_detected_at': c['candidate_first_detected_at'] if c else None,
                     'first_scope_confirmation_at': t['first_scope_confirmation_at'] if t else None,
                     'T_global': 'UNKNOWN', 'lead_time_days': days, 'status': status})
    return stamp_export({'mode': 'LIVE', 'session_started_at': session['started_at'],
                         'confirmation_source_universe': session['confirmation_source_universe'],
                         'rows': rows, 'overall_performance_PASS': None,
                         'note': 'Individual scoped results only; no global firstness or aggregate performance PASS claim.'})


def report(root):
    with _lock(root) as root:
        return _report(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('start'); init.add_argument('--feeds', type=Path, default=Path('rss_feeds.yaml'))
    for name in ('run', 'run-early', 'observe'):
        command = commands.add_parser(name); command.add_argument('--input', type=Path, required=True)
    commands.add_parser('report')
    args = parser.parse_args()
    try:
        value = start(args.store, args.feeds) if args.command == 'start' else report(args.store) if args.command == 'report' else (
            (lambda root, batch: run(root, batch, early=True)) if args.command == 'run-early' else run if args.command == 'run' else observe)(args.store, json.loads(args.input.read_text()))
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'state': 'BLOCKED', 'reason': str(exc)})); raise SystemExit(1)


if __name__ == '__main__':
    main()
