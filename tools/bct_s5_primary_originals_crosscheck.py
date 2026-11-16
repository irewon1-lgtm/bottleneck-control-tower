"""Read-only BCT S5 pilot: fetch *public, prelisted primary URLs*, never private-cache queries.

No model inference, no secrets, no source text in GitHub artifacts, no LIVE writes.
Distinct official issuer confirmations are NOT independent economic demand/supply events.
"""
import argparse
from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from html import unescape
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

FORMAT="bct-s5-public-primary-original-crosscheck-v1"
MANIFEST_FORMAT="bct-s5-primary-public-url-pilot-v1"
ALLOWED_ASOF="2026-11-16"
EXPECTED_URLS=8
BANNED_FIELDS=frozenset(("body","text","html","raw","quote","source_quote","original_bytes","model_output"))
CERTIFICATE="NO_LIVE_NO_EARLY_NO_STRICT_SUPPLY_DEMAND_PROMOTION"

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def sha(data):
    return hashlib.sha256(data if isinstance(data,bytes) else data.encode("utf-8")).hexdigest()

def guard(condition,code):
    if not condition: raise ValueError("S5_PRIMARY_"+code)

def public_url(value,host):
    p=urlsplit(value)
    guard(p.scheme=="https" and p.hostname==host and p.username is None
          and p.password is None and not p.query and not p.fragment
          and p.port is None and p.path.startswith("/"),"UNSAFE_OR_CHANGED_URL")
    guard(not host.endswith(".local") and not host.startswith("localhost"),"PRIVATE_HOST")
    try:
        addr=ipaddress.ip_address(host)
    except ValueError:
        addr=None
    guard(addr is None or addr.is_global,"NON_PUBLIC_IP")
    return value

def validate_manifest(manifest):
    guard(manifest.get("format")==MANIFEST_FORMAT
          and manifest.get("mode")=="READ_ONLY_BACKFILL_NO_LIVE"
          and manifest.get("as_of")==ALLOWED_ASOF
          and manifest.get("scope")=="PUBLIC_ORIGINALS_ONLY_NOT_S4_CONSUMER_ARTICLE_COHORT"
          and manifest.get("source_policy")=="MANUALLY_VERIFIED_PUBLIC_ORIGINAL_URLS_NO_PRIVATE_DERIVED_QUERY"
          and manifest.get("target")=="unobligated-haleu-us-qualified-supply",
          "MANIFEST_NOT_FIXED_PUBLIC_RESEARCH")
    entries=manifest.get("sources")
    guard(isinstance(entries,list) and len(entries)==EXPECTED_URLS,"EXACT_PILOT_SOURCE_COUNT")
    ids=set();urls=set()
    for s in entries:
        guard(type(s)==dict and all(isinstance(s.get(k),str) and s[k] for k in
              ("id","issuer","host","published_date","url","causal_event","role",
               "visible_title","visible_date","visible_issuer_marker")),
              "SOURCE_DECLARATION_INVALID")
        guard(s["id"] not in ids and s["url"] not in urls,"DUPLICATE_SOURCE")
        ids.add(s["id"]);urls.add(s["url"])
        public_url(s["url"],s["host"])
        day=date.fromisoformat(s["published_date"])
        guard(day<=date.fromisoformat(ALLOWED_ASOF),"FUTURE_PRIMARY_EVIDENCE")
        facts=s.get("fact_patterns")
        guard(isinstance(facts,dict) and facts and len(facts)<=6
              and all(re.fullmatch("[A-Z][A-Z0-9_]{4,80}",k)
                      and type(v)==str and 12<=len(v)<=160 and "\n" not in v
                      for k,v in facts.items()),"FACT_PATTERNS_INVALID")
        guard(not any(q in canonical(s).lower() for q in ("ghp_","github_pat_","authorization: bearer")),
              "PRIVATE_CREDENTIAL_LIKE_SOURCE")
        guard(20<=len(s["visible_title"])<=150
              and 8<=len(s["visible_date"])<=30
              and 8<=len(s["visible_issuer_marker"])<=100,
              "PUBLIC_SOURCE_VISIBLE_ATTESTATION_CONTRACT")
    return entries

def flattened(s):
    return re.sub(r"\s+"," ",s.replace("\u00a0"," ").casefold()).strip()

def attested_visible_primary(source,raw,final,proof):
    """Separate, narrower visible-public attestation, NOT global strict provenance.

    It establishes that THIS already-public listed issuer URL displays the
    exact expected headline, adjacent original date, issuer identification,
    and at least one actual source-bound observable. It does not establish
    eligible unreserved supply, whole-article completeness, or a forecast pair.
    """
    if not isinstance(raw,bytes) or len(raw)<600:
        return False
    if public_url(final,source["host"])!=source["url"]:
        return False
    if sha(raw)!=proof.get("raw_sha256"):
        return False
    if (not isinstance(proof.get("body"),str)
        or len(proof["body"])<600
        or sha(proof["body"])!=proof.get("body_sha256")):
        return False
    if not any(flattened(pat) in flattened(proof["body"])
               for pat in source["fact_patterns"].values()):
        return False
    html=raw.decode("utf-8",errors="replace")
    html=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>",
                " ",html,flags=re.I|re.S)
    text=flattened(unescape(re.sub(r"<[^>]+>"," ",html)))
    title=flattened(source["visible_title"])
    date_mark=flattened(source["visible_date"])
    issuer=flattened(source["visible_issuer_marker"])
    if issuer not in text:
        return False
    locations=[m.start() for m in re.finditer(re.escape(title),text)]
    if not locations:
        return False
    # Accept exact issuer's date bound near the named article heading, not
    # an unrelated navigation/news item elsewhere on a long issuer page.
    if not any(date_mark in text[max(0,i-220):i+len(title)+500]
               for i in locations):
        return False
    # An accessible original article cannot be a challenge or paywall page.
    if any(x in text[:1000] for x in
            ("enable javascript to continue","verify you are human",
             "access denied","captcha challenge")):
        return False
    return True

def classify_source(source,observed,*,acquired_at,visible_attested=False):
    """observed=None on retrieval failure, else a real exact downloaded verifier result."""
    base={k:source[k] for k in ("id","issuer","url","published_date","role","causal_event")}
    base.update(source_kind="PUBLIC_PRELISTED_PRIMARY_URL",retrieved=False,
                verified_original=False,visible_primary_attested=False,
                fact_codes=[],held_fact_codes=[],attested_fact_codes=[],
                live_changes=0,strict_independent_sourcing_gap_proven=False)
    if observed is None:
        return {**base,"status":"ACCESS_HOLD","blockers":["REMOTE_NOT_AVAILABLE_OR_DENIED"]}
    # Never claim independent original provenance on URL/host alone.
    p=observed
    guard(type(p.get("body"))==str and isinstance(p.get("body_sha256"),str)
          and sha(p["body"])==p["body_sha256"] and isinstance(p.get("raw_sha256"),str),
          "FETCHED_BODY_DIGEST_MISMATCH")
    proof_date=p.get("published_at")
    actual_date=proof_date[:10] if isinstance(proof_date,str) and len(proof_date)>=10 else None
    valid_date=actual_date==source["published_date"]
    checks=p.get("checks") or {}
    legitimate=(p.get("provenance")=="PASS" and p.get("provenance_verified") is True
                and bool(checks) and all(v is True for v in checks.values())
                and valid_date)
    body=flattened(p["body"])
    codes=sorted(k for k,phrase in source["fact_patterns"].items()
                 if flattened(phrase) in body)
    # A matching substring in an unverified page is only a lead.
    evidence=codes if legitimate else []
    attested=bool(visible_attested and codes)
    blockers=([] if legitimate else
              sorted(set([*p.get("provenance_blockers",[])]
                         +([] if valid_date else ["ORIGINAL_PUBLICATION_DATE_NOT_MATCHED"]))))
    record={**base,"retrieved":True,
            "verified_original":legitimate,
            "visible_primary_attested":attested,
            "status":"ORIGINAL_SOURCE_VERIFIED" if legitimate else
                     "VISIBLE_ORIGINAL_ATTESTED_STRICT_PROVENANCE_HOLD" if attested else
                     "BODY_CAPTURED_PROVENANCE_HOLD",
            "raw_sha256":p["raw_sha256"],"body_sha256":p["body_sha256"],
            "source_published_at":proof_date if legitimate else None,
            "source_length":len(p["body"]),
            "provenance_validation":p.get("provenance","UNKNOWN"),
            "blockers":blockers,
            "fact_codes":evidence,
            "attested_fact_codes":[] if legitimate else codes if attested else [],
            "held_fact_codes":[] if legitimate or attested else codes}
    return record

def summarize(manifest,cases):
    entries=validate_manifest(manifest)
    guard(len(cases)==len(entries),"CASE_COUNT_NOT_COMPLETE")
    expected={r["id"]:r for r in entries}
    issuers=set();attested_issuers=set();contract_groups=defaultdict(list);
    codes=Counter();attested_codes=Counter();held=Counter()
    for case in cases:
        expected_source=expected.get(case.get("id"))
        guard(expected_source is not None and
              all(case.get(k)==expected_source[k] for k in
              ("issuer","url","published_date","role","causal_event")),"CASE_ORIGIN_CHANGED")
        guard(case.get("live_changes")==0
              and case.get("strict_independent_sourcing_gap_proven") is False
              and case["fact_codes"]==sorted(set(case["fact_codes"])),"UNVERIFIED_PROMOTION")
        if case["verified_original"] and case["fact_codes"]:
            issuers.add(case["issuer"])
        if case.get("visible_primary_attested") and case.get("attested_fact_codes"):
            attested_issuers.add(case["issuer"])
        contract_groups[case["causal_event"]].append(case)
        codes.update(case["fact_codes"])
        attested_codes.update(case.get("attested_fact_codes",[]))
        held.update(case["held_fact_codes"])
    # Reports from buyer and seller about the SAME agreement are one causal event.
    contract_groups={k:{
         "original_issuers_with_verified_facts":len({x["issuer"]for x in v
           if x["verified_original"] and x["fact_codes"]}),
         "additional_visible_attested_original_issuers":len({x["issuer"]for x in v
           if x.get("visible_primary_attested") and x.get("attested_fact_codes")}),
         "economic_events_maximum":1,
         "original_urls_checked":len(v)}
         for k,v in sorted(contract_groups.items())}
    return {
       "format":FORMAT,"status":"PASS_READONLY_BOUNDED_PRIMARY_ORIGINAL_CAPTURE_AND_HOLD",
       "target":manifest["target"],
       "as_of":manifest["as_of"],
       "scope":manifest["scope"],
       "attempted_public_primary_urls":len(cases),
       "fetched_bodies":sum(c["retrieved"] for c in cases),
       "provenance_verified_originals":sum(c["verified_original"] for c in cases),
       "provenance_holds":sum(c["retrieved"] and not c["verified_original"] for c in cases),
       "access_holds":sum(not c["retrieved"] for c in cases),
       "independent_original_issuers_with_verified_facts":len(issuers),
       "visible_public_original_attestations":sum(c.get("visible_primary_attested",False) for c in cases),
       "distinct_visible_public_original_issuers":len(attested_issuers|issuers),
       "verified_fact_codes":dict(sorted(codes.items())),
       "attested_research_only_fact_codes":dict(sorted(attested_codes.items())),
       "held_fact_codes":dict(sorted(held.items())),
       "same_contract_deduplicated_event_groups":contract_groups,
       "strict_eligible_supply_demand_pairs":0,
       "forecast_early_candidates":0,
       "candidate_or_LIVE_writes":0,
       "S4_11_originals_or_private_epoch_modified":False,
       "full_RSS_corpus_audited":False,
       "no_source_text_exported":True,
       "case_count":len(cases),
       "next_gate":"SEPARATE_ECONOMIC_CAUSAL_FACTS_QUALIFIED_SUPPLY_AND_CUSTOMER_NEED_PERIOD_PROOF",
       "forecast_accuracy":"UNVERIFIED",
       "certificate":CERTIFICATE
    }

def save_output(path,summary,cases):
    path=Path(path)
    guard(not path.exists(),"OUTPUT_OVERWRITE_FORBIDDEN")
    path.mkdir(parents=True)
    dbfile=path/"cases.sqlite3"
    with sqlite3.connect(dbfile) as db:
        db.execute("CREATE TABLE source_cases(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, payload TEXT NOT NULL)")
        for row in cases:
            serialized=canonical(row)
            db.execute("INSERT INTO source_cases(id,sha256,payload) VALUES(?,?,?)",
                       (row["id"],sha(serialized),serialized))
        db.commit()
    summary=dict(summary)
    summary["sources_sqlite_sha256"]=sha(dbfile.read_bytes())
    summary["result_sha256"]=sha(canonical(cases))
    (path/"summary.json").write_text(canonical(summary)+"\n")
    readback(path)
    return summary

def readback(path):
    path=Path(path)
    summary=json.loads((path/"summary.json").read_text())
    dbfile=path/"cases.sqlite3"
    guard(sha(dbfile.read_bytes())==summary["sources_sqlite_sha256"],"SQLITE_ARCHIVE_HASH_CHANGED")
    with sqlite3.connect(dbfile.resolve().as_uri()+"?mode=ro",uri=True) as db:
        guard(db.execute("PRAGMA integrity_check").fetchone()==("ok",),"SQLITE_INTEGRITY_FAILED")
        data=db.execute("SELECT id,sha256,payload FROM source_cases ORDER BY id").fetchall()
    cases=[]
    for id,check,payload in data:
        guard(sha(payload)==check,"CASE_PAYLOAD_CHANGED")
        item=json.loads(payload)
        guard(item["id"]==id and not any(f in item for f in BANNED_FIELDS),
              "RAW_ORIGINAL_CONTENT_LEAK_OR_SOURCE_ID_CHANGE")
        cases.append(item)
    guard(summary["case_count"]==len(cases)==EXPECTED_URLS
          and summary["result_sha256"]==sha(canonical(sorted(cases,key=lambda x:x["id"])))
          and summary["candidate_or_LIVE_writes"]==0
          and summary["strict_eligible_supply_demand_pairs"]==0
          and summary["certificate"]==CERTIFICATE,"WRITTEN_EVIDENCE_REQUERY_MISMATCH")
    return {"status":"PASS_S5_PUBLIC_ORIGINALS_FRESH_SQLITE_READBACK",
            "sources":len(cases),"verified":summary["provenance_verified_originals"],
            "held":summary["provenance_holds"]+summary["access_holds"]}

def run(manifest_path,output):
    from bct import target_acquisition as capture
    manifest=json.loads(Path(manifest_path).read_text())
    entries=validate_manifest(manifest)
    cases=[]
    for src in entries:
        raw=None
        try:
            raw,final,status,ctype=capture.fetch(src["url"])
            # A public URL pointing to a different host is not a verified original.
            if urlsplit(final).hostname!=src["host"]:
                raise ValueError("UNEXPECTED_CROSS_DOMAIN_REDIRECT")
            verified=capture.verify(raw,src["url"],final,
                                    datetime.now(timezone.utc).isoformat(),status,ctype)
            visible=attested_visible_primary(src,raw,final,verified)
            case=classify_source(src,verified,
                         acquired_at=datetime.now(timezone.utc).isoformat(),
                         visible_attested=visible)
        except Exception as exc:
            case=classify_source(src,None,acquired_at=datetime.now(timezone.utc).isoformat())
            case["blockers"]=[("HTTP_"+str(exc.code)) if hasattr(exc,"code") else type(exc).__name__]
        cases.append(case)
        # No original HTML, text, or private derived query printed to CI logs.
        print("S5_PRIMARY_FETCH="+canonical({
            "source":case["id"],"status":case["status"],
            "fact_codes":case["fact_codes"],"attested_fact_codes":case.get("attested_fact_codes",[]),
            "blockers":case["blockers"]}),flush=True)
    summary=summarize(manifest,cases)
    # Do not accidentally mark source string matches as independent qualified pairs.
    assert summary["candidate_or_LIVE_writes"]==summary["strict_eligible_supply_demand_pairs"]==0
    cases=sorted(cases,key=lambda item:item["id"])
    saved=save_output(output,summary,cases)
    print("S5_PRIMARY_CAPTURE_SUMMARY="+canonical({
          k:saved[k] for k in ("status","attempted_public_primary_urls","fetched_bodies",
             "provenance_verified_originals","provenance_holds","access_holds",
             "independent_original_issuers_with_verified_facts",
             "visible_public_original_attestations","distinct_visible_public_original_issuers",
             "strict_eligible_supply_demand_pairs")}),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.verify_only:
        print("S5_PRIMARY_READBACK="+canonical(readback(args.output)));return
    guard(args.manifest is not None,"PUBLIC_MANIFEST_REQUIRED")
    run(args.manifest,args.output)

if __name__=="__main__":
    main()
