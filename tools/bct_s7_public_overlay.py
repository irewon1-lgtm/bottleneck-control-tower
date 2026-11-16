"""S7 bounded, verified GitHub Pages overlay WITHOUT replacing legacy V4 site.

Existing generated 511 historical ranking/1,703 detail files, JavaScript,
research records, and SHA-bound Pages manifest are immutable. Adds a small,
self-contained read-only source-truth page and a navigation link only.
"""
import argparse
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import re

from bct.objective_lock import require_objective

FORMAT="bct-s7-source-truth-preview-v1"
HIST_DATE="2026-10-14T23:16:13.592709+00:00"
RESEARCH_BRANCH="research/bct-s6-sourcefree-ledger-20261116"
RESEARCH_SQL_SHA="d0bef9da83910bf4ede638cea87df8f582bcb0cbb12033aee09aac64e832872d"
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA64=re.compile(r"^[0-9a-f]{64}$")
SITE_REL="source-truth"
TRUTH_ANCHOR='<a href="./source-truth/" class="bct-s7-link" aria-label="원출처 근거 검증 현황 보기">근거 검증 현황</a>'
BASE_URL="https://irewon1-lgtm.github.io/bottleneck-control-tower/"

def require(value, code):
    if not value:
        raise ValueError("BCT_S7_PUBLIC_"+code)

def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def time_value(iso):
    try:
        d=datetime.fromisoformat(iso.replace("Z","+00:00"))
        require(d.tzinfo is not None,"NAIVE_TIME")
        return d.astimezone(timezone.utc)
    except (AttributeError,TypeError,ValueError):
        raise ValueError("BCT_S7_PUBLIC_INVALID_TIME") from None

def status_contract(status, run_sha):
    require_objective(status)
    for sha in [run_sha]:
        require(isinstance(sha,str) and SHA40.fullmatch(sha),"SOURCE_RUN_SHA_INVALID")
    h=status.get("historical",{})
    r=status.get("research",{})
    admission=status.get("admission",{})
    deploy=status.get("deployment",{})
    generations=status.get("generations",{})
    require(status.get("format")==FORMAT
            and status.get("status")=="PASS_RESEARCH_SOURCEBOUND_PRESENTATION_PREVIEW_ONLY"
            and status.get("view")=="S7_PROOF_NOT_PUBLIC_OPERATING_PAGES",
            "STATUS_SOURCE_NOT_VERIFIED")
    require(h.get("status")=="FROZEN_2026_10_14_NOT_FRESH_EVIDENCE"
            and h.get("data_at_utc")==HIST_DATE
            and h.get("record_count")==511
            and h.get("counts")=={"reviewed":23,"structured":211,"discovery":277}
            and h.get("sector_ranked_records")==508
            and h.get("unclassified_records")==3
            and h.get("published_detail_files_different_units")==1703
            and h.get("overlay_new_originals_unpaired")==12
            and h.get("rank_is_current_verifiable_shortage") is False,
            "HISTORICAL_RANK_FALSELY_CURRENT")
    require(r.get("status")=="VERIFIED_S6_ISOLATED_SOURCE_FREE_HOLD"
            and r.get("branch")==RESEARCH_BRANCH
            and isinstance(r.get("commit_sha"),str)
            and SHA40.fullmatch(r["commit_sha"])
            and r.get("sqlite_sha256")==RESEARCH_SQL_SHA
            and r.get("rss_only_article_ids")==316
            and r.get("article_reentry_attempts")==60
            and r.get("body_states")=={"FULL":24,"PARTIAL":22,"UNAVAILABLE":14}
            and r.get("strict_original_publisher_body_date_verified")==18
            and r.get("registered_target_holds")==22
            and r.get("official_public_fact_codes_research_only")==20
            and r.get("new_sourcebound_research_hints_not_independent_pairs")==147
            and r.get("not_attempted_in_316_snapshot")==256
            and r.get("admitted_qualified_independent_pairs")==0
            and r.get("research_fact_units_not_additive_to_historical_count") is True
            and r.get("stage6_status")=="PARTIAL",
            "RESEARCH_FACT_SCOPE_OR_SHA_INVALID")
    require(admission.get("eligible_independent_pair_count")==0
            and admission.get("strict_pair_evaluation_for_all_corpus")=="NOT_PERFORMED"
            and admission.get("historical_rank_511_not_updated") is True
            and admission.get("new_research_hints_not_ranked") is True
            and deploy.get("public_pages_deployed_by_this_job") is False
            and deploy.get("operating_rss_or_sidecar_writes")==0
            and deploy.get("LIVE_writes")==deploy.get("public_rank_writes")==0
            and deploy.get("session8")=="NOT_RUN",
            "UNVERIFIED_SHORTAGE_OR_PRODUCTION_WRITES")
    require(generations.get("main_code_commit")==run_sha
            and all(isinstance(generations.get(key),str)
                    and SHA40.fullmatch(generations[key]) for key in
                    ("main_code_commit","rss_data_commit_observed",
                     "sidecar_commit_observed","research_ledger_commit"))
            and generations["research_ledger_commit"]==r["commit_sha"]
            and time_value(status.get("checked_at_utc"))>time_value(HIST_DATE),
            "SOURCE_RUN_AND_DATA_GENERATION_NOT_BOUND")
    return status

def legacy_contract(root,status):
    manifest=json.loads((root/"build-manifest.json").read_bytes())
    dashboard_bytes=(root/"api/dashboard.json").read_bytes()
    dashboard=json.loads(dashboard_bytes)
    require(manifest.get("site_type")=="PUBLIC_STATIC_READ_ONLY"
            and manifest.get("code_commit")==dashboard.get("publication",{}).get("code_commit")
            and manifest.get("evidence_count")==1703
            and dashboard.get("counts",{}).get("evidence")==511
            and dashboard.get("historical_data_at")==HIST_DATE
            and isinstance(dashboard.get("records"),list)
            and len(dashboard["records"])==511
            and dashboard.get("sector_rankings",{}).get("ranked_record_count")==508
            and dashboard.get("sector_rankings_live",{}).get("new_original_verified")==12
            and dashboard.get("sector_rankings_live",{}).get("no_verified_supply_shortage_promoted") is True
            and manifest.get("dashboard_sha256")==hash_bytes(dashboard_bytes),
            "EXISTING_PAGES_MANIFEST_511_OR_EVIDENCE_NOT_VERIFIED")
    require(status["historical"]["record_count"]==len(dashboard["records"])
            and status["historical"]["data_at_utc"]==dashboard["historical_data_at"],
            "PAGES_HISTORICAL_GENERATION_NOT_SAME")
    raw=(root/"index.html").read_text(encoding="utf-8")
    require(raw.count('src="./app.js"')==1
            and raw.count('<nav class="bct-tabs"')==1
            and raw.count('data-nav="candidates"')==1
            and raw.count('href="./source-truth/"')==0,
            "EXISTING_SITE_HTML_NOT_APPROVED")
    return manifest,raw

def page_content(status, historical_code_sha, run_id):
    r=status["research"];h=status["historical"]
    research_time="2026-11-16"
    observed=escape(status["checked_at_utc"])
    history_time=escape(h["data_at_utc"])
    code=escape(historical_code_sha[:12])
    rs=escape(r["commit_sha"][:12])
    side=escape(status["generations"]["sidecar_commit_observed"][:12])
    label=lambda n:format(n,",")
    table_rows=[
        ("기존 연구 근거 · 과거 집계",label(h["record_count"]),
         "2026-10-14 고정 자료 / 검증된 수요·공급 부족 수치가 아님"),
        ("과거 검토됨 · 구조화됨 · 탐색", "23 · 211 · 277",
         "동일한 이전 집계 단위, 합계 511"),
        ("최근 원문 접근 실제 시도",label(r["article_reentry_attempts"]),
         "2026-11-16 회차, 실제 HTTP 접근 및 본문 추출"),
        ("원문 FULL · PARTIAL · 미확보","24 · 22 · 14",
         "본문 확보 정도이며 독립 수급쌍 인증은 별도"),
        ("원출처 발행자·날짜·본문 검증",label(r["strict_original_publisher_body_date_verified"]),
         "60건 회차에서 엄격한 원출처 조건 통과"),
        ("공식 공시 사실 코드",label(r["official_public_fact_codes_research_only"]),
         "검증된 문서 사실, 제품별 수급쌍 아님"),
        ("원문 문장 위치·해시 단서",label(r["new_sourcebound_research_hints_not_independent_pairs"]),
         "탐색용 단서. 과거 511건과 합산 금지"),
        ("등록 TARGET 보류",label(r["registered_target_holds"]),
         "검증된 고객별 미예약 적격 공급·기간의 부족 근거 없음"),
        ("독립 적격 수급쌍 신규 통과","0",
         "이번 검증에서 입증된 쌍 0. 시장 병목이 없다는 의미 아님"),
    ]
    tr="\n".join("<tr><th scope='row'>"+escape(k)+"</th><td>"+escape(v)+
                 "</td><td>"+escape(note)+"</td></tr>"
                 for k,v,note in table_rows)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#102c59">
<meta name="description" content="BCT 과거 근거 511건과 최신 연구용 원출처 검증을 구분하는 읽기 전용 화면">
<meta http-equiv="refresh" content="3600">
<title>BCT V4 · 근거 검증 현황</title>
<style>
:root{{color-scheme:light;font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf3fb;color:#172b48;line-height:1.62}}
header{{background:#102f64;color:white;padding:18px clamp(16px,3vw,42px);display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}}
header strong{{font-size:1.1rem}}a{{color:inherit}}header a{{color:#e6f4ff;text-decoration:none;font-weight:650}}
main{{max-width:1200px;margin:auto;padding:24px clamp(14px,3vw,32px) 45px}}
h1{{font-size:clamp(1.55rem,3.1vw,2.35rem);letter-spacing:-.035em;margin:.1em 0 .3em}}
h2{{font-size:1.18rem;margin:0 0 14px}}.kicker{{font-size:.8rem;font-weight:750;letter-spacing:.1em;color:#28578c}}
.lede{{max-width:85ch;color:#3e526a;margin:0 0 20px}}
.cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}}
.card,.paper{{border:1px solid #ccd9e8;background:white;border-radius:10px;box-shadow:0 2px 5px #1024440a}}
.card{{padding:19px}}.card small{{display:block;color:#405672;font-size:.85rem;font-weight:650}}.card strong{{display:block;font-size:clamp(1.55rem,3vw,2.2rem);line-height:1.25;margin:8px 0}}
.card em{{display:block;font-size:.78rem;font-style:normal;color:#52677e}}
.paper{{padding:22px;margin-bottom:18px}}.warning{{border-left:4px solid #ad7736;background:#fff9ed}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;min-width:690px;font-size:.9rem}}
th,td{{padding:12px;border-bottom:1px solid #dbe4ee;text-align:left;vertical-align:top}}
thead{{background:#eaf1fa}}thead th{{font-size:.84rem}}tbody th{{font-weight:650;width:36%}}tbody td:nth-child(2){{white-space:nowrap;font-weight:750}}
.meta{{font-size:.83rem;color:#536883;overflow-wrap:anywhere}}
.meta code{{font-family:ui-monospace,Consolas,monospace}}footer{{font-size:.83rem;color:#4a607a;margin:24px 0}}
@media(max-width:760px){{.cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}.paper{{padding:16px}}}}
@media(max-width:400px){{.cards{{grid-template-columns:1fr 1fr;gap:8px}}.card{{padding:12px}}}}
</style>
</head>
<body>
<header><strong>BCT V4 · 미래 병목 탐색</strong><nav><a href="../">← 기존 병목 탐색판</a></nav></header>
<main><p class="kicker">SOURCE-BOUND RESEARCH · READ ONLY</p>
<h1>근거 검증 현황</h1>
<p class="lede">새 기사 수, 과거 섹터 연구 기록, 원출처 검증, 탐색 단서는 서로 다른 단위입니다. 원출처가 입증되지 않은 값을 실제 병목 순위에 더하지 않습니다.</p>
<div class="cards" aria-label="근거 검증 핵심 수치">
<div class="card"><small>과거 연구 기록</small><strong>511건</strong><em>2026년 10월 14일 기준</em></div>
<div class="card"><small>새 원출처 검증</small><strong>18건</strong><em>2026년 11월 16일 연구 회차</em></div>
<div class="card"><small>신규 탐색 단서</small><strong>147개</strong><em>독립 수급쌍 증거로 합산 불가</em></div>
<div class="card"><small>입증된 신규 적격 수급쌍</small><strong>0건</strong><em>22개 등록 TARGET HOLD</em></div>
</div>
<section class="paper warning"><h2>현재 입증 가능한 것과 불가능한 것</h2>
<p>과거 511건은 <strong>검토됨 23 + 구조화됨 211 + 탐색 277</strong>의 역사적 연구 기록입니다.
해당 날짜 이후 확인한 원출처 18건과 문장 단서 147개를 과거 511건에 더해 새 병목 점수로 만들지 않습니다.
실제 제품·규격·기간·지역·고객이 일치하는 독립 수요와 적격 미예약 공급량 비교는 아직 입증되지 않았습니다.</p></section>
<section class="paper"><h2>원장별 상세 현황</h2>
<div class="table-wrap"><table><thead><tr><th scope="col">자료</th><th scope="col">건수</th><th scope="col">판정과 기간</th></tr></thead>
<tbody>{tr}</tbody></table></div></section>
<section class="paper"><h2>기준 시각과 검증 계보</h2>
<p class="meta">과거 연구 레코드 기준: <code>{history_time}</code><br>
새 원문 판독 회차: <code>{research_time}</code><br>
화면의 원장 검증 실행: <code>{observed}</code> (새 기사 발행 시각이 아닙니다)<br>
기존 대시보드 코드: <code>{code}</code> · 연구 원장: <code>{rs}</code> · sidecar 관측: <code>{side}</code><br>
근거 검증 실행 ID: <code>{int(run_id)}</code></p>
<p class="meta">기존 공개 순위표의 511건을 대체하거나 수정하지 않았습니다. 연구 원장에는 해시와 HOLD 상태만 저장되며, 원문 전문 및 비공개 자료는 공개하지 않습니다.</p></section>
<footer>정적 읽기 전용 · BCT V4 | 이 페이지는 자동 생성된 검증 상태를 보여주며 주가 추천·실제 공급부족 확정 보고서가 아닙니다.</footer>
</main></body></html>
"""

def build(root,status_path,run_sha,run_id):
    root=Path(root)
    sbytes=Path(status_path).read_bytes()
    require(len(sbytes)<200000,"S7_SOURCE_STATUS_TOO_LARGE")
    status=status_contract(json.loads(sbytes),run_sha)
    child=root/SITE_REL
    require(not child.exists(),"DUPLICATE_RESEARCH_OVERLAY")
    manifest,index=legacy_contract(root,status)
    # No deletion, replacement, or reinterpretation of legacy dashboard counts.
    old_api=(root/"api/dashboard.json").read_bytes()
    old_js=(root/"app.js").read_bytes()
    old_manifest=(root/"build-manifest.json").read_bytes()
    modified=index.replace(
        '        <a href="#candidates" data-nav="candidates">검토 중인 변화</a>',
        '        <a href="#candidates" data-nav="candidates">검토 중인 변화</a>\n'
        '        '+TRUTH_ANCHOR)
    require(modified!=index and modified.count(TRUTH_ANCHOR)==1,
            "EXACT_LEGACY_LINK_INSERTION_FAILED")
    child.mkdir()
    (child/"index.html").write_text(
        page_content(status,manifest["code_commit"],run_id),encoding="utf-8")
    (child/"status.json").write_bytes(sbytes)
    (root/"index.html").write_text(modified,encoding="utf-8")
    require((root/"api/dashboard.json").read_bytes()==old_api
            and (root/"app.js").read_bytes()==old_js
            and (root/"build-manifest.json").read_bytes()==old_manifest,
            "LEGACY_GENERATION_REWRITTEN")
    view=(child/"index.html").read_text(encoding="utf-8")
    require('근거 검증 현황' in view and '511건' in view and '18건' in view
            and '147개' in view and '22개 등록 TARGET HOLD' in view
            and "기존 병목 탐색판" in view,
            "PUBLIC_SOURCE_TRUTH_HTML_INCOMPLETE")
    return {"status":"PASS_S7_PUBLIC_SOURCE_TRUTH_OVERLAY_BUILT",
            "public_relative":"source-truth/",
            "source_status_sha256":hash_bytes(sbytes),
            "page_html_sha256":hash_bytes((child/"index.html").read_bytes()),
            "historical_511":511,"new_originals_verified":18,
            "research_hints":147,"HOLD_targets":22,
            "independent_qualified_pairs_admitted":0,
            "legacy_dashboard_sha256":hash_bytes(old_api),
            "legacy_code_commit":manifest["code_commit"],
            "s7_authoritative_run_id":int(run_id),
            "s7_authoritative_run_sha":run_sha}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--site-root",type=Path,required=True)
    p.add_argument("--source-status",type=Path,required=True)
    p.add_argument("--run-sha",required=True)
    p.add_argument("--run-id",type=int,required=True)
    args=p.parse_args()
    print("BCT_S7_PAGES_SAFE_OVERLAY="+json.dumps(
        build(args.site_root,args.source_status,args.run_sha,args.run_id),
        ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":
    main()
