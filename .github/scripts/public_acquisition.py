"""Validate public acquisition counters only; no engines or source documents."""
from datetime import datetime
import re

FORMAT='bct-public-acquisition-1'
REPOSITORY='irewon1-lgtm/bottleneck-control-tower'
OBJECTIVE_VERSION='bct-objective-1'
OBJECTIVE_SHA256='0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7'
UNITS={'new_seed_attempts':'SEED_CAPTURE_OUTCOMES_NOT_HTTP_REQUESTS',
       'new_verified_documents':'NEW_SOURCE_VERIFIED_DOCUMENTS',
       'new_seed_statuses':'SEED_CAPTURE_OUTCOMES_BY_FIXED_CODE'}
STATUS_CODES={'CAPTURED','PROVENANCE_BLOCKED','DUPLICATE_BODY_EXCLUDED',
              'EXISTING_CORPUS_EXCLUDED','BEFORE_NEW_COLLECTION_CUTOVER',
              'TIMEOUT','CONNECT_BLOCKED','NETWORK_FAILED'}
COUNT_KEYS={'new_URLs','new_seed_attempts','new_seed_statuses','new_verified_documents',
            'additional_bodies_acquired','valid_additional_primary_documents',
            'body_HTTP_requests','body_pending'}
FIELDS={'format','repository','run_id','run_attempt','head_sha','RSS_run_id','RSS_run_attempt','RSS_manifest_sha256',
        'collection_started_at','acquisition_started_at','completed_at','scope_reader_version',
        'counts','units','source_integrity_state','unverified_source_holds',
        'objective_version','objective_sha256'}


def count(value, *, nullable=True):
    return (nullable and value is None) or type(value)is int and 0<=value<=1_000_000


def validate_receipt(value):
    """Fail closed on added fields or free-form source/error content."""
    if not isinstance(value,dict) or set(value)!=FIELDS:
        raise ValueError('PUBLIC_ACQUISITION_FIELDS')
    if (value['format']!=FORMAT or value['repository']!=REPOSITORY
            or value['objective_version']!=OBJECTIVE_VERSION
            or value['objective_sha256']!=OBJECTIVE_SHA256
            or any(type(value[k])is not int or value[k]<=0 for k in ('run_id','run_attempt','RSS_run_id','RSS_run_attempt'))
            or not isinstance(value['head_sha'],str) or not re.fullmatch('[0-9a-f]{40}',value['head_sha'])
            or not isinstance(value['RSS_manifest_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['RSS_manifest_sha256'])):
        raise ValueError('PUBLIC_ACQUISITION_BINDING')
    try:
        for key in ('collection_started_at','acquisition_started_at','completed_at'):
            if datetime.fromisoformat(value[key].replace('Z','+00:00')).tzinfo is None:raise ValueError
    except (ValueError,TypeError,AttributeError):raise ValueError('PUBLIC_ACQUISITION_TIME') from None
    counters=value['counts']
    if not isinstance(counters,dict) or set(counters)!=COUNT_KEYS or value['units']!=UNITS:
        raise ValueError('PUBLIC_ACQUISITION_COUNTER_FIELDS')
    if any(not count(v) for k,v in counters.items() if k!='new_seed_statuses') or not count(counters['new_URLs'],nullable=False):
        raise ValueError('PUBLIC_ACQUISITION_COUNTER')
    statuses=counters['new_seed_statuses']
    if statuses is not None:
        if not isinstance(statuses,dict) or any(not isinstance(k,str)
                or (k not in STATUS_CODES and not re.fullmatch(r'HTTP_[1-5][0-9]{2}',k))
                or not count(v,nullable=False) for k,v in statuses.items()):
            raise ValueError('PUBLIC_ACQUISITION_STATUS_CODE')
    reader=value['scope_reader_version']
    if reader is not None and (not isinstance(reader,str) or not
            (re.fullmatch(r'source-scope-reader-[0-9]+',reader) or reader=='LEGACY_RECEIPT_NO_REPROCESSING')):
        raise ValueError('PUBLIC_ACQUISITION_READER_VERSION')
    if (value['source_integrity_state']not in ('NOT_SCANNED_NO_NEW_DOCUMENTS','VERIFIED_INPUTS','PARTIAL_HOLD','UNVERIFIED')
            or not count(value['unverified_source_holds'])):
        raise ValueError('PUBLIC_ACQUISITION_INTEGRITY_STATE')
    return value
