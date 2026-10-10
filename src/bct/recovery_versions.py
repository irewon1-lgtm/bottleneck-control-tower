"""Append observed source versions; never copy an old score onto new text."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .future_bottleneck import screen
from .future_hypothesis import extract_facts


def append_observed_versions(candidates, failed_versions, observations, cache):
    updated=deepcopy(candidates);added=[]
    links: dict[str,list[dict[str,Any]]]={}
    for row in failed_versions:
        links.setdefault(row['document_id'],[]).append({
            'source_version':row['source_version'],'body_sha256':row.get('old_body_sha256'),
            'failure':row['old_failure']})
    for document_id,prior_links in links.items():
        record=updated['results'][document_id];observation=observations.get(record['url'],{})
        digest=observation.get('body_sha256');status=observation.get('body_status')
        if not digest or status not in ('FULL','PARTIAL') or digest in record.get('versions',{}):continue
        if len(digest)!=64 or any(x not in '0123456789abcdef' for x in digest):
            raise ValueError('invalid observed version digest')
        body=(Path(cache)/(digest+'.txt')).read_text()
        if sha256(body.encode()).hexdigest()!=digest or len(body)!=observation['body_chars']:
            raise ValueError('new observed source version hash/extent mismatch')
        screening=screen(body)
        source_version=sha256(json.dumps(['RECOVERY_OBSERVATION',document_id,record['url'],
            digest,observation['attempted_at']],separators=(',',':')).encode()).hexdigest()
        version={'body_sha256':digest,'body_chars':len(body),'body_status':status,
            'source_version':source_version,'checked_at':observation['attempted_at'],
            'queue_entered_at':observation['attempted_at'],
            'extraction_method':observation.get('extraction_method'),
            'completeness':deepcopy(observation.get('completeness',{})),
            'reasons':list(observation.get('reasons',[])),
            'provenance_verified':False,'publication_verified':False,
            'source_recovery':{'observed_url':record['url'],'observed_body_sha256':digest,
                'prior_versions':deepcopy(prior_links),'environment':observation.get('environment')},
            **screening,**extract_facts(body,screening)}
        record.setdefault('versions',{})[digest]=version
        added.append({'document_id':document_id,'body_sha256':digest,'body_status':status,
                      'source_version':source_version})
    # Preserve every preexisting version and the prior current decision/score.
    for document_id,old in candidates['results'].items():
        current=updated['results'][document_id]
        if {k:v for k,v in old.items() if k!='versions'}!={k:v for k,v in current.items() if k!='versions'}:
            raise ValueError('new observation changed an existing current judgment')
        if any(current.get('versions',{}).get(h)!=v for h,v in old.get('versions',{}).items()):
            raise ValueError('new observation changed preserved version history')
    return updated,added
