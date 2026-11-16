"""S5 authentic public-origin policy regressions. No network or real original text."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import bct_s5_primary_originals_crosscheck as s5

MANIFEST=Path(__file__).resolve().parents[1]/"config/bct-s5-public-primary-pilot-20261116.json"

def loaded():
    return json.loads(MANIFEST.read_text())

def sampled():
    m=loaded(); sources=s5.validate_manifest(m)
    rows=[]
    for source in sources:
        rows.append(s5.classify_source(source,None,acquired_at="2026-11-16T00:00:00+00:00"))
    return m,rows

class TestS5PublicPrimary(unittest.TestCase):
    def test_manifest_is_exact_eight_public_sources(self):
        m=loaded()
        self.assertEqual(len(s5.validate_manifest(m)),8)
        self.assertTrue(all(x["url"].startswith("https://") for x in m["sources"]))

    def test_no_private_url_or_futuristic_timestamp_or_private_query(self):
        m=loaded()
        m["sources"][0]["url"]="https://127.0.0.1/secret"
        m["sources"][0]["host"]="127.0.0.1"
        with self.assertRaisesRegex(ValueError,"NON_PUBLIC_IP"):s5.validate_manifest(m)
        m=loaded();m["sources"][0]["published_date"]="2027-01-02"
        with self.assertRaisesRegex(ValueError,"FUTURE_PRIMARY_EVIDENCE"):s5.validate_manifest(m)
        m=loaded();m["mode"]="LIVE"
        with self.assertRaisesRegex(ValueError,"MANIFEST_NOT_FIXED"):s5.validate_manifest(m)

    def test_issuer_and_public_origin_alone_not_verified_evidence(self):
        m=loaded();source=m["sources"][0]
        out=s5.classify_source(source,None,acquired_at="2026-11-16T00:00:00+00:00")
        self.assertEqual(out["status"],"ACCESS_HOLD")
        self.assertEqual(out["fact_codes"],[])
        self.assertFalse(out["verified_original"])

    def test_real_body_hash_and_published_date_gate_and_fact_match(self):
        m=loaded();source=m["sources"][0]
        body="Antares now has two qualified sources and terms for an initial allocation of one metric ton of uranium."
        proof={"body":body,"body_sha256":s5.sha(body),"raw_sha256":s5.sha(b"html"),
               "provenance":"PASS","provenance_verified":True,
               "published_at":"2026-10-27T10:00:00+00:00",
               "checks":{"http_success":True,"original_identity":True}}
        item=s5.classify_source(source,proof,acquired_at="2026-11-16T00:00:00+00:00")
        self.assertTrue(item["verified_original"])
        self.assertEqual(item["fact_codes"],[
            "TRISO_BWXT_INITIAL_1MTU","TRISO_TWO_QUALIFIED_FAB_SOURCES"])
        self.assertNotIn("body",item)
        old=copy.deepcopy(proof);old["published_at"]="2026-10-26T10:00:00+00:00"
        item=s5.classify_source(source,old,acquired_at="2026-11-16T00:00:00+00:00")
        self.assertEqual(item["fact_codes"],[])
        self.assertEqual(item["held_fact_codes"],[
            "TRISO_BWXT_INITIAL_1MTU","TRISO_TWO_QUALIFIED_FAB_SOURCES"])
        old=copy.deepcopy(proof);old["body_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"FETCHED_BODY_DIGEST_MISMATCH"):
            s5.classify_source(source,old,acquired_at="2026-11-16T00:00:00+00:00")

    def test_two_issuers_same_contract_never_become_two_independent_economic_events(self):
        m,rows=sampled();sources=m["sources"]
        for i in (0,1):
            rows[i].update(retrieved=True,verified_original=True,
                           status="ORIGINAL_SOURCE_VERIFIED",fact_codes=[list(sources[i]["fact_patterns"])[0]],
                           held_fact_codes=[])
        summary=s5.summarize(m,rows)
        self.assertEqual(summary["independent_original_issuers_with_verified_facts"],2)
        self.assertEqual(summary["same_contract_deduplicated_event_groups"][
            "ANTARES_BWXT_FABRICATION_CONTRACT"]["original_issuers_with_verified_facts"],2)
        self.assertEqual(summary["strict_eligible_supply_demand_pairs"],0)
        self.assertEqual(summary["candidate_or_LIVE_writes"],0)

    def test_source_free_fresh_sqlite_roundtrip_and_tamper(self):
        m,rows=sampled();summary=s5.summarize(m,rows)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"proof"
            rec=s5.save_output(out,summary,sorted(rows,key=lambda x:x["id"]))
            self.assertEqual(s5.readback(out)["sources"],8)
            self.assertEqual(rec["attempted_public_primary_urls"],8)
            with self.assertRaisesRegex(ValueError,"OUTPUT_OVERWRITE_FORBIDDEN"):
                s5.save_output(out,summary,rows)
            (out/"cases.sqlite3").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"SQLITE_ARCHIVE_HASH_CHANGED"):
                s5.readback(out)

    def test_exact_visible_public_issuer_headline_adjacent_date_and_fact_without_strict_promotion(self):
        source=loaded()["sources"][0]
        fact=list(source["fact_patterns"].values())[0]
        text=(f"<html><main><h1>{source['visible_title']}</h1>"
              f"<time>{source['visible_date']}</time><article>{fact}</article>"
              f"<footer>{source['visible_issuer_marker']}</footer>"
              + "<p>additional sourced article observations and production context. </p>"*16
              + "</main></html>")
        raw=text.encode()
        proof={"body":fact+" additional genuine article text "*20,
               "raw_sha256":s5.sha(raw)}
        proof["body_sha256"]=s5.sha(proof["body"])
        self.assertTrue(s5.attested_visible_primary(source,raw,source["url"],proof))
        proof["provenance"]="BLOCKED"
        proof["provenance_verified"]=False
        proof["published_at"]=None
        proof["checks"]={"full_accessible_body":False}
        proof["provenance_blockers"]=["full_accessible_body","original_publication"]
        case=s5.classify_source(source,proof,acquired_at="2026-11-16T00:00:00Z",
                                visible_attested=True)
        self.assertFalse(case["verified_original"])
        self.assertTrue(case["visible_primary_attested"])
        self.assertEqual(case["fact_codes"],[])
        self.assertTrue(case["attested_fact_codes"])
        self.assertEqual(case["live_changes"],0)

    def test_official_title_from_other_news_or_wrong_date_does_not_establish_attestation(self):
        src=loaded()["sources"][0]
        fact=list(src["fact_patterns"].values())[0]
        text=(f"<html><h1>{src['visible_title']}</h1>"
              + "background unrelated report " * 160
              +f"<time>{src['visible_date']}</time>"
              +f"<p>{fact}</p><footer>{src['visible_issuer_marker']}</footer></html>")
        raw=text.encode()
        proof={"body":fact+"."*800,"raw_sha256":s5.sha(raw)}
        proof["body_sha256"]=s5.sha(proof["body"])
        self.assertFalse(s5.attested_visible_primary(src,raw,src["url"],proof))
        text=f"<h1>{src['visible_title']}</h1><p>{src['visible_date']}</p><p>{fact}</p>"
        raw=text.encode()
        proof["raw_sha256"]=s5.sha(raw)
        self.assertFalse(s5.attested_visible_primary(src,raw,src["url"],proof))

if __name__=="__main__":
    unittest.main()
