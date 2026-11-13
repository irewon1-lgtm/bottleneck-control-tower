"""Register exact RSS original-source observations as provisional V4 sector evidence.

Only an immutable hash-verified Future sidecar generation is consumed. The
publisher original + publication proof MUST match the current FULL body.
A screened title, feed industry or AI hypothesis never becomes evidence.
Existing 511 historical records and S1/S2/S3/confirmed shortages are immutable.
"""
from __future__ import annotations
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from bct.future_github import assemble
from bct.future_body import verified_source_metadata
from bct.v4.dashboard import SECTORS
from v4_public_news_export import _safe_link, feed_group_hints, _domain

FORMAT = "bct-rss-sector-evidence-register-1"
SOURCE_HINT_TO_SECTOR = {
    "방산·우주":"방산·항공우주",
    "전력·발전":"전력·발전",
    "반도체·AI·데이터센터":"반도체·광통신·AI 기반시설",
    "제조·산업장비":"제조·산업설비",
    "광물·희토류":"광물·금속·희토류",
    "석유·가스·화학":"석유·가스·화학",
    "물류·항만·운송":"물류·항만·해운",
    "자동차·배터리":"자동차·배터리",
    "건설·인프라":"건설·기반시설",
    "바이오·의약":"바이오·의약",
}
# Only an explicit, unambiguous named product in a source-located claim
# establishes the sector of an article observation. Source/feed domains are
# only preliminary routing hints and cannot qualify records by themselves.
PRODUCTS = {
"방산·항공우주":r"\b(?:missiles?|munitions?|rockets?|spacecraft|satellites?|launch vehicles?|rocket motors?|propellants?|fighter jets?|aircraft engines?)\b",
"전력·발전":r"\b(?:power transformers?|transmission grids?|electrical substations?|grid transformers?|power generation turbines?|HVDC)\b",
"반도체·광통신·AI 기반시설":r"\b(?:semiconductor(?:s)?|silicon wafers?|HBM|high.bandwidth.memory|chiplets?|photonic chips?|optical transceivers?|lithography|EUV scanners?|advanced packaging)\b",
"제조·산업설비":r"\b(?:industrial robots?|CNC machines?|manufacturing equipment|machine tools?|industrial automation lines?)\b",
"광물·금속·희토류":r"\b(?:lithium|copper|cobalt|nickel|tungsten|gallium|germanium|graphite|rare earths?|neodymium|dysprosium|antimony)\b",
"석유·가스·화학":r"\b(?:LNG|liquefied natural gas|petrochemicals?|ethylene|crude oil|oil rigs?|chemical feedstocks?)\b",
"물류·항만·해운":r"\b(?:container ships?|shipping vessels?|port cranes?|bulk carriers?|freight terminals?|ocean freight)\b",
"자동차·배터리":r"\b(?:EV battery cells?|battery cathodes?|battery anodes?|electric vehicles?|automotive batteries?|vehicle assembly lines?)\b",
"건설·기반시설":r"\b(?:construction cement|construction steel|rail infrastructure|bridge beams?|building materials?)\b",
"바이오·의약":r"\b(?:vaccines?|pharmaceutical(?:s)?|biologic drugs?|sterile injectables?|active pharmaceutical ingredients?|drug substances?|CDMO)\b",
"에너지·원자력":r"\b(?:uranium|HALEU|nuclear reactors?|small modular reactors?|nuclear fuel|enriched uranium)\b"
}
PATTERNS = {k:re.compile(v,re.I) for k,v in PRODUCTS.items()}
VALID_SECTORS=set(SECTORS.values())
VALID_ROLES={"DEMAND","SUPPLY","RELIEF"}


def _cmd(repo,*args):
    return subprocess.run(args,check=True,cwd=repo,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,timeout=150).stdout


def _record_body(record):
    digest=record.get("current_body_sha256") or record.get("body_sha256")
    if not isinstance(digest,str) or not re.fullmatch("[0-9a-f]{64}",digest):
        return None,None
    version=(record.get("versions") or {}).get(digest) or {}
    status=version.get("body_status") or record.get("body_status")
    if status not in ("FULL","PARTIAL","UNAVAILABLE","BODY_OK"):
        return None,None
    return digest,{**record,**version,"body_status":status}


def _sector(claims):
    named=set()
    for claim in claims:
        if not isinstance(claim,dict):continue
        target=claim.get("target")
        if not isinstance(target,str) or target=="UNKNOWN":continue
        for k,pattern in PATTERNS.items():
            if pattern.search(target):named.add(k)
    return next(iter(named)) if len(named)==1 else None


def _claims(record,body_chars):
    claims=[]
    for f in record.get("scope_facts") or []:
        if not isinstance(f,dict) or f.get("role") not in VALID_ROLES:
            continue
        loc=f.get("locator")
        if not isinstance(loc,dict):continue
        start,end=loc.get("start"),loc.get("end")
        if not (type(start) is int and type(end) is int and 0<=start<end<=body_chars):
            continue
        claims.append(f)
    return claims


def register(sidecar,*,sidecar_sha,feed_domains):
    if (not re.fullmatch("[0-9a-f]{40}",str(sidecar_sha))
            or not isinstance(sidecar.get("results"),dict)):
        raise ValueError("RSS_RESEARCH_SOURCE_INVALID")
    counts=Counter()
    groups=defaultdict(lambda:Counter())
    preview=defaultdict(list)
    records=[]
    dedup=set()
    for document_id,doc in sidecar["results"].items():
        counts["screened_articles"]+=1
        if not isinstance(doc,dict) or not isinstance(document_id,str):
            raise ValueError("RSS_RESEARCH_BAD_RECORD")
        body_hash,version=_record_body(doc)
        if version is None:
            counts["no_usable_body_hash"]+=1
            continue
        if version["body_status"]!="FULL":
            counts["not_full"]+=1
            continue
        chars=version.get("body_chars")
        if type(chars) is not int or chars<=0:
            counts["bad_body_extent"]+=1
            continue
        claims=_claims(version,chars)
        roles=sorted({f["role"] for f in claims})
        url=_safe_link(doc.get("url"))
        if not url or not roles:
            counts["no_safe_source_or_claim"]+=1
            continue
        hint=feed_domains.get(_domain(url),"분야 확인 필요")
        # The hint is intentionally NOT used to qualify a sector.
        group=SOURCE_HINT_TO_SECTOR.get(hint,"산업 추가 확인")
        counts["FULL_with_located_screening_claim"]+=1
        groups[group]["source_located_leads"]+=1
        metadata=verified_source_metadata(version,body_hash)
        proof=(metadata.get("provenance_verified") is True
               and metadata.get("publication_verified") is True)
        if not proof:
            counts["awaiting_original_publisher_proof"]+=1
            groups[group]["proof_pending"]+=1
        else:
            counts["verified_original_and_publication"]+=1
            groups[group]["original_verified"]+=1
        if len(preview[group])<12:
            preview[group].append({
                "id":document_id[:72],
                "title":str(doc.get("title") or "")[:150],
                "url":url,
                "collected_at":str(doc.get("collected_at") or "")[:40],
                "roles":roles,"publisher_verified":bool(proof)
            })
        if not proof:
            continue
        literal=[f for f in claims if (f.get("actual_statement") is True
            and f.get("target") not in (None,"UNKNOWN","")
            and not f.get("scope_ambiguous"))]
        sector=_sector(literal)
        if sector is None or sector not in VALID_SECTORS:
            counts["verified_original_needing_product_sector_review"]+=1
            continue
        canonical=_safe_link(metadata.get("origin_url"))
        if not canonical:
            counts["verified_original_missing_safe_link"]+=1
            continue
        key=(canonical.split("#")[0],body_hash,sector)
        if key in dedup:
            counts["deduplicated_exact_origin_body_sector"]+=1
            continue
        dedup.add(key)
        record_id=hashlib.sha256(("\0".join(key)).encode()).hexdigest()
        dates=metadata.get("published_at")
        if not isinstance(dates,str) or not dates:
            raise ValueError("RSS_RESEARCH_VERIFIED_PUBLICATION_MISSING")
        records.append({
            "id":record_id,
            "source_document_id":document_id[:100],
            "industry":sector,
            "title":str(doc.get("title") or "")[:180],
            "url":canonical,
            "origin_publisher":str(metadata["origin_publisher"])[:180],
            "published_at":dates,
            "collected_at":str(doc.get("collected_at") or "")[:40],
            "body_sha256":body_hash,
            "roles":sorted({f["role"] for f in literal}),
            "claim_offsets":[f["locator"] for f in literal[:6]],
            "category":"rss_source_observation",
            "verification":"ORIGINAL_PUBLISHER_AND_BODY_VERIFIED_UNPAIRED",
            "confirmed_future_shortage":False,
        })
        groups[sector]["source_verified_research_records"]+=1
        counts["new_source_verified_sector_records"]+=1
    records.sort(key=lambda r:(r["industry"],r["url"],r["id"]))
    # The source and primary lexicon only provide conservative triage;
    # independent opposite-side supply is still a different Q3 gate.
    return {"format":FORMAT,"status":"SOURCE_BOUND_RESEARCH_BRIDGE",
        "sidecar_commit":sidecar_sha,
        "screened_articles":counts["screened_articles"],
        "counts":dict(counts),
        "groups":{k:dict(v) for k,v in sorted(groups.items())},
        "preview":dict(preview),
        "source_records":records,
        "source_verified_sector_count":len(records),
        "classification":"VERIFIED_ORIGINAL_RESEARCH_OBSERVATIONS_NOT_PROVEN_SHORTAGES"}


def from_remote(repo):
    repo=Path(repo).resolve()
    side_sha=_cmd(repo,"git","ls-remote","origin","refs/heads/future-bottleneck-data").decode().split()[0]
    if not re.fullmatch("[0-9a-f]{40}",side_sha):
        raise ValueError("RSS_RESEARCH_SIDECAR_REF_INVALID")
    _cmd(repo,"git","fetch","--no-tags","--depth=1","origin",side_sha)
    raw=_cmd(repo,"git","show",side_sha+":future-candidates.json")
    if len(raw)>256_000:
        raise ValueError("RSS_RESEARCH_MANIFEST_EXCESSIVE")
    manifest=json.loads(raw)
    if (manifest.get("format")!="bct-sharded-sidecar-v1"
            or not re.fullmatch("[0-9a-f]{64}",str(manifest.get("document_sha256","")))
            or len(manifest.get("shards",[]))>120):
        raise ValueError("RSS_RESEARCH_SIDECAR_FORMAT")
    stem="future-candidates"
    def source(part):
        i=source.count+1
        expected=f"{stem}.shards/{manifest['document_sha256']}/{stem}.part-{i:03d}.json"
        if part.get("path")!=expected:
            raise ValueError("RSS_RESEARCH_UNEXPECTED_SHARD")
        source.count=i
        return _cmd(repo,"git","show",side_sha+":"+part["path"])
    source.count=0
    document=assemble(manifest,source)  # Per-shard + complete document SHA256.
    if len(document.get("results",{}))!=manifest["item_counts"]["results"]:
        raise ValueError("RSS_RESEARCH_COUNT_MISMATCH")
    record=register(document,sidecar_sha=side_sha,
                    feed_domains=feed_group_hints(repo/"rss_feeds.yaml"))
    record["shards_hash_verified"]=source.count
    record["document_sha256"]=manifest["document_sha256"]
    return record
