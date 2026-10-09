import gzip
import hashlib
import json
from copy import deepcopy
from bct.future_ui import display_blob,project


def test_projection_matches_current_version_and_preserves_authoritative_history():
    document={'results':{'a':{'title':'Original','url':'https://a.test','body_status':'UNAVAILABLE',
        'current_body_sha256':'current','versions':{'current':{'body_status':'FULL','screening':{'candidate':True}},
        'old':{'body_status':'PARTIAL'}},'acquisition':{'history':[1,2]}}},
        'hypotheses':{'h':{'first_detected_at':'2026-01-01','history':[1,2],
          'current':{'stage':'S1','evidence':[{'document_id':'a','body_sha256':'current','quantity':None,'unused_history':[1,2]}]}}},
        'summary':{'review_queue':{'completed_documents':184,'failed_versions':3696,'preview':list(range(20))}}}
    before=deepcopy(document);result=project('future-candidates.json',document)
    assert document==before
    assert result['results']['a']['body_status']=='FULL' and result['results']['a']['candidate'] is True
    assert result['summary']['review_queue']['completed_documents']==184
    assert result['summary']['review_queue']['failed_versions']==3696
    assert result['hypotheses']['h']['current']['evidence'][0]['quantity'] is None
    blob=display_blob('future-candidates.json',document,'s'*64)
    assert blob==display_blob('future-candidates.json',document,'s'*64)
    envelope=json.loads(gzip.decompress(blob))
    assert hashlib.sha256(envelope['payload'].encode()).hexdigest()==envelope['payload_sha256']
    assert json.loads(envelope['payload'])==result


def test_tracking_projection_retains_all_confirmed_target_history():
    source={'version':1,'targets':[{'id':'t','history':[{'status':'FUTURE'},{'status':'OBSERVE'}]}],
            'reviews':{'archived':{'disposition':'DATA_INSUFFICIENT'}}}
    result=project('future-tracking.json',source)
    assert result['targets']==source['targets'] and source['reviews']['archived']
