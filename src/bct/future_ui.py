"""Current display projection; authoritative histories stay in full sidecars."""
from copy import deepcopy
import gzip
import hashlib
import json


def compact(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


def project(path, document):
    if path=='future-tracking.json':
        return {k:deepcopy(document[k]) for k in ('version','updated_at','targets') if k in document}
    summary=deepcopy(document.get('summary',{}))
    for field in ('operation_observation','prd_operation_observation'):
        if isinstance(summary.get(field),dict):
            summary[field]={k:v for k,v in summary[field].items() if k not in ('samples','history','observations')}
    if isinstance(summary.get('review_queue'),dict):
        summary['review_queue']['preview']=summary['review_queue'].get('preview',[])[:5]
    records={}
    for key, record in document.get('results',{}).items():
        digest=record.get('current_body_sha256') or record.get('body_sha256')
        version=record.get('versions',{}).get(digest,{})
        current={**record,**version,**version.get('screening',{})}
        fields=('id','title','url','source','checked_at','candidate','reason','body_status',
                'evidence','evidence_locations','body_sha256','current_body_sha256')
        records[key]={k:deepcopy(current[k]) for k in fields if k in current}
        for field in ('title','url','source','checked_at'):
            if field in record:records[key][field]=deepcopy(record[field])
    hypotheses={}
    evidence_fields=('document_id','body_sha256','url','role','target','quantity','unit',
                     'need_date','available_date','actual_statement','locator')
    for key, record in document.get('hypotheses',{}).items():
        current=deepcopy(record.get('current',{}))
        current['evidence']=[{f:deepcopy(ref[f]) for f in evidence_fields if f in ref}
                             for ref in current.get('evidence',[])]
        current.pop('related_evidence',None)
        hypotheses[key]={'first_detected_at':record.get('first_detected_at'),'current':current}
    result={'version':document.get('version'),'results':records,'summary':summary,
            'hypotheses':hypotheses,'bundles':deepcopy(document.get('bundles',{}))}
    if 'prospective' in document:result['prospective']=deepcopy(document['prospective'])
    return result


def display_blob(path, document, full_document_sha256):
    payload=compact(project(path,document))
    envelope={'format':'bct-sidecar-display-v1','source_document_sha256':full_document_sha256,
              'payload_sha256':hashlib.sha256(payload).hexdigest(),'payload':payload.decode()}
    return gzip.compress(compact(envelope),mtime=0)
