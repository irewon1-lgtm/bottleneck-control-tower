"""Adversarial S6 316 RSS-only intake and source-bound 20-fact research ledger tests."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase,main,mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import bct_s6_316_sourcefree_intake as s6
import bct_s5_quantitative_capacity_audit as q
import bct_s5_supplier_fact_followon as u

def sample_rows():
    rows=[]
    for i in range(10992):
        rows.append({
            "id":f"item-{i:05}","url":f"https://feed{i%31}.example.com/post/{i}",
            "source":f"feed-{i%31}","title":"New manufacturing capacity report",
            "snippet":"Company production plan",
            "published_at":"2026-11-15T07:00:00+00:00",
            "collected_at":"2026-11-15T08:00:00+00:00",
            "updated_at":"2026-11-15T08:00:00+00:00",
            "status":"active"})
    return rows

def prior_map(rows):
    return {s6.sha(r["id"]):
          (("CANONICAL_ONLY",None,"active") if i>=10676
           else ("BOTH","FULL","active"))
          for i,r in enumerate(rows)}

def fake_fact_data():
    h="a"*64;v="b"*64;sp="c"*64
    def source(id,stat):
        return {"source_id":id,"raw_sha256":h,"visible_sha256":v,"status":stat,
                "qualified_customer_unreserved_supply_MTU":"UNKNOWN","LIVE_writes":0}
    std=source("standard_2026q3_sec_10q","FETCHED_PUBLIC_ORIGINAL_RESEARCH_ONLY")
    std["fact_receipts"]=[{"fact_id":f[0],"state":"SOURCE_LOCATOR_HASH_VERIFIED",
                          "meaning":f[3],"value":f[1],"unit":f[2],
                          "locator":{"start":10*i,"end":10*i+2,
                                     "source_span_sha256":sp}}
                          for i,f in enumerate(q.FACTS["standard_2026q3_sec_10q"])]
    cen=source("centrus_2026q3_issuer","ACCESS_HOLD")
    cen["fact_receipts"]=[]
    raw=[("standard_2026q3_sec_10q",std),("centrus_2026q3_issuer",cen)]
    def su_case(id,status,issuer,causal):
        p=source(id,status);p["issuer"]=issuer;p["causal_event"]=causal
        p["facts"]=[{"fact_id":f[0],
                    "state":"VISIBLE_SOURCE_SPAN_HASH_VERIFIED",
                    "value":f[2],"interpretation":f[3],
                    "location":{"start":8*i,"end":8*i+3,"span_sha256":sp}}
                   for i,f in enumerate(u.FACTS[causal])] if status.startswith("ORIGINAL") else []
        return (id,p)
    supp=[
      su_case("bwxt_antares_issuer","ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY",
              "BWX Technologies, Inc.","ANTARES_BWXT_FUEL_FRAMEWORK"),
      su_case("centrus_issuer_q3","ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY",
              "Centrus Energy Corp.","CENTRUS_2026Q3_SINGLE_DISCLOSURE"),
      su_case("centrus_official_8k_pdf","ORIGINAL_VISIBLE_SOURCE_ATTESTED_RESEARCH_ONLY",
              "Centrus Energy Corp.","CENTRUS_2026Q3_SINGLE_DISCLOSURE"),
      su_case("centrus_sec_q3_ex99","ACCESS_HOLD",
              "Centrus Energy Corp.","CENTRUS_2026Q3_SINGLE_DISCLOSURE")
    ]
    return raw,supp

def targets():
    return [{"target_id":f"T{i:02}","source_case_sha256":s6.sha(str(i)),
             "disposition":"HOLD","historical_review_count":0,
             "previous_display_stage":"NONE",
             "qualifying_independent_pairs":"NOT_EVALUATED_UNDER_S5_PROVENANCE",
             "candidate_promotion":False} for i in range(22)]

def parents():
    return {x:{"sqlite_sha256":"d"*64,"sql_sha256":"d"*64}
            for x in ("join","target","standard","supplier")}

class TestS6ResearchIntake(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=sample_rows()
        cls.map=prior_map(cls.rows)

    def test_316_are_rss_only_not_cpu_errors_or_failed_source_proof(self):
        x,work,ai=s6.classify_316(self.rows,{},self.map,s6.PINNED_CANONICAL_SHA)
        self.assertEqual(len(x),316)
        self.assertEqual(len({r["id_sha256"] for r in x}),316)
        self.assertTrue(all(r["work_state"]=="SOURCE_RECHECK_ELIGIBLE_UNKNOWN_PRIOR_BODY" for r in x))
        self.assertTrue(all(r["source_access_failure_verified"] is False
                            and r["independent_CPU_read_status"]=="NOT_EVALUATED_FROM_RSS_METADATA"
                            and r["source_retry_and_attempts"]=="NOT_RECORDED_IN_OPERATING_SIDECAR"
                            and r["qualifying_source_evidence_count"]==0 for r in x))
        self.assertLessEqual(len(work),120)

    def test_missing_result_can_have_separate_rss_title_ai_but_not_cpu(self):
        reviews={self.rows[10991]["id"]:Counter({"OK":2,"ERROR":1})}
        x,work,counts=s6.classify_316(self.rows,reviews,self.map,s6.PINNED_CANONICAL_SHA)
        p=next(a for a in x if a["id_sha256"]==s6.sha(self.rows[10991]["id"]))
        self.assertEqual(p["separate_rss_title_ai"],"RSS_TITLE_AI_OK_SEPARATE_NOT_CPU")
        self.assertEqual(p["separate_rss_ai_ok_count"],2)
        self.assertEqual(p["independent_CPU_read_status"],"NOT_EVALUATED_FROM_RSS_METADATA")
        self.assertEqual(counts,{"OK":2,"ERROR":1})

    def test_changed_canonical_id_or_previous_sidecar_mapping_fails(self):
        p=deepcopy(self.map)
        p.pop(next(iter(p)))
        with self.assertRaisesRegex(ValueError,"CANONICAL_AND_PREVIOUS_HASHED_IDS_MISMATCH"):
            s6.classify_316(self.rows,{},p,s6.PINNED_CANONICAL_SHA)
        p=dict(self.map)
        key=s6.sha(self.rows[-1]["id"])
        p[key]=("BOTH","FULL","active")
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_316_INTAKE_OR_FALSE_PAIR"):
            s6.classify_316(self.rows,{},p,s6.PINNED_CANONICAL_SHA)
        with self.assertRaisesRegex(ValueError,"CANONICAL_INPUT_NOT_PINNED"):
            s6.classify_316(self.rows,{},self.map,"0"*64)

    def test_invalid_urls_hold_without_inventing_source_http_status(self):
        rows=deepcopy(self.rows)
        rows[-1]["url"]="javascript:alert(1)"
        x,_,_=s6.classify_316(rows,{},self.map,s6.PINNED_CANONICAL_SHA)
        last=next(z for z in x if z["id_sha256"]==s6.sha(rows[-1]["id"]))
        self.assertEqual(last["work_state"],"SOURCE_METADATA_INVALID_HOLD")
        self.assertFalse(last["source_access_failure_verified"])

    def test_typed_source_bound_20_facts_and_two_centrus_formats_one_event(self):
        st,su=fake_fact_data()
        with mock.patch.object(s6,"query_cases",side_effect=[st,su]):
            facts=s6.combined_research_facts(Path("/fake/std"),Path("/fake/su"),{s6.SOURCE_TARGET})
        self.assertEqual(len(facts),20)
        self.assertEqual(sum(f["causal_event"]=="CENTRUS_2026Q3_SINGLE_DISCLOSURE" for f in facts),5)
        self.assertEqual(sum(f["causal_event"]=="ANTARES_STANDARD_FABRICATION_AND_CAPACITY_2026Q3" for f in facts),12)
        self.assertTrue(all(not f["strict_original_pair_eligible"] for f in facts))
        self.assertEqual({len(f["public_original_receipts"]) for f in facts
                          if f["causal_event"]=="CENTRUS_2026Q3_SINGLE_DISCLOSURE"},{2})
        firm=next(f for f in facts if f["fact_id"]=="STDN_FIRM_FABRICATION_TOTAL_MTU")
        optional=next(f for f in facts if f["fact_id"]=="STDN_OPTION_NOT_COMMITTED_MTU")
        self.assertEqual((firm["value"],optional["value"]),(1,7))

    def test_one_changed_source_fact_or_hold_does_not_become_verified(self):
        st,su=fake_fact_data()
        su[1][1]["facts"][0]["location"]["span_sha256"]="notasha"
        with mock.patch.object(s6,"query_cases",side_effect=[st,su]):
            with self.assertRaisesRegex(ValueError,"FACT_SPAN_NOT_SOURCE_HASH_BOUND"):
                s6.combined_research_facts(Path("/fake/a"),Path("/fake/b"),{s6.SOURCE_TARGET})
        st,su=fake_fact_data()
        with mock.patch.object(s6,"query_cases",side_effect=[st,su]):
            with self.assertRaisesRegex(ValueError,"TARGET_REFERENCE_NOT_REGISTERED"):
                s6.combined_research_facts(Path("/fake/a"),Path("/fake/b"),{"other"})

    def test_research_sqlite_fresh_roundtrip_and_changed_count_fails(self):
        x,queue,review=s6.classify_316(self.rows,{},self.map,s6.PINNED_CANONICAL_SHA)
        st,su=fake_fact_data()
        with mock.patch.object(s6,"query_cases",side_effect=[st,su]):
            facts=s6.combined_research_facts(Path("/fake/a"),Path("/fake/b"),{s6.SOURCE_TARGET})
        t=targets()
        summary=s6.build_summary(x,queue,review,t,facts,parents(),
                                 {"rss_ai_separate_table_present":False,
                                  "rss_ai_review_rows_full_corpus":0})
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"intake"
            res=s6.write_db(out,summary,x,queue,t,facts)
            self.assertEqual(s6.fresh_readback(out)["articles"],316)
            self.assertEqual(s6.fresh_readback(out)["source_bound_facts"],20)
            self.assertEqual(res["research_fact_promotable_strict_pairs"],0)
            with self.assertRaisesRegex(ValueError,"OUTPUT_EXISTS"):
                s6.write_db(out,summary,x,queue,t,facts)
            p=out/"s6-research-summary.json"
            altered=json.loads(p.read_text())
            altered["research_fact_promotable_strict_pairs"]=3
            p.write_text(s6.canon(altered))
            with self.assertRaisesRegex(ValueError,"SOURCE_FREE_AGGREGATE_REQUERY_MISMATCH"):
                s6.fresh_readback(out)

if __name__=="__main__":
    main()
