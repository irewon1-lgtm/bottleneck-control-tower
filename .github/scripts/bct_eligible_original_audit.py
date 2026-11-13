"""Inspect exact Source index, no mutations and no original text publication."""
import json,hashlib,subprocess,collections,os
from urllib.parse import urlsplit
from bct.future_github import assemble
from bct.future_body import verified_source_metadata
from bct.future_review import event_groups
from pathlib import Path

def cmd(*args):
    return subprocess.check_output(args)
data_ref=cmd("git","ls-remote","origin","refs/heads/future-bottleneck-data").decode().split()[0]
assert len(data_ref)==40
cmd("git","fetch","--no-tags","--depth=1","origin",data_ref)
manifest=json.loads(cmd("git","show",data_ref+":future-candidates.json"))
assert manifest["format"]=="bct-sharded-sidecar-v1"
verified=[0]
def shard(part):
    raw=cmd("git","show",data_ref+":"+part["path"])
    assert hashlib.sha256(raw).hexdigest()==part["sha256"]
    verified[0]+=1
    return raw
doc=assemble(manifest,shard)
data=doc["results"]
counts=collections.Counter()
samples=[]
publishers=collections.Counter()
fact_types=collections.Counter()
roles=collections.Counter()
sectors=collections.Counter()
target_values=collections.Counter()
for id,r in data.items():
    counts["total"]+=1
    digest=r.get("current_body_sha256") or r.get("body_sha256")
    version=r.get("versions",{}).get(digest,{}) if digest else {}
    status=version.get("body_status") or r.get("body_status") or "UNAVAILABLE"
    s={**r,**version}
    meta=verified_source_metadata(s,digest)
    if status=="FULL":counts["full"]+=1
    if r.get("candidate") is True:counts["screen_candidate"]+=1
    if r.get("discovery_paths"):counts["has_paths"]+=1
    if r.get("scope_facts"):counts["has_scope_facts"]+=1
    if r.get("targets"):counts["has_targets"]+=1
    if meta.get("provenance_verified"):counts["source_provenance_verified"]+=1
    if meta.get("publication_verified"):counts["original_publication_verified"]+=1
    if r.get("provenance_verified") is True:counts["top_level_provenance_flag"]+=1
    if r.get("publication_verified") is True:counts["top_level_publication_flag"]+=1
    if status=="FULL" and meta.get("provenance_verified"):counts["full_source_verified"]+=1
    if status=="FULL" and meta.get("publication_verified"):counts["full_publication_verified"]+=1
    if status=="FULL" and meta.get("provenance_verified") and meta.get("publication_verified"):counts["full_both_verified"]+=1
    facts=r.get("scope_facts") or []
    strong=[f for f in facts if isinstance(f,dict) and f.get("actual_statement") is True and f.get("target") not in (None,"UNKNOWN","")]
    if status=="FULL" and meta.get("provenance_verified") and strong:
        counts["full_source_verified_with_claim"]+=1
        publishers[urlsplit(r.get("url") or "").hostname]+=1
        if len(samples)<14:
            samples.append({"id":id[:16],"hostname":urlsplit(r.get("url") or "").hostname,
                "title":str(r.get("title"))[:110],"body_chars":r.get("body_chars"),
                "published":meta.get("publication_verified") is True,
                "roles":list(sorted({f.get("role","") for f in strong})),
                "targets":list(sorted({str(f.get("target"))[:64] for f in strong}))[:5],
                "original_verified":bool(meta.get("provenance_verified"))})
    if status=="FULL" and meta.get("provenance_verified") and meta.get("publication_verified") and strong:
        counts["full_both_verified_with_claim"]+=1
    if status=="FULL" and facts:counts["full_has_any_fact"]+=1
    if status=="FULL" and strong:counts["full_has_literal_claim"]+=1
    for f in facts:
        if not isinstance(f,dict):continue
        fact_types[f.get("extraction_status","not_set")]+=1
        if f.get("role"):roles[f["role"]]+=1
        if status=="FULL" and meta.get("provenance_verified") and f.get("target") not in (None,"UNKNOWN",""):
            target_values[str(f["target"])[:70]]+=1
    if r.get("industry_hint"):sectors[r["industry_hint"]]+=1
events=event_groups(doc)
output={"schema":"bct-source-eligibility-audit-20261114-v1","sidecar_sha":data_ref,
    "source_manifest_sha256":manifest["document_sha256"],"shards_checksum_verified":verified[0],
    "records":len(data),"counts":dict(counts),"first_source_verified_examples":samples,
    "facts":dict(fact_types),"roles":dict(roles),"industry_hint":dict(sectors),
    "most_common_claim_targets":target_values.most_common(32),
    "verified_publishers":publishers.most_common(20),"grouped_events":len(events),
    "note":"Aggregate only. No original bodies downloaded, cached or displayed. No evidence promoted."}
out=Path(os.environ["RUNNER_TEMP"])/"bct-eligibility.json"
out.write_text(json.dumps(output,ensure_ascii=False,indent=2))
print("BCT_SOURCE_ELIGIBILITY_AUDIT="+json.dumps(output,ensure_ascii=False)[:35000],flush=True)
