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

def test_actual_product_priority_and_other_valid_publishers_are_not_silently_excluded():
    a=sample(1,host="random-aggregator.example")
    b=sample(2);b["scope_facts"][0]["target"]="generic update"
    c=sample(3)
    ids,_,due=select({r["id"]:r for r in [a,b,c]})
    assert due==3 and set(ids)=={a["id"],b["id"],c["id"]}
    assert ids.index(a["id"])<ids.index(b["id"])
    assert ids.index(c["id"])<ids.index(b["id"])

def test_all_publisher_bounded_fair_selection_and_ssrf_url_holds():
    entries=[sample(i,host=f"publisher-{i%11}.example.com") for i in range(80)]
    ids,hosts,due=select({x["id"]:x for x in entries})
    assert due==80 and len(ids)==24
    assert len(set(ids))==24
    assert len(hosts)>=6 and max(hosts.values())<=4
    for invalid in ("127.0.0.1","localhost","news.example.local","[::1]"):
        assert not mod.accepted_url("http://"+invalid+"/page")
    assert not mod.accepted_url("file:///etc/passwd")
    assert not mod.accepted_url("https://news.example.com:8080/page")
    assert not mod.accepted_url("https://user:pass@news.example.com/")
    assert mod.accepted_url("https://example.com/article")

def test_previously_attempted_cross_publisher_items_are_not_retried():
    old=sample(1,host="new-publisher.example",attempt=True)
    fresh=sample(2,host="second-publisher.example")
    ids,_,due=select({a["id"]:a for a in [old,fresh]})
    assert ids==[fresh["id"]] and due==1

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
    assert "cron: '17 */2 * * *'" in workflow
    assert "python tools/bct_original_proof_backfill.py" in workflow


def test_successful_original_reproof_triggers_the_existing_public_pages_refresh():
    wf=(Path(__file__).resolve().parents[1]/".github/workflows/ui-pages.yml").read_text()
    assert "'BCT recurring original-source verification backlog (bounded)'" in wf
    assert "github.event.workflow_run.name != 'BCT recurring original-source verification backlog (bounded)'" in wf
    assert "github.event.workflow_run.conclusion == 'success'" in wf
    assert "group: bct-readonly-pages" in wf
    assert "ref: '6e788d18cf85fdb834b451bb35585a8b58925301'" in wf
