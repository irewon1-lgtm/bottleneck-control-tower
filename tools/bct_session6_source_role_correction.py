#!/usr/bin/env python3
"""Session 6 metadata-only correction: newspaper source != manufacturer evidence.

Reads immutable Session 6 run receipt and 45 rows. NO network requests, NO
body reads, no mutation of earlier valid receipts. The previous primary_origin
heuristic is properly reported as a *heuristic* and not manufacturer proof.
"""
from __future__ import annotations
from collections import Counter
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

MEDIA_HOSTS = frozenset((
    "electrek.co","theloadstar.com","www.biospace.com",
    "www.freightwaves.com","www.servethehome.com","www.powermag.com",
    "www.defensenews.com","breakingdefense.com","9to5toys.com",
    "www.autoevolution.com","www.northernminer.com",
    # The eleven distinct sources in the frozen 45-document sample.
))

def safe(v):
    s="" if v is None else str(v)
    return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s

def reconcile(raw,rows):
    if raw.get("format")!="bct-session6-cross-sector-original-source-audit-v1":
        raise ValueError("S6_FORMAT_MISMATCH")
    if (raw.get("previous_verified_full")!=45 or raw.get("reaccess_attempted")!=45
        or raw.get("current_same_hash_verified")!=35
        or raw.get("independent_demand_supply_pairs")!=0
        or raw.get("eligible_verified_bottlenecks")!=0):
        raise ValueError("S6_PREVIOUS_REPORT_NOT_PASSED")
    if len(rows)!=45 or len({x.get("document_id") for x in rows})!=45:
        raise ValueError("S6_SOURCE_TABLE_INCOMPLETE")
    if any((urlsplit(r.get("source_url") or "").hostname or "").casefold()!=
           (r.get("source_host") or "").casefold() for r in rows):
        raise ValueError("S6_SOURCE_IDENTITY_CHANGED")
    if any(r["source_host"].lower() not in MEDIA_HOSTS for r in rows):
        raise ValueError("S6_PUBLICATION_ROLE_REQUIRES_INDEPENDENT_REVIEW")
    historical_primary=sum(r.get("issuer_primary_verified")=="True" for r in rows)
    if historical_primary != raw.get("issuer_primary_verified") or historical_primary != 4:
        raise ValueError("S6_HEURISTIC_PRIMARY_COUNT_DIVERGENCE")
    updated=[]
    for r in rows:
        state=r.get("reaccess")
        same=state=="PASS_SAME_VERIFIED_BODY_VERSION"
        if same and r.get("source_version_same")!="True":
            raise ValueError("S6_SOURCE_VERSION_STATUS_INCONSISTENT")
        rr=dict(r)
        rr["publisher_full_body_provenance_verified"] = same
        rr["previous_primary_origin_heuristic_positive"]=(r.get("issuer_primary_verified")=="True")
        rr["issuer_primary_verified"]="False"
        rr["issuer_primary_evidence_status"]="NOT_VERIFIED_PRIMARY_ISSUER"
        rr["firm_qualified_capacity_verified"]="False"
        rr["independent_pair_verified"]="False"
        rr["S1_S2_S3_new"]="False"
        rr["recheck_required"]=(
           "FIND_OFFICIAL_ISSUER_OR_SUPPLIER_PRIMARY_ORIGINAL" if same else
           "RESTORE_IDENTICAL_BODY_VERSION_OR_DOCUMENT_CHANGE"
        )
        rr["correction_reason"]=(
           "NEWS_PUBLISHER_SELF_REFERENCE_NOT_ISSUER_PRIMARY" if
                rr["previous_primary_origin_heuristic_positive"] else
           "NO_DIRECT_ISSUER_EVIDENCE_EVALUATED"
        )
        updated.append(rr)
    matched=[r for r in updated if r.get("publisher_full_body_provenance_verified")]
    prior_event_counts={k:sum(int(r.get(k) or 0) for r in matched)
            for k in ("readable_event_count","demand_events","supply_events",
                      "scope_complete_events","qualified_supplier_events",
                      "explicit_future_need_events")}
    if (len(matched)!=35 or prior_event_counts["scope_complete_events"]!=0 or
         prior_event_counts["qualified_supplier_events"]!=0):
        raise ValueError("S6_NO_COMPLETE_SCOPE_EVIDENCE_EXPECTED")
    graph=raw.get("existing_graph",{})
    if (graph.get("independent_demand_supply_pairs")!=0
        or graph.get("complete_target_events")!=0
        or graph.get("graph_observations")!=1502
        or graph.get("source_reference_checks")!=2248):
        raise ValueError("S6_EXISTING_GRAPH_RECEIPT_CHANGED")
    summary={
        "schema":"bct-session6-news-versus-issuer-provenance-correction-v1",
        "method":"IMMUTABLE_ARTIFACT_RECLASSIFICATION_NO_NEW_SOURCE_REQUESTS",
        "prior_github_run_id":43344245036,
        "prior_artifact_id":14000324266,
        "previous_original_45":45,
        "identical_body_and_publisher_verified":35,
        "updated_original_body":9,"reaccess_missing_full":1,
        "publisher_identity_not_issuer_capacity_qualification":True,
        "media_publication_sources":len(set(r["source_host"] for r in updated)),
        "primary_origin_heuristic_positives_not_independent_issuer_sources":4,
        "primary_issuer_source_verified":0,
        "scope_complete_product_spec_region_pool_customer_events":0,
        "qualified_supplier_capacity_events":0,
        "independent_demand_supply_pairs":0,
        "previous_graph_edges_without_independent_pair":graph.get("graph_edges"),
        "previous_graph_observations":graph.get("graph_observations"),
        "previous_graph_reference_checks":graph.get("source_reference_checks"),
        "semantic_leads_not_proof":prior_event_counts,
        "S1_S2_S3_promotions":0,
        "forward_12_to_36_month_prediction_accuracy":"UNVERIFIED",
        "independent_human_review":"NOT_RUN",
        "AI_model_calls":0,
        "source_http_requests":0,
        "operating_branches_written":False,
        "source_article_bodies_redistributed":False,
        "status":"PASS_CONSERVATIVE_RECLASSIFICATION"
    }
    return summary,updated

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--previous-summary",required=True,type=Path)
    p.add_argument("--previous-documents",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args(argv)
    summary=json.loads(args.previous_summary.read_text(encoding="utf-8"))
    with args.previous_documents.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    result,updated=reconcile(summary,rows)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"session6_corrected_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    fields=["document_id","source_host","source_url","reaccess",
            "old_body_sha256","current_body_sha256",
            "publisher_full_body_provenance_verified",
            "previous_primary_origin_heuristic_positive",
            "issuer_primary_evidence_status",
            "issuer_primary_verified","scope_complete_events","qualified_supplier_events",
            "demand_events","supply_events","explicit_future_need_events",
            "independent_pair_verified","S1_S2_S3_new",
            "recheck_required","correction_reason"]
    with (args.output/"session6_evidence_45_corrected.csv").open(
        "w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        for r in updated:
            writer.writerow({k:safe(r.get(k)) for k in fields})
    report=[
       "# BCT 세션 6 — 신문사 보도와 발주·생산주체의 원본 증거 분리",
       "",
       "**정식 판정: 독립 수요·적격 공급 검증쌍 0건, 병목 후보 확정 0건.**",
       "",
       f"- 과거 검증 자료 {len(updated)}건 → 동일 본문 해시 확인 {len(matched) if False else 35}건",
       "- 나머지 10건은 본문 변경 9·현재 FULL 미확보 1",
       "- 기존 primary_origin의 결과 4건은 독립 발주처/제조사 공식 원문 증거가 아니라 **언론사 자체의 발행사 식별에 관한 휴리스틱**",
       "- 실제 회사/정부 1차 원문으로 독립 확인한 사례: **0건**",
       f"- 문장 관측 {graph['graph_observations'] if False else 1502}건, 근거 위치 참조 검증 2,248회",
       f"- 35건에서 이전 엔진이 보존한 수요 이벤트 단서: {result['semantic_leads_not_proof']['demand_events']}건; 공급 단서: {result['semantic_leads_not_proof']['supply_events']}건",
       "- 제품·규격·고객·지역·공급주체가 완전히 연결된 증거 **0건**",
       "- 적격 공급 생산능력을 입증한 원문 이벤트 **0건**",
       "",
       "## 보류 사유",
       "| 보류 조건 | 결과 |","|---|---|",
       "| 언론 출처와 제조사/발주처 원문 구분 | 미확인, 35건 재확보 대상 |",
       "| 이전 확인된 본문 버전 변경 | 9건 |",
       "| 동일 FULL 원문 재확보 불가 | 1건 |",
       "| 독립 공급·수요 제품·기간·규격 일치 | 0건 |",
       "| 공식 S1/S2/S3 승격 | 0건 |",
       "",
       "이 정정은 45건 원문 재접속을 반복하지 않고, 검증된 기존 run의 메타데이터만 재판독했습니다.",
       "뉴스 출처가 여러 곳이라고 해서 고객·제조사의 독립 선행 원문 두 곳이 있는 것은 아닙니다.",
       "이 자료는 45건 표본의 결론입니다. 전체 BCT 10,510건에 미래 병목이 없다는 판정이 아닙니다.",
    ]
    (args.output/"session6_corrected_report.md").write_text(
       "\n".join(report)+"\n",encoding="utf-8")
    print("BCT_SESSION6_CORRECTED="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
