"""Read exact canonical data-branch registered original RSS source evidence.

Only the already source/artifact/hash-verified, append-only research receipts
are projected. This never equates a product mention with a qualified supply gap.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from v4_public_news_export import _cmd, _safe_link

FORMAT="bct-public-original-source-research-1"
SOURCE_RESEARCH="v4-public/rss-source-research.json"
STATUS="VERIFIED_PERSISTED_ORIGINAL_SOURCE_RESEARCH"
PRODUCT_SECTOR={"electric vehicles":"자동차·배터리","trucks":"자동차·배터리"}


def _iso(value):
    if not isinstance(value,str) or len(value)>48:return None
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError):return None


def validate(value,*,data_commit,rss_run_id):
    if (not isinstance(value,dict)
            or value.get("format")!=FORMAT
            or value.get("classification")!="SOURCE_VERIFIED_NOT_VERIFIED_SHORTAGE"
            or not re.fullmatch("[a-f0-9]{40}",str(data_commit))
            or type(rss_run_id)is not int or rss_run_id<=0):
        raise ValueError("BCT_SOURCE_RESEARCH_ROOT_INVALID")
    rows=value.get("records")
    if (not isinstance(rows,dict) or len(rows)>30000
            or type(value.get("verified_original_record_count"))is not int
            or len(rows)!=value["verified_original_record_count"]):
        raise ValueError("BCT_SOURCE_RESEARCH_RECORD_COUNT_MISMATCH")
    source=value.get("source_archive") or {}
    if (not isinstance(source,dict)
            or type(source.get("run_id"))is not int or source["run_id"]<=0
            or type(source.get("rss_run_id"))is not int
            or source["rss_run_id"]>rss_run_id
            or not re.fullmatch("[0-9a-f]{64}",str(source.get("bundle_manifest_sha256")))):
        raise ValueError("BCT_SOURCE_RESEARCH_SOURCE_ARCHIVE_INVALID")
    ids=value.get("source_run_ids")
    if not isinstance(ids,list) or ids!=sorted(set(ids)) or any(type(x)is not int or x<=0 for x in ids):
        raise ValueError("BCT_SOURCE_RESEARCH_RUN_IDS_INVALID")
    if source["run_id"] not in ids:
        raise ValueError("BCT_SOURCE_RESEARCH_ARCHIVE_RUN_NOT_INCLUDED")
    verified=[]
    for key,record in rows.items():
        if (not isinstance(record,dict) or key!=record.get("id")
                or not re.fullmatch("[a-f0-9]{64}",str(key))
                or record.get("verification")!="ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED"
                or record.get("category")!="rss_source_observation"
                or record.get("confirmed_future_shortage") is not False
                or record.get("independent_supply_demand_pair_verified") is not False
                or record.get("industry") not in PRODUCT_SECTOR.values()
                or type(record.get("source_run_id"))is not int
                or record.get("source_run_id") not in ids
                or record.get("source_rss_run_id",0)>rss_run_id
                or record.get("source_manifest_sha256")!=source["bundle_manifest_sha256"]
                or not re.fullmatch("[a-f0-9]{64}",str(record.get("body_sha256")))
                or not re.fullmatch("[a-f0-9]{64}",str(record.get("raw_sha256")))):
            raise ValueError("BCT_SOURCE_RESEARCH_RECORD_UNVERIFIED")
        url=_safe_link(record.get("url"))
        if url is None or urlsplit(url).scheme!="https":
            raise ValueError("BCT_SOURCE_RESEARCH_URL_UNSAFE")
        expect=hashlib.sha256(("\0".join((url.split("#")[0],record["body_sha256"],record["industry"]))).encode()).hexdigest()
        if expect!=key:
            raise ValueError("BCT_SOURCE_RESEARCH_BINDING_HASH_MISMATCH")
        if (not isinstance(record.get("origin_publisher"),str)
                or not record["origin_publisher"].strip()
                or record["origin_publisher"]=="UNKNOWN"
                or not _iso(record.get("published_at"))
                or not _iso(record.get("collected_at"))):
            raise ValueError("BCT_SOURCE_RESEARCH_PUBLICATION_NOT_PROVEN")
        products=record.get("product_names")
        if (not isinstance(products,list) or not products or
                any(type(p)is not str or PRODUCT_SECTOR.get(p.casefold())!=record["industry"] for p in products)):
            raise ValueError("BCT_SOURCE_RESEARCH_PRODUCT_SECTOR_AMBIGUOUS")
        locs=record.get("claim_offsets")
        if (not isinstance(locs,list) or not 1<=len(locs)<=8 or
                any(not isinstance(loc,dict) or type(loc.get("start"))is not int
                or type(loc.get("end"))is not int
                or not 0<=loc["start"]<loc["end"] for loc in locs)):
            raise ValueError("BCT_SOURCE_RESEARCH_SOURCE_OFFSETS_INVALID")
        if (not isinstance(record.get("roles"),list)
                or not record["roles"]
                or any(not isinstance(r,str) or not re.fullmatch("[A-Z_]{3,32}",r) for r in record["roles"])):
            raise ValueError("BCT_SOURCE_RESEARCH_UNSUPPORTED_EVENT_TYPE")
        approved={k:record[k] for k in (
            "id","source_document_id","industry","title","url","origin_publisher",
            "published_at","collected_at","body_sha256","roles","claim_offsets",
            "category","verification","confirmed_future_shortage")}
        approved["source_run_id"]=record["source_run_id"]
        approved["source"]="IMMUTABLE_PRECURSOR_CPU_DELTA"
        approved["source_manifest_sha256"]=record["source_manifest_sha256"]
        approved["product_names"]=products
        verified.append(approved)
    verified.sort(key=lambda r:(r["industry"],r["published_at"],r["id"]))
    return {"format":FORMAT,"status":STATUS,
        "data_commit":data_commit,"rss_run_id":rss_run_id,
        "classification":"PUBLISHER_VERIFIED_UNPAIRED_PRODUCT_OBSERVATIONS",
        "verified_original_record_count":len(verified),
        "registered_source_runs":ids,
        "source_manifest_sha256":source["bundle_manifest_sha256"],
        "records":verified}


def from_data_snapshot(repo,*,data_commit,rss_run_id):
    repo=Path(repo).resolve()
    raw=_cmd(["git","show",data_commit+":"+SOURCE_RESEARCH],cwd=repo,timeout=30)
    if len(raw)>2_000_000:raise ValueError("BCT_SOURCE_RESEARCH_PUBLIC_BYTES_EXCEEDED")
    return validate(json.loads(raw),data_commit=data_commit,rss_run_id=rss_run_id)
