"""Session 3: all-publisher original-source verification, bounded real batch.

The selected source-reading engine, CAS writer and verification policy are
imported unchanged from the reviewed BCT code. This one-shot job is scoped to
an isolated GitHub branch and never writes main, data or private CPU state.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import urlsplit

from bct.future_body import verified_source_metadata
from bct.future_bottleneck import run
from bct.future_github import GitHubTransport
from bct.future_store import store_patch
from tools.bct_original_proof_backfill import (
    already_reproof_attempted, cmd, host, qualified_fact, source
)

REPO = "irewon1-lgtm/bottleneck-control-tower"
BRANCH = "refs/heads/ops/bct-s3-batch2-all-publishers-20261114"
PIN = "4bee55936c5975d2859c9be787ef2159181baf85"
BUDGET = 24
PER_HOST = 4


def accepted_url(value):
    if not isinstance(value, str):
        return False
    try:
        u=urlsplit(value)
        h=u.hostname or ""
        if u.scheme not in ("https", "http") or u.username or u.password:
            return False
        if not h or "." not in h or h.endswith(".local") or h.lower() in ("localhost","localhost.localdomain"):
            return False
        try:
            ipaddress.ip_address(h)
            return False
        except ValueError:
            pass
        if u.port not in (None,80,443):
            return False
        return True
    except (TypeError, ValueError):
        return False


def select_all_publishers(candidates, active_ids, *, limit=BUDGET, per_host=PER_HOST):
    if type(limit) is not int or not 1 <= limit <= 24:
        raise ValueError("S3_BATCH_MUST_BE_BOUNDED")
    if type(per_host) is not int or not 1 <= per_host <= 4:
        raise ValueError("S3_HOST_CAP_INVALID")
    eligible=[]
    host_counts=Counter()
    counts=Counter()
    for docid, record in candidates.get("results", {}).items():
        if docid not in active_ids:
            counts["sidecar_not_active"]+=1
            continue
        if not source(record):
            counts["not_FULL_or_already_verified"]+=1
            continue
        if already_reproof_attempted(record):
            counts["prior_explicit_attempt_hold"]+=1
            continue
        if not accepted_url(record.get("url")):
            counts["invalid_or_nonpublic_url"]+=1
            continue
        h=host(record["url"])
        # Wider publisher pool: no hard-coded 7-host whitelist.
        eligible.append((not qualified_fact(record),
                         not bool(record.get("candidate")),
                         str(record.get("collected_at") or ""),
                         docid,h))
        host_counts[h]+=1
    eligible.sort()
    selected=[]
    selected_hosts=Counter()
    for item in eligible:
        _,_,_,docid,h=item
        if selected_hosts[h]>=per_host:
            continue
        selected.append(docid)
        selected_hosts[h]+=1
        if len(selected)>=limit:
            break
    if len(set(selected))!=len(selected):
        raise ValueError("S3_DUPLICATE_SELECTED_ID")
    return selected,dict(selected_hosts),len(eligible),dict(counts),len(host_counts)


def _self_test():
    def rec(i,h,*,attempted=False,verified=False):
        val={
           "id":str(i),"url":f"https://{h}/article/{i}",
           "candidate":True,"collected_at":"2026-11-11T00:00:00Z",
           "body_status":"FULL","body_sha256":"a"*64,
           "scope_facts":[{"role":"DEMAND","actual_statement":True,
                           "scope_ambiguous":False,"target":"battery cells"}],
        }
        if attempted:
            val["source_version"]="v1"
            val["acquisition"]={"versions":{"v1":{"explicit_checks":{
                "bct-scheduled-original-proof-old":{"trigger":"SCHEDULED"}}}}}
        if verified:
            val["provenance_verified"]=True
            val["origin_url"]=val["url"]
            val["origin_id"]="original"
            val["origin_publisher"]=h
            val["provenance_evidence"]={"body_sha256":"a"*64,
                "verified_source_url":val["url"],"source_identity":"real"}
            val["publication_verified"]=True
            val["publication_precision"]="DATE"
            val["published_at"]="2026-11-11"
            val["publication_evidence"]={"body_sha256":"a"*64,
                "source_quote":"November 11, 2026"}
        return val
    x={str(i):rec(i,f"news{i%8}.example.com") for i in range(50)}
    x["49"]=rec(49,"news0.example.com",attempted=True)
    x["48"]=rec(48,"news0.example.com",verified=True)
    ids,hosts,total,reasons,domaincount=select_all_publishers(
        {"results":x},set(x),limit=12)
    assert len(ids)==12 and len(set(ids))==12 and max(hosts.values())<=3
    assert len(hosts)>1 and "48" not in ids and "49" not in ids
    assert total==48 and domaincount==8
    assert not accepted_url("https://localhost/private")
    assert not accepted_url("http://127.0.0.1/")
    assert not accepted_url("file:///etc/passwd")
    assert accepted_url("https://news.example.com/supply.html")
    print("BCT_S3_ALL_PUBLISHER_SELECTOR_SELF_TEST_PASS=1",flush=True)


def stage():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO
        or os.environ.get("GITHUB_REF") != BRANCH
        or os.environ.get("GITHUB_EVENT_NAME") != "push"):
        raise ValueError("S3_ISOLATED_ONE_SHOT_ONLY")
    if not re.fullmatch("[0-9a-f]{40}",PIN):
        raise ValueError("S3_CODE_PIN")
    # Current main may contain only the two release receipt changes since its
    # validated code. If it moves, fail closed rather than processing stale code.
    actual_main=cmd("git","ls-remote","origin","refs/heads/main").decode().split()[0]
    if actual_main!=PIN:
        raise ValueError("S3_REVIEWED_MAIN_MOVED")
    root=Path(os.environ["RUNNER_TEMP"])/"bct-s3-all-publisher"
    root.mkdir(parents=True,exist_ok=True)
    transport=GitHubTransport(REPO,"future-bottleneck-data",os.environ["GITHUB_TOKEN"])
    prior=transport.head()
    candidates=transport.read_at("future-candidates.json",prior).document
    tracking=transport.read_at("future-tracking.json",prior).document
    if len(candidates.get("results",{}))<10483:
        raise ValueError("S3_SIDECAR_REGRESSION")
    collection_sha=cmd("git","ls-remote","origin","refs/heads/data").decode().split()[0]
    if not re.fullmatch("[0-9a-f]{40}",collection_sha):
        raise ValueError("S3_RSS_REF_MISSING")
    cmd("git","fetch","--no-tags","--depth=1","origin",collection_sha,timeout=160)
    state=json.loads(cmd("git","show",collection_sha+":state.json"))
    db_path=root/"canonical.sqlite3"
    db_path.write_bytes(cmd("git","show",collection_sha+":canonical.sqlite3",timeout=160))
    if hashlib.sha256(db_path.read_bytes()).hexdigest()!=state["sha256"]:
        raise ValueError("S3_CANONICAL_DB_SHA_MISMATCH")
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro&immutable=1",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("S3_CANONICAL_INTEGRITY")
        row=db.execute("SELECT COUNT(*),COUNT(DISTINCT id) FROM radar_items WHERE status='active'").fetchone()
        active_ids={i[0] for i in db.execute("SELECT id FROM radar_items WHERE status='active'")}
    if row[0]!=row[1] or row[0]!=state["radar_items"] or len(active_ids)!=row[0]:
        raise ValueError("S3_CANONICAL_ID_MISMATCH")
    if set(candidates["results"])-active_ids:
        raise ValueError("S3_SIDECAR_ORPHAN_SET_NONEMPTY")
    summary=Counter()
    for docid,record in candidates["results"].items():
        digest=record.get("current_body_sha256") or record.get("body_sha256")
        version=(record.get("versions") or {}).get(digest,{}) if digest else {}
        status=version.get("body_status") or record.get("body_status") or "UNKNOWN"
        summary["body_"+str(status)]+=1
        if status=="FULL":
            summary["full_total"]+=1
            if digest:
                proof=verified_source_metadata({**record,**version},digest)
                if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
                    summary["full_both_proofs"]+=1
                else:
                    summary["full_missing_proof"]+=1
    selected,hostset,eligible,holds,publishers=select_all_publishers(candidates,active_ids)
    report={
       "format":"bct-session3-cross-publisher-original-backfill-v1",
       "created_at_utc":datetime.now(timezone.utc).isoformat(),
       "source_before":prior,"collection_sha":collection_sha,
       "rss_total":len(active_ids),
       "sidecar_total":len(candidates["results"]),
       "rss_without_sidecar":len(active_ids)-len(candidates["results"]),
       "body_and_proof_counts":dict(summary),
       "prior_state_counts":holds,
       "full_eligible_all_publishers":eligible,
       "eligible_publisher_count":publishers,
       "selected_count":len(selected),
       "selected_host_counts":hostset,
       "unread_full_article_count_as_completed":False,
       "verified_shortages_created":0,
       "selected_article_ids_sha256":hashlib.sha256("|".join(sorted(selected)).encode()).hexdigest(),
       "private_source_body_published":False,
       "data_branch_writes":0,
       "research_rank_promotions":0,
       "status":"SOURCE_AUDIT_COMPLETE_NOT_ACQUIRED"
    }
    receipt=root/"receipt.json"
    def save():
        receipt.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    save()
    print("BCT_S3_INPUT_AUDIT="+json.dumps(report,ensure_ascii=False),flush=True)
    if not selected:
        report["status"]="NO_UNATTEMPTED_FULL_ORIGINALS_AVAILABLE"
        save()
        return
    c=root/"future-candidates.json"
    t=root/"future-tracking.json"
    c.write_text(json.dumps(candidates,ensure_ascii=False))
    t.write_text(json.dumps(tracking,ensure_ascii=False))
    patch=root/"patch.json"
    # The trigger prefix makes prior failed attempts visible to the existing
    # scheduled reproof selector, preventing repeat hammering.
    operation_key="bct-scheduled-original-proof-s3-"+os.environ["GITHUB_RUN_ID"]
    result=run(db_path,c,limit=len(selected),workers=4,
          tracking_path=t,cache_dir=root/"private-body",
          document_ids=selected,trigger="SCHEDULED",trigger_id=operation_key,
          patch_output=patch)
    changes=json.loads(patch.read_text())
    modified=changes["patch"]["results"]
    if not modified or not set(modified).issubset(set(selected)):
        raise ValueError("S3_UNEXPECTED_MODIFIED_RECORDS")
    verified_ids=[]
    outcomes=Counter()
    for docid,item in modified.items():
        digest=item.get("current_body_sha256") or item.get("body_sha256")
        proof=verified_source_metadata(item,digest) if digest else {}
        if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
            verified_ids.append(docid)
            outcomes["origin_publisher_and_publication_verified"]+=1
        else:
            outcomes["source_or_date_still_unverified"]+=1
        outcomes["body_"+str(item.get("body_status") or "UNKNOWN")]+=1
    report.update(status="PROCESSED_AWAITING_REMOTE_CAS",
          source_requests_attempted=len(modified),
          actual_processor_output_count=result["summary"]["processed_this_run"],
          source_proofs_before_commit=len(verified_ids),
          source_outcome_counts=dict(outcomes))
    save()
    written=store_patch(transport,"future-candidates.json",owner=changes["owner"],
            patch=changes["patch"],operation_id=changes["operation_id"],
            prepared_document=changes["prepared_document"])
    if written.status not in ("APPLIED","ALREADY_APPLIED"):
        report.update(status="CAS_SAVE_NOT_CONFIRMED",cas_reason=written.reason)
        save()
        raise ValueError("S3_CAS_SAVE_NOT_CONFIRMED")
    persisted_sha=transport.last_commit or transport.head()
    remote=transport.read_at("future-candidates.json",persisted_sha).document
    if len(remote.get("results",{})) < len(candidates["results"]):
        raise ValueError("S3_PERSISTED_CORPUS_LOSS")
    actually_verified=[]
    for docid in verified_ids:
        item=remote["results"].get(docid,{})
        digest=item.get("current_body_sha256") or item.get("body_sha256")
        proof=verified_source_metadata(item,digest) if digest else {}
        if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
            actually_verified.append(docid)
    if set(actually_verified)!=set(verified_ids):
        raise ValueError("S3_REMOTE_PROOF_READBACK_MISMATCH")
    report.update(status=("PASS_ACTUAL_ORIGINALS_SAVED_AND_RETRIEVED" if actually_verified
           else "PASS_ATTEMPTS_SAVED_BUT_NO_NEW_PROOFS"),
       source_after=persisted_sha,
       saved_current_count=len(remote["results"]),
       new_originals_verified_and_retrieved=len(actually_verified),
       verified_ids_digest=hashlib.sha256("|".join(sorted(actually_verified)).encode()).hexdigest(),
       ended_at_utc=datetime.now(timezone.utc).isoformat(),
       session3_complete=False)
    save()
    print("BCT_S3_REMOTE_PERSISTENCE="+json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    if os.environ.get("BCT_S3_SELF_TEST_ONLY")=="1":
        _self_test()
    else:
        stage()
