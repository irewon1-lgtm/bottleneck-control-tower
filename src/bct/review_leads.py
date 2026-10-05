"""Source-bound manual research cards, separate from EARLY and LIVE engines.

This module validates attributed annotations; it is not an automatic fact reader.
No collector, v2 evaluator, operational store or performance counter is invoked.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from .objective_lock import require_objective, stamp_export

VERSION = 'BCT_REVIEW_LEAD_RULES_1'
FORMAT = 'bct-research-review-record-v1'
UNKNOWN = 'UNKNOWN'
STATES = {'REVIEW_LEAD', 'HOLD', 'EXCLUDED', 'CONFIRMATION', 'REFUTED'}
CHANGE_ROLES = {'DEMAND', 'SUPPLY', 'RAMP', 'QUALIFICATION', 'COMPONENT'}


def now():return datetime.now(timezone.utc).isoformat()


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def read_json(path):return json.loads(Path(path).read_text())


def sealed_read(path):
    record = read_json(path); require_objective(record)
    if record.get('record_sha256') != digest({k:v for k,v in record.items() if k!='record_sha256'}):
        raise ValueError('REVIEW_RECORD_INTEGRITY_MISMATCH')
    if record.get('review_rules_version') != VERSION:
        raise ValueError('REVIEW_RULES_VERSION_MISMATCH')
    return record


def write_first(path, value):
    record = stamp_export(value); record['record_sha256'] = digest(record)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:json.dump(record, stream, ensure_ascii=False, indent=2)
    path.chmod(0o444)
    return record


def binding(contract):
    require_objective(contract)
    if contract['review_rules_version'] != VERSION:
        raise ValueError('REVIEW_RULES_VERSION_MISMATCH')
    if datetime.fromisoformat(contract['applies_from']).tzinfo is None:
        raise ValueError('REVIEW_ACTIVATION_TIMEZONE_REQUIRED')
    return {'review_rules_version':VERSION, 'review_contract_version':contract['review_contract_version'],
        'contract_sha256':digest(contract), 'implementation_sha256':digest(Path(__file__).read_bytes()),
        'applies_from':contract['applies_from']}


@contextmanager
def locked(root):
    root = Path(root).resolve()
    if ('live-state' in root.parts or (root/'session.json').exists() or
            'v2-origin-count-20261005' in root.parts):
        raise ValueError('PROTECTED_STORE_FORBIDDEN')
    root.mkdir(parents=True, exist_ok=True)
    with (root/'.review-lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:yield root
        finally:fcntl.flock(stream, fcntl.LOCK_UN)


def activate(root, contract):
    current = binding(contract); path = root/'activation.json'
    if path.exists():
        old = sealed_read(path)
        if any(old[k]!=v for k,v in current.items()):
            raise ValueError('REVIEW_STORE_BINDING_CHANGED')
        return old
    return write_first(path, {**current, 'format':'bct-review-activation-v1',
        'activated_at':now(), 'EARLY_success':False, 'LIVE_writes':0})


def documents(bundle):
    require_objective(bundle)
    result = {}
    for doc in bundle['documents']:
        if digest(doc['body'].encode())!=doc['body_sha256'] or doc.get('version',doc['body_sha256'])!=doc['body_sha256']:
            raise ValueError('SOURCE_BODY_VERSION_MISMATCH')
        if doc['document_id'] in result:
            raise ValueError('DUPLICATE_REVIEW_DOCUMENT_ID')
        result[doc['document_id']] = doc
    return result


def reference(ref, docs):
    doc = docs[ref['document_id']]; a, b = ref['locator']['start'], ref['locator']['end']
    if (type(a) is not int or type(b) is not int or not 0<=a<b<=len(doc['body']) or
            ref['body_sha256']!=doc['body_sha256'] or doc['body'][a:b]!=ref['quote']):
        raise ValueError('SOURCE_REFERENCE_MISMATCH')
    return ref


def validate_fields(fields, docs):
    for value in fields.values():
        if value['value'] != reference(value['reference'],docs)['quote']:
            raise ValueError('SCOPE_VALUE_NOT_LITERAL_SOURCE')


def assess(annotation, docs):
    """Generic gates on attributed readings; never substitute EARLY eligibility."""
    if not annotation.get('annotation_method') or not annotation.get('annotator'):
        raise ValueError('ANNOTATION_ATTRIBUTION_REQUIRED')
    fields = annotation['scope_fields']; validate_fields(fields, docs)
    facts = annotation['facts']; ids = {f['fact_id'] for f in facts}
    if len(ids)!=len(facts):raise ValueError('DUPLICATE_FACT_ID')
    mismatches = []
    for fact in facts:
        reference(fact['reference'],docs); validate_fields(fact.get('scope_fields',{}),docs)
        for key, field in fact.get('scope_fields',{}).items():
            if key in fields and fields[key]['value'].casefold()!=field['value'].casefold():
                mismatches.append(key)
    for ref in annotation.get('relation_references',[]):reference(ref,docs)
    for evidence in annotation.get('counter_evidence',[]):reference(evidence['reference'],docs)
    for period in annotation.get('period_expressions',[]):
        ref = reference(period['reference'],docs)
        if period['raw'] not in ref['quote'] or period['normalized']!=UNKNOWN:
            raise ValueError('UNSUPPORTED_REVIEW_PERIOD_MUST_STAY_RAW_UNKNOWN')
    confirmation = annotation['confirmation']
    if confirmation['same_TARGET'] not in ('YES','NO',UNKNOWN) or confirmation['document'] not in ('YES','NO',UNKNOWN):
        raise ValueError('CONFIRMATION_TRI_STATE_REQUIRED')
    for ref in confirmation.get('references',[]):reference(ref,docs)
    if confirmation['same_TARGET']=='YES' and not confirmation.get('references'):
        raise ValueError('CONFIRMATION_REFERENCE_REQUIRED')
    if any(x.get('status')!=UNKNOWN for x in annotation['unknowns']):
        raise ValueError('UNKNOWN_NOT_PASS')
    source_ids = {f['reference']['document_id'] for f in facts} | {f['reference']['document_id'] for f in fields.values()}
    if not source_ids:raise ValueError('SOURCE_BOUND_SCOPE_REQUIRED')
    if mismatches or annotation['scope_relation']=='MISMATCH':
        return 'EXCLUDED', ['EXPLICIT_SCOPE_MISMATCH'], source_ids
    if annotation['scope_relation']!= 'MATCH':return 'HOLD', ['SCOPE_RELATION_UNKNOWN'], source_ids
    if any(docs[i].get('provenance_verified') is not True for i in source_ids):
        return 'HOLD', ['SOURCE_PROVENANCE_UNVERIFIED'], source_ids
    if confirmation['same_TARGET']=='YES':return 'CONFIRMATION', ['PUBLIC_SAME_TARGET_BOTTLENECK'], source_ids
    if confirmation['document']=='YES' and confirmation['same_TARGET']==UNKNOWN:
        return 'HOLD', ['POSSIBLE_PRIOR_CONFIRMATION'], source_ids
    if confirmation['document']==UNKNOWN or confirmation['same_TARGET']==UNKNOWN:
        return 'HOLD', ['CONFIRMATION_REVIEW_INCOMPLETE'], source_ids
    changes = [f for f in facts if f['role'] in CHANGE_ROLES and f['evidence_kind'] in ('FACT','EXPLICIT_PLAN')]
    if not changes:return 'EXCLUDED', ['NO_FACTUAL_PRECURSOR_CHANGE'], source_ids
    hypothesis = annotation['hypothesis']
    linked = set(hypothesis['affected_fact_ids'])
    if not linked.issubset(ids):raise ValueError('HYPOTHESIS_FACT_REFERENCE_MISSING')
    if (not fields or hypothesis['link_assessment']!='SPECIFIC' or not linked or
            not linked.intersection(f['fact_id'] for f in changes) or
            not hypothesis.get('mechanism') or not hypothesis.get('assumptions') or
            not annotation.get('questions') or not annotation.get('refutation_conditions')):
        return 'HOLD', ['TARGET_SPECIFIC_RESEARCH_LINK_INSUFFICIENT'], source_ids
    return 'REVIEW_LEAD', ['SOURCE_BOUND_CHANGE_AND_FALSIFIABLE_RESEARCH_QUESTION'], source_ids


def make_card(annotation, docs, contract):
    state, reasons, source_ids = assess(annotation,docs)
    identity = {'scope':annotation['scope_fields'], 'anchor_documents':sorted(source_ids),
                'hypothesis_key':annotation['hypothesis_key']}
    review_id = 'review-'+digest(identity)[:24]
    facts = annotation['facts']; source_records = []
    for did in sorted(source_ids):
        d = docs[did]
        source_records.append({k:d.get(k,UNKNOWN) for k in ('document_id','origin_id','origin_url',
            'origin_publisher','body_sha256','published_at','publication_precision','acquired_at','available_at')})
    origin_ids = {d['origin_id'] for d in source_records}
    recorded = now()
    mode = 'BACKFILL' if any(d['published_at'][:10]<=contract['applies_from'][:10] for d in source_records) else 'PROSPECTIVE_REVIEW'
    return {**binding(contract), 'format':FORMAT, 'review_id':review_id,
        'formal_TARGET_id':None, 'target':annotation['target'], 'source_supported_scope':annotation['scope_fields'],
        'sources':source_records, 'source_observations':facts,
        'confirmed_facts':[f for f in facts if f['evidence_kind'] in ('FACT','EXPLICIT_PLAN')],
        'analysis_hypothesis':annotation['hypothesis'],
        'UNKNOWN':annotation['unknowns'], 'period_expressions':annotation.get('period_expressions',[]),
        'counter_evidence':annotation.get('counter_evidence',[]), 'refutation_conditions':annotation['refutation_conditions'],
        'next_questions':annotation['questions'], 'source_status':{'observed_origin_count':len(origin_ids),
            'single_source':len(origin_ids)==1, 'independent_origin_verification':UNKNOWN,
            'republication':annotation.get('republication',UNKNOWN)}, 'confirmation':annotation['confirmation'],
        'existing_v2_reference':annotation['existing_v2_reference'], 'status':state, 'reasons':reasons,
        'mode':mode, 'first_review_recorded_at':recorded,
        'strict_candidate_first_met_at':UNKNOWN, 'T':UNKNOWN, 'T_scope':UNKNOWN,
        'annotation':{k:annotation[k] for k in ('annotation_method','annotator','annotated_at')},
        'annotation_sha256':digest(annotation), 'EARLY_success':False, 'leading_detection_success':False,
        'performance_evaluation':False, 'LIVE_writes':0}


def load_store(root):
    root = Path(root); activation = sealed_read(root/'activation.json')
    output = []
    for path in sorted((root/'first').glob('*.json')):
        first = sealed_read(path)
        if first['format']!=FORMAT:raise ValueError('NOT_REVIEW_LEAD_STORE')
        history = sorted((sealed_read(p) for p in (root/'history'/first['review_id']).glob('*.json')),
                         key=lambda r:(r['recorded_at'],r['record_sha256']))
        latest = next((h['status_after'] for h in reversed(history) if h.get('status_after')), first['status'])
        output.append({'first':first, 'history':history, 'current_status':latest})
    return stamp_export({'review_rules_version':VERSION,'activation':activation,'records':output,
        'status_counts':{s:sum(r['current_status']==s for r in output) for s in sorted(STATES)},
        'EARLY_count':0,'leading_detection_success_count':0})


def generate(bundle, contract, root):
    docs = documents(bundle)
    with locked(root) as root:
        activate(root,contract); created=0; seen={}
        for annotation in bundle['annotations']:
            card = make_card(annotation,docs,contract)
            if card['review_id'] in seen:
                if seen[card['review_id']]!=card['annotation_sha256']:
                    raise ValueError('DUPLICATE_SCOPE_REQUIRES_MERGED_ANNOTATION')
                continue
            seen[card['review_id']]=card['annotation_sha256']; path=root/'first'/(card['review_id']+'.json')
            if path.exists():
                old = sealed_read(path)
                if old['annotation_sha256']!=card['annotation_sha256']:
                    raise ValueError('CHANGED_REVIEW_REQUIRES_EXPLICIT_APPEND_NOT_OVERWRITE')
                continue
            write_first(path,card); created+=1
        result = load_store(root); result['new_first_records']=created
        return result


def append_event(root, contract, bundle, review_id, event):
    require_objective(event)
    if event['kind'] not in ('EVIDENCE','REVIEW','CONFIRMATION','REFUTATION'):
        raise ValueError('INVALID_REVIEW_FOLLOWUP_KIND')
    if event.get('status_after') and event['status_after'] not in STATES:
        raise ValueError('REVIEW_IS_NOT_EARLY_PROMOTION')
    if not event.get('annotator') or not event.get('summary'):
        raise ValueError('FOLLOWUP_READING_ATTRIBUTION_REQUIRED')
    docs = documents(bundle)
    for ref in event.get('references',[]):reference(ref,docs)
    if event['kind'] in ('EVIDENCE','CONFIRMATION','REFUTATION') and not event.get('references'):
        raise ValueError('FOLLOWUP_EVIDENCE_REFERENCE_REQUIRED')
    with locked(root) as root:
        activate(root,contract); first=sealed_read(root/'first'/(review_id+'.json'))
        validate_fields(event.get('scope_fields',{}),docs)
        for key, field in event.get('scope_fields',{}).items():
            if key in first['source_supported_scope'] and field['value'].casefold()!=first['source_supported_scope'][key]['value'].casefold():
                raise ValueError('FOLLOWUP_SCOPE_MISMATCH')
        if event.get('status_after') in ('CONFIRMATION','REFUTED') and event.get('same_TARGET')!='YES':
            raise ValueError('FOLLOWUP_SAME_TARGET_UNVERIFIED')
        event_id=digest(event); path=root/'history'/review_id/(event_id+'.json')
        if path.exists():return sealed_read(path)
        allowed={'kind','summary','annotator','references','status_after','scope_fields','same_TARGET','unknowns','source_note'}
        return write_first(path,{**binding(contract), 'format':'bct-review-followup-v1',
            'review_id':review_id,'recorded_at':now(),'first_record_sha256':first['record_sha256'],
            **{k:v for k,v in event.items() if k in allowed},
            'source_documents':[docs[did] for did in sorted({r['document_id'] for r in event.get('references',[])})],
            'EARLY_success':False,'leading_detection_success':False})


def render(report):
    require_objective(report)
    lines=['# 1차 조사 검토 목록', '', '수동 원문 판독 주석 기반 개발 예시. BACKFILL이며 EARLY/선행탐지 성과가 아닙니다.', '']
    for item in report['records']:
        c=item['first'];lines += [f"## {c['target']} — {item['current_status']}", '',
            f"검토 ID: `{c['review_id']}` · 정식 TARGET ID: 없음 · `{c['mode']}`", '',
            '원문이 뒷받침하는 범위: '+', '.join(k+'='+v['value'] for k,v in c['source_supported_scope'].items()), '',
            f"판독: {c['annotation']['annotation_method']} / {c['annotation']['annotator']} (자동 추출 아님)", '']
        for source in c['sources']:
            lines += [f"출처: {source['origin_publisher']} · {source['origin_url']}",
                f"문서 ID: `{source['document_id']}` · SHA-256: `{source['body_sha256']}`",
                f"공개: {source['published_at']} · 확보: {source['acquired_at']} · 보존 가용: {source['available_at']}", '']
        lines += [f"최초 검토: {c['first_review_recorded_at']} · 엄격 후보 최초 충족: {UNKNOWN}", '']
        for fact in c['source_observations']:
            ref=fact['reference'];lines += [f"- 원문 사실/표현 [{fact['evidence_kind']}, {fact['modality']}]: {fact['description']}",
                f"  > {ref['quote']}", f"  위치: {ref['locator']['start']}–{ref['locator']['end']} · 문서 `{ref['document_id']}`", '']
        lines += ['가설(확인 사실과 구분): '+c['analysis_hypothesis']['mechanism'], '',
            '가정: '+'; '.join(c['analysis_hypothesis']['assumptions']), '',
            '핵심 UNKNOWN: '+'; '.join(x['field']+': '+x['question'] for x in c['UNKNOWN']), '']
        for period in c['period_expressions']:
            lines += [f"기간 원문: “{period['raw']}” · 정규화={period['normalized']} · {period['precision_note']}", '']
        lines += ['반대 근거: '+'; '.join(x['description'] for x in c['counter_evidence']) if c['counter_evidence'] else '확인된 반대 근거: 미확인', '',
            '반박 조건: '+'; '.join(c['refutation_conditions']), '', '다음 조사 질문:', '']
        lines += ['- '+q for q in c['next_questions']]
        lines += ['', f"단일 출처: {c['source_status']['single_source']} · 재인용: {c['source_status']['republication']}",
            f"confirmation 문서/같은 TARGET: {c['confirmation']['document']}/{c['confirmation']['same_TARGET']} · T/T_scope: UNKNOWN/UNKNOWN",
            '기존 V2 판정 참조: '+json.dumps(c['existing_v2_reference'],ensure_ascii=False),
            '상태 근거: '+'; '.join(c['reasons']), f"append-only 후속 기록: {len(item['history'])}개", '']
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('generate','read','append'))
    parser.add_argument('--store',type=Path,required=True);parser.add_argument('--input',type=Path)
    parser.add_argument('--contract',type=Path);parser.add_argument('--report',type=Path)
    parser.add_argument('--event',type=Path);parser.add_argument('--review-id');a=parser.parse_args()
    if a.action=='generate':result=generate(read_json(a.input),read_json(a.contract),a.store)
    elif a.action=='append':
        append_event(a.store,read_json(a.contract),read_json(a.input),a.review_id,read_json(a.event));result=load_store(a.store)
    else:result=load_store(a.store)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        a.report.with_suffix('.md').write_text(render(result))
    print(json.dumps({'new_first_records':result.get('new_first_records',0),'status_counts':result['status_counts'],
        'EARLY_count':result['EARLY_count'],'leading_detection_success_count':0},ensure_ascii=False))


if __name__=='__main__':main()
