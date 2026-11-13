"""Read-only archived verified new RSS originals and scope events.

Uses exact completed acquisition run and new-only RSS manifest. Does not
publish raw bodies, fabricated products or final shortage predictions.
"""
from collections import Counter
import hashlib, json, os, re
from pathlib import Path
from bct.precursor_collection import stored_documents

ROOT=Path(os.environ["RUNNER_TEMP"])/"bct-precursor-audit"
cache=ROOT/"private"
rss=ROOT/"rss"
manifest=json.loads((rss/"new-document-manifest.json").read_bytes())
assert manifest["run_id"]==43472909460 and manifest["run_attempt"]==1
ids={str(row["document_id"]) for row in manifest["documents"]}
assert len(ids)==len(manifest["documents"])==80
holds=[]
docs=stored_documents(cache,quarantine_invalid=True,holds=holds)
selected=[d for d in docs if str(d.get("document_id")) in ids]
products=Counter();event_types=Counter();status=Counter()
named_docs=[];examples=[]
def name_from_scope(value):
    if isinstance(value,dict):
        for key in ("value","surface","text","name"):
            if isinstance(value.get(key),str):return value[key]
    return value if isinstance(value,str) else None
for d in selected:
    if d.get("provenance")!="PASS" or hashlib.sha256(d["body"].encode()).hexdigest()!=d["body_sha256"]:
        raise ValueError("BCT_ORIGINAL_STORED_BODY_INVALID")
    status["source_body_valid"]+=1
    events=d.get("precursor_events",[])
    status["source_events"]+=len(events)
    unique=set()
    for e in events:
        if not isinstance(e,dict):continue
        for typ in e.get("event_types",[]):event_types[str(typ)]+=1
        s=e.get("scope") or {}
        p=name_from_scope(s.get("product"))
        if isinstance(p,str) and p and p!="UNKNOWN":
            unique.add(p)
            products[p[:80]]+=1
            status["events_with_explicit_product"]+=1
    if unique:
        named_docs.append(d["document_id"])
        if len(examples)<20:
            examples.append({"doc_hash":d["body_sha256"][:12],
                "publisher":str(d.get("origin_publisher") or "?")[:90],
                "product_names":sorted(unique)[:4],
                "event_count":len(events),
                "published_at":d.get("published_at"),
                "url_host":__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(d["origin_url"]).hostname})
result={
    "status":"VERIFIED_READONLY_NEW_ORIGINALS_NOT_SHORTAGES",
    "rss_run":43472909460,"acquisition_run":43473259686,
    "manifest_urls":len(ids),
    "stored_total":len(docs),
    "new_stored_sources":len(selected),
    "new_source_holds":len(holds),
    "source_body_valid":status["source_body_valid"],
    "with_explicit_products":len(named_docs),
    "events":dict(event_types),
    "event_product_count":status["events_with_explicit_product"],
    "products_distinct":len(products),
    "top_products":products.most_common(20),
    "samples":examples,
    "current_new_original_sha256":hashlib.sha256("|".join(sorted(named_docs)).encode()).hexdigest(),
    "raw_bodies_exported":False,
    "production_db_modified":False,
    "claims_source_bound_but_not_bottleneck_proven":True
}
(ROOT/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
print("BCT_NEW_VERIFIED_PRECURSOR_SOURCE_FACTS="+json.dumps(result,ensure_ascii=False),flush=True)
