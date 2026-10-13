"""Publication failures retain safe transport facts, never a false saved state."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from bct.future_github import GitHubRequestError,error_details

def load_publisher():
    script=Path(__file__).parents[1]/'.github/scripts/bct_publish_operating_queue.py'
    spec=importlib.util.spec_from_file_location('publication_error_receipt_fixture',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('status,headers,body,category',[
    (500,{'x-github-request-id':'test-service'},b'{"message":"Internal Server Error"}','GITHUB_SERVICE_ERROR'),
    (403,{'x-ratelimit-remaining':'0','x-ratelimit-reset':'1900000000','x-github-request-id':'test-rate'},b'{"message":"API rate limit exceeded"}','PRIMARY_RATE_LIMIT'),
])
def test_publication_retains_safe_github_error_without_false_commit(tmp_path,monkeypatch,status,headers,body,category):
    module=load_publisher();output=tmp_path/'output';root=tmp_path/'state'
    output.mkdir();root.mkdir()
    for name in ('bundle','queue'):(output/(name+'-change.json')).write_text('{}')
    (root/'source-recovery-versions.json').write_text('{}')
    (root/'source-recovery-attempts.jsonl').write_text('')
    (root/'recovery-preservation-seal.json').write_text('{}')
    details=error_details('POST','/git/trees',status,headers,body)
    assert details['category']==category
    def fail(*args,**kwargs):raise GitHubRequestError(details)
    monkeypatch.setattr(module,'publish_projection',fail)
    monkeypatch.setenv('GITHUB_REPOSITORY','fixture/no-network')
    monkeypatch.setenv('GITHUB_TOKEN','fixture-token-never-output')
    monkeypatch.setenv('GITHUB_RUN_ID','12345')
    monkeypatch.setattr(sys,'argv',['publisher','--output-dir',str(output),'--recovery-state',str(root)])
    assert module.main()==1
    raw=(output/'operating-publication.json').read_text();receipt=json.loads(raw)
    assert receipt['status']=='FAIL' and receipt['actual_execution'] is True
    assert receipt.get('published_commit') is None
    assert receipt['error_type']=='GitHubRequestError'
    assert receipt['github_error_details']==details and receipt['failure_code']==str(GitHubRequestError(details))
    assert 'fixture-token-never-output' not in raw and 'Internal Server Error' not in raw
