"""Append only real publisher-verified RSS product observations to data branch.

Source: exact 3MB acquisition CPU delta from real run 43473259686.
Never publish original article body, inferred shortages or vague commodity phrases.
All changes preserve canonical RSS and unrelated data branch files by CAS.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit,parse_qsl

RUN=43473259686
RSS_RUN=43472909460
FORMAT="bct-public-original-source-research-1"
DEST="v4-public/rss-source-research.json"
ROOT=Path(os.environ["RUNNER_TEMP"])/"bct-delta-source-audit"
REJECT_QUERY=frozenset(("token","key","secret","password","auth","signature","sig","session","api_key"))
PRODUCTS={
  "electric vehicles":"자동차·배터리",
  "trucks":"자동차·배터리",
}


def identity(entry):
    url=entry.get("origin_url")
    if not isinstance(url,str) or len(url)>2048:
        raise ValueError("BCT_SOURCE_URL_INVALID")
    try:
        u=urlsplit(url)
        if (u.scheme!="https" or not u.hostname or u.username or u.password or
                u.hostname in ("localhost",) or
                any(k.casefold() in REJECT_QUERY for k,v in parse_qsl(u.query,keep_blank_values=True))):
            raise ValueError("BCT_SOURCE_URL_NOT_PUBLIC")
        return url
    except ValueError:
        raise ValueError("BCT_SOURCE_URL_INVALID") from None


def cmd(*args,allow_missing=False):
    p=subprocess.run(args,capture_output=True,timeout=150)
    if p.returncode and not allow_missing:
        raise ValueError("BCT_GIT_OR_CAS_COMMAND_FAILED:"+args[1])
    return None if p.returncode else p.stdout


def main():
    manifest=json.loads((ROOT/"receipt.json").read_bytes())
    candidates=json.loads((ROOT/"candidates.json").read_bytes())
    if (manifest["original_verified_in_delta"]!=44 or manifest["rss_documents"]!=80
            or manifest["source_acquisition_run_id"]!=RUN or
            manifest["status_counts"]["valid_new_originals"]!=44 or
            manifest["no_full_text_published"] is not True or
            manifest["no_production_writes"] is not True):
        raise ValueError("BCT_SOURCE_DELTA_REGISTRATION_PROOF_MISSING")
    if len(candidates)!=44:
        raise ValueError("BCT_DELTA_CANDIDATE_DOCUMENT_SET_INVALID")
    next_rows={}
    rejected={}
    for record in candidates:
        url=identity(record)
        if (not isinstance(record.get("body_sha256"),str) or
                not re.fullmatch("[a-f0-9]{64}",record["body_sha256"]) or
                not re.fullmatch("[a-f0-9]{64}",str(record.get("raw_sha256"))) or
                not record.get("published_at") or not record.get("origin_publisher")):
            raise ValueError("BCT_VERIFIED_ORIGINAL_PROOF_FIELDS_MISSING")
        events=record.get("product_events") or []
        sectors={}
        for e in events:
            p=str(e.get("product") or "").strip().casefold()
            if p not in PRODUCTS:
                rejected[p]=rejected.get(p,0)+1
                continue
            loc=e.get("product_offset")
            if (not isinstance(loc,dict) or type(loc.get("start"))is not int
                    or type(loc.get("end"))is not int
                    or not 0<=loc["start"]<loc["end"]):
                raise ValueError("BCT_ORIGINAL_PRODUCT_LOCATOR_INVALID")
            sector=PRODUCTS[p]
            sectors.setdefault(sector,[]).append(e)
        if len(sectors)!=1:
            continue
        sector=list(sectors)[0]
        body_sha=record["body_sha256"]
        key="\0".join((url.split("#")[0],body_sha,sector))
        id=hashlib.sha256(key.encode()).hexdigest()
        if id in next_rows:continue
        ev=sectors[sector]
        next_rows[id]={
            "id":id,"source_document_id":record["document_id"],
            "industry":sector,
            "title":record.get("title") or "공식 원문 검증 기사",
            "url":url,
            "origin_publisher":record["origin_publisher"],
            "published_at":record["published_at"],
            "collected_at":record.get("acquired_at"),
            "body_sha256":body_sha,
            "raw_sha256":record["raw_sha256"],
            "source_run_id":RUN,"source_rss_run_id":RSS_RUN,
            "source_manifest_sha256":manifest["bundle_manifest_sha256"],
            "roles":sorted({str(t) for e in ev for t in (e.get("event_types") or [])}),
            "claim_offsets":[e["product_offset"] for e in ev[:8]],
            "product_names":sorted({str(e["product"]) for e in ev}),
            "category":"rss_source_observation",
            "verification":"ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED",
            "confirmed_future_shortage":False,
            "independent_supply_demand_pair_verified":False,
        }
    if not next_rows or len(next_rows)>5:
        raise ValueError("BCT_NO_OR_TOO_MANY_EXPLICIT_PRODUCT_SECTOR_RECORDS")
    original=cmd("git","ls-remote","origin","refs/heads/data").decode().split()[0]
    if not re.fullmatch("[0-9a-f]{40}",original):
        raise ValueError("BCT_DATA_REF_INVALID")
    cmd("git","fetch","--no-tags","--depth=1","origin",original)
    index=json.loads(cmd("git","show",original+":precursor-index.json"))
    if str(index.get("cache_run_id"))!=str(RUN) or index.get("new_verified_documents")!=44:
        raise ValueError("BCT_STALE_OR_UNMATCHED_PRECURSOR_INDEX")
    prior_bytes=cmd("git","show",original+":"+DEST,allow_missing=True)
    prior=json.loads(prior_bytes) if prior_bytes is not None else {
        "format":FORMAT,"records":{},"classification":"SOURCE_VERIFIED_NOT_VERIFIED_SHORTAGE",
        "source_run_ids":[]}
    if prior.get("format")!=FORMAT or prior.get("classification")!="SOURCE_VERIFIED_NOT_VERIFIED_SHORTAGE":
        raise ValueError("BCT_PREVIOUS_PROVENANCE_LEDGER_INVALID")
    old=prior.get("records")
    if not isinstance(old,dict):
        raise ValueError("BCT_INVALID_PREVIOUS_RECORD_SET")
    for id,v in next_rows.items():
        if id in old and old[id]!=v:
            raise ValueError("BCT_EXISTING_RESEARCH_RECEIPT_IMMUTABILITY")
    updated=dict(old)
    updated.update(next_rows)
    runs=sorted(set(prior.get("source_run_ids",[]))|{RUN})
    saved={"format":FORMAT,
         "classification":"SOURCE_VERIFIED_NOT_VERIFIED_SHORTAGE",
         "records":updated,"source_run_ids":runs,
         "original_data_ref_before":original,
         "source_archive":{"run_id":RUN,"rss_run_id":RSS_RUN,"bundle_manifest_sha256":manifest["bundle_manifest_sha256"]},
         "verified_original_record_count":len(updated)}
    raw=(json.dumps(saved,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+"\n").encode()
    out=ROOT/"source-research-publish.json"
    out.write_bytes(raw)
    # GitHub's non-force fast-forward is CAS against the actual data ref.
    # A simultaneous RSS writer makes the push fail without overwriting it.
    subprocess.run(["git","config","user.name","github-actions[bot]"],check=True)
    subprocess.run(["git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com"],check=True)
    os.environ["GIT_INDEX_FILE"]=str(ROOT/"source-research.index")
    cmd("git","read-tree",original)
    blob=cmd("git","hash-object","-w",str(out)).decode().strip()
    cmd("git","update-index","--add","--cacheinfo",f"100644,{blob},{DEST}")
    tree=cmd("git","write-tree").decode().strip()
    commit=cmd("git","commit-tree",tree,"-p",original,"-m",
        "Register actual original-source RSS product observations from verified acquisition 43473259686").decode().strip()
    pushed=subprocess.run(["git","push","origin",commit+":refs/heads/data"],capture_output=True,timeout=120)
    if pushed.returncode:
        raise RuntimeError("BCT_DATA_REF_CAS_REJECTED_PRESERVED_NO_FORCE")
    confirm=cmd("git","ls-remote","origin","refs/heads/data").decode().split()[0]
    if confirm!=commit:
        raise ValueError("BCT_DATA_REF_NOT_AT_EXPECTED_COMMIT")
    cmd("git","fetch","--no-tags","--depth=1","origin",commit)
    remote=cmd("git","show",commit+":"+DEST)
    if hashlib.sha256(remote).hexdigest()!=hashlib.sha256(raw).hexdigest():
        raise ValueError("BCT_REGISTERED_SOURCE_LEDGER_READBACK_MISMATCH")
    receipt={
       "status":"PASS_REGISTERED_AND_VERIFIED_READBACK",
       "source_acquisition_run":RUN,"rss_run":RSS_RUN,
       "added_or_reconfirmed":len(next_rows),
       "historical_research_source_records":len(old),
       "new_total_research_source_records":len(updated),
       "persisted_data_commit":commit,
       "root_sha256":hashlib.sha256(raw).hexdigest(),
       "explicit_product_scope":{k:v for k,v in sorted(rejected.items())},
       "source_articles_verified_in_delta":len(candidates),
       "independent_supply_demand_pairs_promoted":0,
       "original_article_text_published":False,
    }
    (ROOT/"publish-receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print("BCT_SOURCE_RESEARCH_ACTUALLY_REGISTERED="+json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
