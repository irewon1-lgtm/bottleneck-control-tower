"""Adversarial 60-public-original fetch execution, immutable source, no false pairing."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase,main,mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import bct_s6_60_real_original_reentry as v

SIDE="b"*40
MANIFEST="a"*64

def selection():
    selected=[]
    for i in range(60):
        item={"id":f"article-{i:02}",
              "url":f"https://example.org/p/{i}",
              "updated_at":"2026-11-16T09:00:00+00:00"}
        selected.append({"id_sha256":v.sha(item["id"]),"source":item})
    return selected

def record(src,body_status="UNAVAILABLE",verified=False,scope=None):
    fp=v.sha((src["url"]+src["updated_at"]).encode())
    result={"id":src["id"],"fingerprint":fp,
            "body_status":body_status,
            "acquisition":{"versions":{fp:{"history":[{"trigger":"SCHEDULED"}]}}},
            "scope_facts":scope or [],
            "reasons":["NO_ACCESSIBLE_BODY"] if body_status=="UNAVAILABLE" else []}
    if body_status in ("FULL","PARTIAL"):
        body="Demand for example material has increased. Capacity for example material is limited."
        result["body_sha256"]=v.sha(body)
        result["body_chars"]=len(body)
    else:
        body=""
    if verified:
        result.update(provenance_verified=True,publication_verified=True,
                      current_body_sha256=v.sha(body),
                      origin_id="valid-issuer",origin_publisher="Valid Publisher",
                      provenance_evidence={"body_sha256":v.sha(body),"raw_sha256":"c"*64})
    return result,body

class RealPublicReentry(TestCase):
    def test_60_planned_no_unnecessary_refetch_current_result(self):
        s=selection()
        current={x["source"]["id"]:{"body_status":"PARTIAL"} for x in s[:17]}
        due,skip=v.gate_latest_sidecar({**current,**{
            f"existing-{i}":{} for i in range(10676)}},s)
        self.assertEqual((len(due),len(skip)),(43,17))
        self.assertEqual({x["id_sha256"] for x in skip},
                         {x["id_sha256"] for x in s[:17]})

    def test_full_without_source_proof_is_not_original_verification(self):
        x,body=record(selection()[0]["source"],"FULL")
        self.assertFalse(v.strict_source_receipt(x))
        x["provenance_verified"]=True
        x["publication_verified"]=True
        self.assertFalse(v.strict_source_receipt(x))
        x,body=record(selection()[0]["source"],"FULL",verified=True)
        self.assertTrue(v.strict_source_receipt(x))
        x["provenance_evidence"]["raw_sha256"]="invalid"
        self.assertFalse(v.strict_source_receipt(x))

    def test_status_projection_no_fake_article_CPU_failure_or_pair(self):
        s=selection()
        old={f"existing-{i}":{} for i in range(10676)}
        processed={x["source"]["id"]:record(x["source"])[0] for x in s}
        rows,hints,due,skipped=v.sourcefree_projection(s,old,processed,
                                                       "/nonexistent",SIDE,MANIFEST)
        self.assertEqual((len(rows),len(hints),due,skipped),(60,0,60,0))
        self.assertEqual({r["source_body_status"] for r in rows},{"UNAVAILABLE"})
        self.assertFalse(any(r["verified_public_original"] for r in rows))
        self.assertFalse(any("url" in r or "title" in r for r in rows))
        self.assertEqual(sum(r["auto_promotions"] for r in rows),0)
        report=v.summarize(rows,hints,due,skipped,SIDE,MANIFEST,{"sqlite_sha256":"f"*64})
        self.assertEqual(report["actual_acquired_body_states"],{"UNAVAILABLE":60})
        self.assertEqual(report["research_pair_admitted"],0)

    def test_successful_strict_source_body_retains_only_bound_hashes(self):
        selected=selection()
        item=selected[0]["source"]
        record0,body=record(item,"FULL",verified=True,
                            scope=[{"locator":{"start":0,"end":25},"role":"DEMAND",
                                    "target":"Material A"}])
        existing={f"existing-{i}":{} for i in range(10676)}
        existing.update({x["source"]["id"]:{"body_status":"FULL"} for x in selected[1:]})
        with mock.patch.object(v,"read_cached_body",return_value=body):
            rows,hints,n,skip=v.sourcefree_projection(selected,existing,
                                {item["id"]:record0},"/tmp",SIDE,MANIFEST)
        self.assertEqual((n,skip),(1,59))
        self.assertEqual(len(hints),1)
        self.assertEqual(hints[0]["span_sha256"],v.sha(body[:25]))
        self.assertNotIn("body",hints[0])
        self.assertNotIn("url",hints[0])
        self.assertFalse(hints[0]["strict_economic_pair_admitted"])

    def test_no_forged_scheduled_acquisition_or_source_hash(self):
        selected=selection()
        s=selected[0]["source"]
        rec,_=record(s)
        rec["acquisition"]["versions"][rec["fingerprint"]]["history"]=[]
        current={f"existing-{i}":{} for i in range(10676)}
        current.update({x["source"]["id"]:{} for x in selected[1:]})
        with self.assertRaisesRegex(ValueError,"ACTUAL_SOURCE_ATTEMPT_RECEIPT"):
            v.sourcefree_projection(selected,current,{s["id"]:rec},"/tmp",SIDE,MANIFEST)
        with self.assertRaisesRegex(ValueError,"CURRENT_RESULTS_MISSING"):
            v.gate_latest_sidecar({},selected)

    def test_sqlite_fresh_readback_and_explicit_fail_closed_tamper(self):
        selected=selection()
        old={f"existing-{i}":{} for i in range(10676)}
        output={x["source"]["id"]:record(x["source"])[0] for x in selected}
        records,hints,due,skip=v.sourcefree_projection(selected,old,output,
            "/tmp/notcached",SIDE,MANIFEST)
        summary=v.summarize(records,hints,due,skip,SIDE,MANIFEST,{"sqlite_sha256":"f"*64})
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)/"out"
            saved=v.persist(folder,summary,records,hints)
            check=v.fresh_readback(folder)
            self.assertEqual(check["attempted"],60)
            self.assertEqual(check["eligible_independent_pairs"],0)
            with self.assertRaisesRegex(ValueError,"OUTPUT_ALREADY_EXISTS"):
                v.persist(folder,summary,records,hints)
            saved["research_pair_admitted"]=1
            (folder/"s6-60-execution.json").write_text(v.canon(saved)+"\n")
            with self.assertRaisesRegex(ValueError,"FRESH_SQLITE_SUMMARY_OR_INDEPENDENCE_CHANGED"):
                v.fresh_readback(folder)

if __name__=="__main__":
    main()
