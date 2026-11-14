"""BCT original reproof: do not repeat any attempted source identity."""
from pathlib import Path
import pytest
from tools import bct_original_proof_backfill as mod

SHA="a"*64

def sample(i,host="freightwaves.com",attempt=False,full=True,proof=False):
    url=f"https://{host}/news/{i}"
    fp=f"fingerprint-{i}"
    x={"id":f"doc-{i}","url":url,"fingerprint":fp,"source_version":fp,
       "collected_at":"2026-11-13T01:00:00+00:00","candidate":True,
       "body_sha256":SHA,"current_body_sha256":SHA,
       "body_status":"FULL" if full else "PARTIAL",
       "versions":{SHA:{"body_status":"FULL" if full else "PARTIAL"}},
       "scope_facts":[{"role":"SUPPLY","target":"lithium",
                       "actual_statement":True,"scope_ambiguous":False}],
       "acquisition":{"versions":{fp:{"explicit_checks":(
          {"owner-directed-original-proof-43491743664":{"trigger":"SCHEDULED"}}
          if attempt else {}),"history":[]}}}}
    if proof:
        x.update(origin_id=url,origin_url=url,origin_publisher="Real Publisher",
          provenance_verified=True,provenance_evidence={
            "body_sha256":SHA,"verified_source_url":url,"source_identity":"canonical"},
          published_at="2026-11-13T01:00:00+00:00",
          publication_precision="TIMESTAMP",publication_verified=True,
          publication_evidence={"body_sha256":SHA,"source_quote":"2026-11-13T01:00:00+00:00"})
    return x

def select(entries,limit=24):
    return mod.selection({"results":entries},set(entries),limit=limit)

def test_old_attempts_are_not_requested_again():
    one=sample(1,attempt=True);two=sample(2)
    assert mod.already_reproof_attempted(one)
    assert not mod.already_reproof_attempted(two)
    ids,_,due=select({one["id"]:one,two["id"]:two})
    assert ids==[two["id"]] and due==1

def test_current_full_verified_already_completed_and_partial_are_held():
    a=sample(1,proof=True);b=sample(2,full=False);c=sample(3)
    ids,_,due=select({r["id"]:r for r in [a,b,c]})
    assert ids==[c["id"]] and due==1

def test_max_four_attempts_per_host_and_other_hosts_are_served():
    records=[sample(i) for i in range(20)]+[sample(20+i,host="breakingdefense.com") for i in range(20)]
    ids,hosts,due=select({r["id"]:r for r in records})
    assert len(ids)==8 and len(set(ids))==8
    assert hosts=={"freightwaves.com":4,"breakingdefense.com":4}
    assert due==40

def test_old_actual_product_scope_is_first_and_unapproved_hosts_excluded():
    a=sample(1,host="random-aggregator.example")
    b=sample(2);b["scope_facts"][0]["target"]="generic update"
    c=sample(3)
    ids,_,_=select({r["id"]:r for r in [a,b,c]})
    assert ids==[c["id"],b["id"]]

@pytest.mark.parametrize("limit",[0,-1,25,100,False])
def test_batch_bounds_fail_closed(limit):
    with pytest.raises(ValueError,match="BATCH_LIMIT_EXCEEDED"):
        mod.selection({"results":{}},set(),limit=limit)

def test_previous_batch_exclusion_and_CAS_preservation_are_explicit():
    script=(Path(__file__).resolve().parents[1]/"tools/bct_original_proof_backfill.py").read_text()
    assert "BCT_SOURCE_BACKFILL_MAIN_ONLY" in script
    assert 'operation_key="bct-scheduled-original-proof-"+os.environ["GITHUB_RUN_ID"]' in script
    assert 'prepared_document=change["prepared_document"]' in script
    assert 'confirmed_shortages_created":0' in script
    assert 'PASS_ATTEMPTS_SAVED_NO_VERIFIED_PROOF' in script


def test_no_shared_pending_slot_starvation():
    workflow=(Path(__file__).resolve().parents[1]/".github/workflows/bct-recurring-original-reproof.yml").read_text()
    assert "group: bct-periodic-original-proof" in workflow
    assert "group: future-bottleneck-results" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "cron: '10 0,12 * * *'" in workflow
    assert "python tools/bct_original_proof_backfill.py" in workflow
