"""Synthetic adversarial integrity tests for real S6 durable source-free research DB."""
from collections import Counter
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
from unittest import TestCase,main

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import bct_s6_durable_sourcefree_research as r
from bct.objective_lock import stamp_export

def synth(parent,temp):
    """Generate only source-free synthetic records, not scraped article text."""
    p=Path(temp)/parent
    p.mkdir()
    if parent=="s6_316":
        db=p/"s6-research-sourcefree.sqlite3"
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE article_intake(id_sha TEXT PRIMARY KEY,sha TEXT,payload TEXT)")
            c.execute("CREATE TABLE source_reentry_plan(id_sha TEXT PRIMARY KEY,ordinal INTEGER)")
            c.execute("CREATE TABLE target_holds(target_id TEXT PRIMARY KEY,sha TEXT,payload TEXT)")
            c.execute("CREATE TABLE research_facts(fact_sha TEXT PRIMARY KEY,target_id TEXT,sha TEXT,payload TEXT)")
            for i in range(316):
                hid=r.sha(f"i{i:04}")
                value={"id_sha256":hid,"qualifying_source_evidence_count":0,
                       "original_source_url_or_title_exported":False}
                payload=r.canonical(value)
                c.execute("INSERT INTO article_intake VALUES(?,?,?)",(hid,r.sha(payload),payload))
                if i<60:
                    c.execute("INSERT INTO source_reentry_plan VALUES(?,?)",(hid,i+1))
            for i in range(22):
                target="unobligated-haleu-us-qualified-supply" if i==0 else f"target-{i}"
                value={"target_id":target,"disposition":"HOLD","candidate_promotion":False}
                payload=r.canonical(value)
                c.execute("INSERT INTO target_holds VALUES(?,?,?)",(target,r.sha(payload),payload))
            for i in range(20):
                causal=("ANTARES_BWXT_FUEL_FRAMEWORK" if i<3 else
                        "CENTRUS_2026Q3_SINGLE_DISCLOSURE" if i<8 else
                        "ANTARES_STANDARD_FABRICATION_AND_CAPACITY_2026Q3")
                key=r.sha(f"f{i}")
                value={"fact_key_sha256":key,"causal_event":causal,
                       "strict_original_pair_eligible":False,
                       "annual_same_scope_unreserved_supply":"UNKNOWN"}
                payload=r.canonical(value)
                c.execute("INSERT INTO research_facts VALUES(?,?,?,?)",
                          (key,target,r.sha(payload),payload))
        summary=stamp_export({
            "format":r.PREPARED_316,
            "articles_without_prior_sidecar":316,
            "research_hold_registered_target_records":22,
            "research_source_bound_original_fact_records":20,
            "source_reentry_plan_max_120":60,
            "research_fact_promotable_strict_pairs":0,
            "operating_research_DB_merge":"NOT_RUN_RESEARCH_ISOLATED_SQLITE_ONLY",
            "LIVE_writes":0,
            "source_article_body_or_url_exported":False,
            "canonical_sqlite_sha256":"c"*64,
            "research_fact_event_groups":{
             "ANTARES_BWXT_FUEL_FRAMEWORK":3,
             "CENTRUS_2026Q3_SINGLE_DISCLOSURE":5,
             "ANTARES_STANDARD_FABRICATION_AND_CAPACITY_2026Q3":12}
        })
        summary["sqlite_sha256"]=r.sha(db.read_bytes())
        (p/"s6-research-summary.json").write_text(r.canonical(summary))
    else:
        db=p/"s6-60-sourcefree.sqlite3"
        with sqlite3.connect(db) as c:
            c.execute("CREATE TABLE source_attempts(id_sha TEXT PRIMARY KEY,sha TEXT,payload TEXT)")
            c.execute("CREATE TABLE source_bound_hints(fact_sha TEXT PRIMARY KEY,id_sha TEXT,payload_sha TEXT,payload TEXT)")
            frequencies=Counter()
            for i in range(147):
                frequencies[i%18]+=1
            for i in range(60):
                hid=r.sha(f"i{i:04}")
                status=("FULL" if i<24 else "PARTIAL" if i<46 else "UNAVAILABLE")
                value={"id_sha256":hid,"source_body_status":status,
                       "verified_public_original":i<18,"hash_version":"b"*64,
                       "new_source_bound_research_fact_hints":frequencies[i],
                       "auto_promotions":0,
                       "auto_retries_added_to_operating_DB":0,
                       "source_date_or_original_text_exported":False}
                payload=r.canonical(value)
                c.execute("INSERT INTO source_attempts VALUES(?,?,?)",(hid,r.sha(payload),payload))
            for i in range(147):
                hid=r.sha(f"i{i%18:04}")
                fact=r.sha(f"hint{i}")
                val={"fact_sha256":fact,"id_sha256":hid,"body_sha256":"b"*64,
                     "span_sha256":"a"*64,
                     "strict_economic_pair_admitted":False,
                     "classification":"SOURCE_BOUND_RESEARCH_HINT_NOT_INDEPENDENT_ELIGIBLE_PAIR"}
                payload=r.canonical(val)
                c.execute("INSERT INTO source_bound_hints VALUES(?,?,?,?)",
                          (fact,hid,r.sha(payload),payload))
        summary=stamp_export({
           "format":r.ACTUAL_60,"planned_selected":60,
           "actual_eligible_source_attempts":60,
           "skipped_existing_current_sidecar_record":0,
           "actual_acquired_body_states":{"FULL":24,"PARTIAL":22,"UNAVAILABLE":14},
           "new_strict_original_verified":18,
           "new_source_bound_research_fact_hints":147,
           "input_S6_research_sqlite_sha256":"TO_FILL",
           "existing_operating_CAS_mutations":0,"research_pair_admitted":0,
           "forecast_candidate_or_LIVE_promotions":0,
           "original_source_bodies_or_urls_persisted":False,
           "sample_historical_RSS_snapshot_sha256":"c"*64
        })
        summary["research_sqlite_sha256"]=r.sha(db.read_bytes())
        (p/"s6-60-execution.json").write_text(r.canonical(summary))
    return p

def pair(path):
    a=synth("s6_316",path);b=synth("s6_60",path)
    x=json.loads((b/"s6-60-execution.json").read_text())
    y=json.loads((a/"s6-research-summary.json").read_text())
    x["input_S6_research_sqlite_sha256"]=y["sqlite_sha256"]
    (b/"s6-60-execution.json").write_text(r.canonical(x))
    return a,b

class DurableResearchLedgerTest(TestCase):
    def test_actual_316_plus_60_plus_22_plus_20_plus_147_consolidation(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=pair(temp)
            out=Path(temp)/"output"
            saved=r.materialize(a,b,out)
            self.assertEqual(r.readback(out)["source_bound_hints"],147)
            self.assertEqual(r.readback(out)["verified_public_originals"],18)
            self.assertEqual(r.readback(out)["research_fact_codes"],20)
            self.assertEqual(r.readback(out)["qualified_pairs"],0)
            self.assertEqual(saved["article_s6_still_unattempted_in_this_snapshot"],256)
            with self.assertRaisesRegex(ValueError,"OUTPUT_OVERWRITE"):
                r.materialize(a,b,out)

    def test_bad_parent_lineage_never_published(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=pair(temp)
            s=json.loads((b/"s6-60-execution.json").read_text())
            s["input_S6_research_sqlite_sha256"]="1"*64
            (b/"s6-60-execution.json").write_text(r.canonical(s))
            with self.assertRaisesRegex(ValueError,"S6_60_ACTUAL"):
                r.materialize(a,b,Path(temp)/"invalid")

    def test_changed_original_source_payload_hash_cannot_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=pair(temp)
            with sqlite3.connect(a/"s6-research-sourcefree.sqlite3") as db:
                db.execute("UPDATE research_facts SET payload='{}' LIMIT 1")
            s=json.loads((a/"s6-research-summary.json").read_text())
            s["sqlite_sha256"]=r.sha((a/"s6-research-sourcefree.sqlite3").read_bytes())
            (a/"s6-research-summary.json").write_text(r.canonical(s))
            x=json.loads((b/"s6-60-execution.json").read_text())
            x["input_S6_research_sqlite_sha256"]=s["sqlite_sha256"]
            (b/"s6-60-execution.json").write_text(r.canonical(x))
            with self.assertRaisesRegex(ValueError,"PARENT_RECORD_SHA"):
                r.materialize(a,b,Path(temp)/"invalid")

    def test_tampered_durable_database_rejected_on_requery(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=pair(temp);out=Path(temp)/"output"
            r.materialize(a,b,out)
            (out/"research-sourcefree.sqlite3").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"DB_BYTES_CHANGED"):
                r.readback(out)

    def test_false_verified_pair_or_live_write_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=pair(temp);out=Path(temp)/"output"
            report=r.materialize(a,b,out)
            p=out/"research-summary.json"
            report["strict_eligible_independent_pairs_admitted"]=1
            p.write_text(r.canonical(report))
            with self.assertRaisesRegex(ValueError,"STORED_FALSE_ELIGIBLE_PAIR"):
                r.readback(out)

if __name__=="__main__":main()
