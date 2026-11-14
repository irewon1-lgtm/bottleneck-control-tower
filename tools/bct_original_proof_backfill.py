"""User-directed bounded original-article reproof; owns no shortlist or shortage claims.

Runs the already merged main Future collector on a bounded set of old FULL
source versions, persists only its existing source-version CAS patch, and
reads the exact published sidecar generation back. No raw body is uploaded.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import hashlib
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

REPO="irewon1-lgtm/bottleneck-control-tower"
PRIORITY_HOSTS={
"freightwaves.com","powermag.com","breakingdefense.com","defensenews.com",
"autoevolution.com","electrek.co","northernminer.com"}
SCOPE=re.compile(r"\b(?:lithium|copper|nickel|cobalt|uranium|gallium|germanium|graphite|"
                 r"battery cells?|semiconductors?|optical transceivers?|HBM|rockets?|missiles?|"
                 r"nuclear fuel|power transformers?|aircraft engines?|container ships?|"
                 r"industrial robots?|EV battery|solar modules?|wind turbines?)\b",re.I)


def cmd(*args,timeout=180):
    return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          check=True,timeout=timeout).stdout


def source(record):
    digest=record.get("current_body_sha256") or record.get("body_sha256")
    if not isinstance(digest,str) or not re.fullmatch("[0-9a-f]{64}",digest):
        return None
    saved=(record.get("versions") or {}).get(digest,{})
    status=saved.get("body_status") or record.get("body_status")
    if status!="FULL":return None
    if verified_source_metadata(record,digest).get("provenance_verified") is True:
        return None
    if verified_source_metadata(saved,digest).get("provenance_verified") is True:
        return None
    return digest


def qualified_fact(record):
    facts=record.get("scope_facts") or []
    for fact in facts:
        if not isinstance(fact,dict) or fact.get("role") not in ("DEMAND","SUPPLY","RELIEF"):
            continue
        if fact.get("actual_statement") is not True or fact.get("scope_ambiguous"):
            continue
        target=fact.get("target")
        if isinstance(target,str) and SCOPE.search(target):
            return True
    return False


def host(url):
    try:return (urlsplit(url).hostname or "").removeprefix("www.").lower()
    except (TypeError,ValueError):return ""


def selection(candidates,available_ids,*,limit=42):
    ranked=[]
    for document_id,record in candidates.get("results",{}).items():
        if document_id not in available_ids or not source(record):
            continue
        h=host(record.get("url"))
        if h not in PRIORITY_HOSTS:
            continue
        ranked.append((
            not qualified_fact(record),
            not bool(record.get("candidate")),
            str(record.get("collected_at") or ""),
            document_id,h))
    ranked.sort()
    chosen=[]; hosts=Counter()
    for _,_,_,docid,h in ranked:
        if hosts[h]>=6:continue
        chosen.append(docid);hosts[h]+=1
        if len(chosen)>=limit:break
    return chosen,dict(hosts),len(ranked)


def stage():
    root=Path(os.environ["RUNNER_TEMP"])/"bct-owner-reproof"
    root.mkdir(parents=True,exist_ok=True)
    transport=GitHubTransport(REPO,"future-bottleneck-data",os.environ["GITHUB_TOKEN"])
    prior=transport.head()
    candidates=transport.read_at("future-candidates.json",prior).document
    tracking=transport.read_at("future-tracking.json",prior).document
    if len(candidates.get("results",{}))<10327:
        raise ValueError("BCT_OLD_CANDIDATES_MISSING")
    collection_sha=cmd("git","ls-remote","origin","refs/heads/data").decode().split()[0]
    if not re.fullmatch("[0-9a-f]{40}",collection_sha):
        raise ValueError("BCT_INVALID_CANONICAL_REF")
    cmd("git","fetch","--no-tags","--depth=1","origin",collection_sha,timeout=160)
    state=json.loads(cmd("git","show",collection_sha+":state.json"))
    db_path=root/"canonical.sqlite3"
    db_path.write_bytes(cmd("git","show",collection_sha+":canonical.sqlite3",timeout=160))
    if hashlib.sha256(db_path.read_bytes()).hexdigest()!=state["sha256"]:
        raise ValueError("BCT_CANONICAL_RSS_SHA_MISMATCH")
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro&immutable=1",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("BCT_BAD_RSS_DB")
        active_ids={i[0] for i in db.execute("SELECT id FROM radar_items WHERE status='active'")}
    ids,by_host,eligible=selection(candidates,active_ids)
    if len(ids)<5:
        raise RuntimeError("BCT_INSUFFICIENT_OLD_FULL_URLS_FOR_BOUNDED_REPROOF")
    candidate_file=root/"future-candidates.json"
    tracking_file=root/"future-tracking.json"
    candidate_file.write_text(json.dumps(candidates,ensure_ascii=False))
    tracking_file.write_text(json.dumps(tracking,ensure_ascii=False))
    patch_file=root/"collection-change.json"
    report={"status":"RUNNING","collection_sha":collection_sha,
      "source_before":prior,"selected_count":len(ids),
      "eligible_host_qualified":eligible,"selected_host_counts":by_host,
      "user_directed_recheck":True,"source_downloads_attempted":0,
      "source_proofs_persisted":0,"confirmed_shortages_created":0,
      "source_bytes_published":False}
    report_path=root/"receipt.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    # This explicit trigger differs from the scheduled AUTO 3-attempt limit.
    # The only new source bytes are fetched from their public original URLs.
    operation_key="owner-directed-original-proof-"+os.environ["GITHUB_RUN_ID"]
    result=run(db_path,candidate_file,limit=len(ids),workers=4,
        tracking_path=tracking_file,cache_dir=root/"private-body",
        document_ids=ids,trigger="SCHEDULED",trigger_id=operation_key,
        patch_output=patch_file)
    change=json.loads(patch_file.read_text())
    modified=change["patch"]["results"]
    if not modified or not set(modified).issubset(set(ids)):
        raise ValueError("BCT_UNEXPECTED_RECORDS_MODIFIED")
    result_verified=[]
    observed=Counter()
    for docid,record in modified.items():
        digest=record.get("current_body_sha256") or record.get("body_sha256")
        if not digest:
            observed["no_body_hash"]+=1
            continue
        proof=verified_source_metadata(record,digest)
        if proof.get("provenance_verified") is True and proof.get("publication_verified") is True:
            result_verified.append(docid)
            observed["original_and_date_verified"]+=1
        else:
            observed["provenance_or_date_incomplete"]+=1
        status=record.get("body_status") or "UNKNOWN"
        observed["body_"+status]+=1
    report.update(status="EXTRACTED_AWAITING_CAS",
        source_downloads_attempted=len(modified),
        extractor_observations=dict(observed),
        source_proofs_before_publish=len(result_verified),
        processed_this_run=result["summary"]["processed_this_run"])
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    # Actual source attempts that failed remain recorded, but a zero-proof
    # pass is a failed promotion, never an accepted success.
    if not result_verified:
        report["status"]="NO_SOURCE_PROOF_ACCEPTED_NOT_PUBLISHED"
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        raise RuntimeError("BCT_REPROOF_NO_ELIGIBLE_ORIGINAL_DOCUMENTS")
    saved=store_patch(transport,"future-candidates.json",owner=change["owner"],
        patch=change["patch"],operation_id=change["operation_id"],
        prepared_document=change["prepared_document"])
    if saved.status not in ("APPLIED","ALREADY_APPLIED"):
        report.update(status="PENDING_CAS_NO_CONFIRMED_SAVE",reason_code=saved.reason)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        raise RuntimeError("BCT_SOURCE_PROOF_CAS_NOT_CONFIRMED")
    published=transport.last_commit or transport.head()
    remote=transport.read_at("future-candidates.json",published).document
    confirmed=[]
    for docid in result_verified:
        item=remote["results"].get(docid,{})
        digest=item.get("current_body_sha256") or item.get("body_sha256")
        meta=verified_source_metadata(item,digest)
        if meta.get("provenance_verified") is True and meta.get("publication_verified") is True:
            confirmed.append(docid)
    if set(confirmed)!=set(result_verified):
        raise ValueError("BCT_SOURCE_PROOF_READBACK_SET_DIFFERS")
    if len(remote["results"])<len(candidates["results"]):
        raise ValueError("BCT_OLD_SOURCE_INVENTORY_DELETED")
    report.update(status="PASS_SAVED_AND_RETRIEVED",source_after=published,
       source_proofs_persisted=len(confirmed),
       preserved_prior_count=len(candidates["results"]),
       saved_current_count=len(remote["results"]),
       outcome_id_hash=hashlib.sha256("|".join(sorted(confirmed)).encode()).hexdigest(),
       private_artifact_only=True)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("BCT_VERIFIED_ORIGINAL_BACKFILL_SAVED="+json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    stage()
