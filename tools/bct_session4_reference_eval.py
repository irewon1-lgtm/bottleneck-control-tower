#!/usr/bin/env python3
"""BCT session 4: historical 200-document AI-reference audit of a frozen CPU screen.

The reference is pre-existing AI annotation, NOT expert/human gold. Compare only
the exact RSS metadata predictions already emitted by the completed Session 3
read-only run. No model calls, reannotation, publication, source fetching or
bottleneck-stage promotion are made here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random

VALID = {"TRUE", "FALSE", "UNKNOWN"}
SIGNALS = ("DEMAND", "SUPPLY", "RELIEF")
EXPECTED_REFERENCE_BLOBS = {
    "docs/v33-quality-reference.json": "b0acf501cb3e91b2dd194401821f763f2e1d4810",
    "docs/v33-regression-reference.json": "70f8969f583d73070467455ef5a50e62e79d2edb",
    "docs/v33-quality-source-manifest.json": "d8e09cf1ba14833cd13c0e3f4cfada3d30c99bf9",
    "docs/v33-regression-source-manifest.json": "e9a09cf0073928b559d5ea33529eaddd17e9e258",
}
PINNED_ARTICLE_SHA = "aa2e76c45c6167372c73504ca6f861133471c1b00d6799d6fe8566036c0dbfd2"
PINNED_SUMMARY_SHA = "3fa5e31c74b1c09d0cd50d52507774c163302e77df303edf217dcf4cf8e33169"
PINNED_DATA_SHA = "da7b17f34d58c69c72b5d067d6279ec98db8bb44"
PINNED_SIDECAR_SHA = "e8acd5e91f9f972974b5027a36056651098da71f"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def sha1_git_blob(raw):
    return hashlib.sha1(("blob "+str(len(raw))+"\0").encode()+raw).hexdigest()


def cell(value):
    s = "" if value is None else str(value)
    # Do not let malicious publisher titles turn into spreadsheet formulae.
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s


def strict_label(value):
    if isinstance(value, dict):
        value = value.get("value", value.get("status", "UNKNOWN"))
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    label = str(value).upper()
    if label not in VALID:
        raise ValueError("REFERENCE_LABEL_INVALID")
    return label


def any_truth(labels):
    values = [strict_label(labels.get(s, "UNKNOWN")) for s in SIGNALS]
    if "TRUE" in values:
        return "TRUE"
    if all(x=="FALSE" for x in values):
        return "FALSE"
    return "UNKNOWN"


def wilson(success, total, z=1.959963984540054):
    if not total: return None
    p=success/total
    n=total
    d=1+z*z/n
    mid=(p+z*z/(2*n))/d
    delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,mid-delta), min(1,mid+delta)]


def metrics(pairs):
    counts=Counter()
    for truth, predicted in pairs:
        if truth=="UNKNOWN":
            counts["UNKNOWN_REFERENCE"]+=1
            continue
        if truth not in {"TRUE","FALSE"} or type(predicted) is not bool:
            raise ValueError("METRIC_ROW_INVALID")
        counts[("TP" if predicted else "FN") if truth=="TRUE" else
               ("FP" if predicted else "TN")]+=1
    tp,fp,fn,tn=[counts[key] for key in ("TP","FP","FN","TN")]
    p=tp/(tp+fp) if tp+fp else None
    r=tp/(tp+fn) if tp+fn else None
    f1=2*p*r/(p+r) if p is not None and r is not None and p+r else None
    return {
        "TP":tp,"FP":fp,"FN":fn,"TN":tn,"UNKNOWN_REFERENCE":counts["UNKNOWN_REFERENCE"],
        "measurable":tp+fp+fn+tn,"total":len(pairs),
        "precision":p,"recall":r,"f1":f1,
        "precision_95pct_wilson":wilson(tp,tp+fp),
        "recall_95pct_wilson":wilson(tp,tp+fn),
        "precision_denominator":tp+fp,"recall_denominator":tp+fn,
        "unweighted_retrospective_AI_reference_only":True,
    }


def read_csv(path):
    raw=Path(path).read_bytes()
    if sha256(raw)!=PINNED_ARTICLE_SHA: raise ValueError("STAGE3_ARTICLE_LEDGER_HASH_MISMATCH")
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=10510 or any(not x.get("id") or not x.get("url") for x in rows):
        raise ValueError("STAGE3_ARTICLE_LEDGER_COUNT_INVALID")
    ids=[x["id"] for x in rows]
    if len(set(ids))!=len(ids):
        raise ValueError("STAGE3_ARTICLE_LEDGER_DUPLICATE_ID")
    for r in rows:
        if (r.get("metadata_classification")!="TITLE_SNIPPET_ONLY" or r.get("stage")!="NOT_EVALUATED"
                or r.get("metadata_priority") not in {"P1_MULTISIGNAL_METADATA","P2_TEXT_CUE","P3_BROAD_TEXT_CUE","P4_NO_METADATA_CUE"}
                or r.get("combined_review_lane") not in {
                    "Q1_PRIOR_FULL_BODY_LEAD","Q2_PRIOR_PARTIAL_BODY_LEAD",
                    "Q3_PRIOR_UNAVAILABLE_LEAD_HOLD","Q4_METADATA_SIGNAL_NEEDS_SOURCE",
                    "Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING"}):
            raise ValueError("STAGE3_LEDGER_PROVENANCE_INVALID")
    return rows


def frozen_references(root):
    for path, expected in EXPECTED_REFERENCE_BLOBS.items():
        raw=(root/path).read_bytes()
        if sha1_git_blob(raw)!=expected:
            raise ValueError("FROZEN_AI_REFERENCE_GIT_BLOB_CHANGED:"+path)
    groups={}
    used_ids=set()
    for name in ("regression","quality"):
        manifest=json.loads((root/f"docs/v33-{name}-source-manifest.json").read_text())
        reference=json.loads((root/f"docs/v33-{name}-reference.json").read_text())
        if (manifest.get("sample_id")!=reference.get("sample_id")
            or len(manifest.get("documents",[]))!=100
            or len(reference.get("documents",[]))!=100
            or reference.get("automatic_results_seen") is not False
            or reference.get("label_kind")!="AI_REFERENCE_NOT_HUMAN_GOLD"):
            raise ValueError("FROZEN_AI_REFERENCE_CONTRACT_INVALID:"+name)
        frozen_docs={x["id"]:x for x in manifest["documents"]}
        ref_docs={x["id"]:x for x in reference["documents"]}
        if frozen_docs.keys()!=ref_docs.keys() or used_ids.intersection(ref_docs):
            raise ValueError("REFERENCE_ID_OVERLAP_OR_MISMATCH")
        for did,ref in ref_docs.items():
            frozen=frozen_docs[did]
            if (ref["url"]!=frozen["url"] or ref["source"]!=frozen["source"]
                 or ref.get("automatic_results_seen") is not False):
                raise ValueError("REFERENCE_SOURCE_NOT_FROZEN")
            for signal in SIGNALS:
                strict_label(ref.get("labels",{}).get(signal,"UNKNOWN"))
        used_ids.update(ref_docs)
        groups[name]={"sample_id":reference["sample_id"],
            "reference_freeze_at":reference.get("recorded_at"),
            "frozen_source_commit":manifest["source_data_commit"],
            "source_count_at_freeze":manifest.get("source_count_observed_in_window"),
            "docs":ref_docs,"label_kind":reference["label_kind"]}
    if len(used_ids)!=200:
        raise ValueError("REFERENCE_NOT_200_DISJOINT_DOCUMENTS")
    return groups


def observed_signals(r):
    return set(filter(None,(r.get("title_snippet_signal_paths") or "").split("|")))


def prior_full_lead(r):
    return (r["combined_review_lane"]=="Q1_PRIOR_FULL_BODY_LEAD"
            and r["previous_body_status"]=="FULL"
            and r["previous_body_candidate_unverified"]=="True")


def any_combined_lead(r):
    return r["combined_review_lane"]!="Q5_NO_SIGNAL_IN_AVAILABLE_SCREENING"


def evaluate(rows, groups):
    records={r["id"]:r for r in rows}
    output={"format":"bct-session4-ai-reference-accuracy-v1",
        "status":"EVALUATED_RETROSPECTIVE_AI_REFERENCE_NOT_HUMAN_GOLD",
        "reference_documents_total":200,"reader_kind":"PREEXISTING_INDEPENDENT_AI_NOT_HUMAN_GOLD",
        "source_scope":"Historical frozen samples; not a live prospective forecast",
        "reference_body_hash_identical_to_current_rss":"NOT_PROVEN",
        "source_web_requests":0,"AI_provider_calls":0,"source_db_writes":0,
        "signal_validation_target":"RSS_TITLE_SNIPPET_FIRSTPASS_NOT_FUTURE_BOTTLENECK",
        "groups":{},"aggregate":{},"limits":[]}
    joined=[];missing=[];different=[]
    for name,group in groups.items():
        entries=[]
        for did,ref in group["docs"].items():
            current=records.get(did)
            if not current:
                missing.append({"sample":name,"id":did,"reason":"ID_ABSENT_FROM_CURRENT_RSS"})
                continue
            # Source URL and publisher must still be the same exact original.
            if ref["url"]!=current["url"] or ref["source"]!=current["source"]:
                different.append({"sample":name,"id":did,"reason":"ARTICLE_OR_SOURCE_CHANGED"})
                continue
            entries.append((current,ref))
            joined.append((name,current,ref))
        output["groups"][name]={
            "frozen_sample_id":group["sample_id"],
            "records":len(group["docs"]),"comparable":len(entries),
            "not_comparable":100-len(entries),
            "sources":dict(Counter(r["source"] for r,ref in entries)),
            "labels":{signal:dict(Counter(strict_label(ref["labels"].get(signal,"UNKNOWN"))
                for r,ref in entries)) for signal in SIGNALS}}
    output["aggregate"]["matched"] = len(joined)
    output["aggregate"]["not_comparable"] = missing+different
    output["aggregate"]["not_comparable_count"] = len(missing)+len(different)
    if len(joined)<100:
        output["status"]="BLOCKED_INSUFFICIENT_COMPARABLE_AI_REFERENCE"
    errrows=[]
    modes=("metadata_paths","combined_any","prior_full_body_any")
    aggregate=defaultdict(list)
    per_group=defaultdict(lambda: defaultdict(list))
    p4_total=0;p4_positive=0;p4_rescued=0
    by_source=defaultdict(list)
    for name,r,ref in joined:
        labels=ref.get("labels",{})
        paths=observed_signals(r)
        anylabel=any_truth(labels)
        old=prior_full_lead(r)
        is_p4=r["metadata_priority"]=="P4_NO_METADATA_CUE"
        if is_p4:
            p4_total+=1
            if anylabel=="TRUE":
                p4_positive+=1
                if old:p4_rescued+=1
        by_source[r["source"]].append((name,r,ref))
        for sig in SIGNALS:
            truth=strict_label(labels.get(sig,"UNKNOWN"))
            predict=sig in paths
            aggregate[("metadata_paths",sig)].append((truth,predict))
            per_group[name][("metadata_paths",sig)].append((truth,predict))
            if truth!="UNKNOWN" and truth != ("TRUE" if predict else "FALSE"):
                errrows.append({
                    "sample":name,"document_id":r["id"],"signal":sig,
                    "error":"FALSE_POSITIVE" if predict else "FALSE_NEGATIVE",
                    "reference_label":truth,"predicted_from":"TITLE_SNIPPET",
                    "title":r["title"],"source":r["source"],"url":r["url"],
                    "metadata_priority":r["metadata_priority"],
                    "combined_review_lane":r["combined_review_lane"],
                    "reference_status":ref.get("reference_status","UNKNOWN"),
                    "different_normalized_body_version":"UNVERIFIED"})
        for mode,pred in (("metadata_any",bool(paths)),
                          ("combined_any",any_combined_lead(r))):
            aggregate[(mode,"ANY")].append((anylabel,pred))
            per_group[name][(mode,"ANY")].append((anylabel,pred))
        # Prior FULL category is only comparable for *actually FULL* sidecar records.
        if r["previous_body_status"]=="FULL":
            aggregate[("prior_full_body_any","ANY")].append((anylabel,old))
            per_group[name][("prior_full_body_any","ANY")].append((anylabel,old))
    output["aggregate"]["metrics"]={
        mode:{signal:metrics(rows) for (m,signal),rows in sorted(aggregate.items()) if m==mode}
        for mode in ("metadata_paths","metadata_any","combined_any","prior_full_body_any")
    }
    for name in groups:
        output["groups"][name]["metrics"]={
            mode:{signal:metrics(v) for (m,signal),v in sorted(per_group[name].items()) if m==mode}
            for mode in ("metadata_paths","metadata_any","combined_any","prior_full_body_any")
        }
    output["aggregate"]["P4_hidden_reference"]={
        "P4_comparable":p4_total,
        "P4_reference_any_true":p4_positive,
        "P4_reference_positive_rescued_by_prior_full_body":p4_rescued,
        "P4_reference_positive_not_rescued":p4_positive-p4_rescued,
        "note":"Historical references only; unknown or falsely labeled examples are not treated as confirmed."
    }
    output["aggregate"]["source_counts"]={k:len(v) for k,v in sorted(by_source.items())}
    output["aggregate"]["false_positive_and_negative_metadata_rows"]=len(errrows)
    output["limits"]=[
        "AI reference is not expert human gold and may contain errors.",
        "Historical 200 articles came from frozen source windows, not a new random world-wide sample.",
        "Reference source reads lacked normalized-body-hash equivalence; confidence relates to label agreement, not full-body accuracy.",
        "Metric rates exclude source and signal UNKNOWN labels. Unmeasured reference cases cannot become negatives.",
        "Metadata screening sees only RSS title and summary; a lack of signal is not evidence that full article is irrelevant.",
        "Old sidecar FULL/candidate flags are screening leads, not confirmed future supply-demand gaps.",
        "Same publishers and repeated events may be dependent; Wilson intervals do not correct source/event clustering.",
        "No evaluation of 12-36 month prospective bottleneck discovery or securities returns."
    ]
    return output,errrows


def frozen_blind_packet(rows, historical_ids, *, count=240):
    """Precommit new balanced-source review URLs before future output is read.

    Do not show predictions, Q/P buckets or historical labels in reviewer packet.
    """
    eligible=[r for r in rows if r["id"] not in historical_ids]
    by_source=defaultdict(list)
    for r in eligible:
        by_source[r["source"]].append(r)
    chosen=[];used=set()
    def deterministic_key(r):
        return hashlib.sha256(("BCT-S4-NOV13-PRECOMMIT-01|"+r["id"]).encode()).hexdigest()
    # First cover all present source hosts; within host avoid same lane when possible.
    for src,items in sorted(by_source.items()):
        buckets=defaultdict(list)
        for r in items:
            buckets[r["combined_review_lane"]].append(r)
        for values in buckets.values():
            values.sort(key=deterministic_key)
        first=[values[0] for values in buckets.values() if values]
        for r in sorted(first,key=deterministic_key)[:5]:
            if len(chosen)>=count:break
            chosen.append(r);used.add(r["id"])
    # Fill across queues by minimizing representation of each queue and source.
    while len(chosen)<min(count,len(eligible)):
        freq_q=Counter(r["combined_review_lane"] for r in chosen)
        freq_src=Counter(r["source"] for r in chosen)
        pool=[r for r in eligible if r["id"] not in used]
        if not pool:break
        row=min(pool,key=lambda r:(freq_q[r["combined_review_lane"]],
                                   freq_src[r["source"]],deterministic_key(r)))
        chosen.append(row);used.add(row["id"])
    # Output sorted independently of predictions, so review order is not a score hint.
    chosen.sort(key=deterministic_key)
    assert len(chosen)==min(count,len(eligible))
    return chosen


def write_csv(path,records,fields):
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow({k:cell(r.get(k)) for k in fields})


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--article-ledger",type=Path,required=True)
    p.add_argument("--session3-summary",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    raw=args.session3_summary.read_bytes()
    if sha256(raw)!=PINNED_SUMMARY_SHA:
        raise ValueError("STAGE3_SUMMARY_HASH_MISMATCH")
    session3=json.loads(raw)
    if (session3.get("status")!="PASS_READ_ONLY_METADATA_FIRSTPASS"
        or session3["rss_git_sha"]!=PINNED_DATA_SHA
        or session3["sidecar_git_sha"]!=PINNED_SIDECAR_SHA
        or session3.get("total")!=10510
        or session3.get("rescued_p4_using_prior_full_body_leads")!=2843):
        raise ValueError("STAGE3_GENERATION_MISMATCH")
    rows=read_csv(args.article_ledger)
    references=frozen_references(Path.cwd())
    result,err=evaluate(rows,references)
    historical=set().union(*(set(g["docs"]) for g in references.values()))
    fresh=frozen_blind_packet(rows,historical)
    result["actual_article_ledger_sha256"]=PINNED_ARTICLE_SHA
    result["actual_summary_sha256"]=PINNED_SUMMARY_SHA
    result["frozen_reference_blobs"]=EXPECTED_REFERENCE_BLOBS
    result["new_blind_packet"]={"size":len(fresh),"unique_publishers":len({r["source"] for r in fresh}),
        "selection":"Deterministic balanced 48-source candidate pool, labels withheld",
        "prediction_labels_visible_to_reviewers":False,"historical_200_overlap":len(historical & {r["id"] for r in fresh}),
        "packet_sha256":None}
    referr_cols=["sample","document_id","signal","error","reference_label","predicted_from",
                 "source","url","title","metadata_priority","combined_review_lane",
                 "reference_status","different_normalized_body_version"]
    write_csv(out/"metadata_errors.csv",err,referr_cols)
    reviewer=[
        {"review_id":f"BLIND-{i:03d}","document_id":r["id"],"source":r["source"],
         "url":r["url"],"title":r["title"],"published_at":r["published_at"],
         "DEMAND_label":"UNKNOWN","SUPPLY_label":"UNKNOWN","RELIEF_label":"UNKNOWN",
         "source_quote_or_locator":"","independent_reader_notes":""}
        for i,r in enumerate(fresh,1)]
    packet_cols=["review_id","document_id","source","url","title","published_at",
                 "DEMAND_label","SUPPLY_label","RELIEF_label",
                 "source_quote_or_locator","independent_reader_notes"]
    write_csv(out/"blind_reference_packet_240.csv",reviewer,packet_cols)
    packet_raw=(out/"blind_reference_packet_240.csv").read_bytes()
    result["new_blind_packet"]["packet_sha256"]=sha256(packet_raw)
    (out/"blind_sample_provenance.json").write_text(
        json.dumps({"sample_hash":sha256(packet_raw),"source_data_sha":PINNED_DATA_SHA,
                    "stage3_artifact_sha":PINNED_ARTICLE_SHA,
                    "selected_ids": [r["id"] for r in fresh],
                    "source_distribution":dict(Counter(r["source"] for r in fresh)),
                    "lane_distribution":dict(Counter(r["combined_review_lane"] for r in fresh)),
                    "priority_distribution":dict(Counter(r["metadata_priority"] for r in fresh)),
                    "references_200_excluded":True,
                    "reviewer_packet_omits_all_predictions":True},ensure_ascii=False,indent=2)+"\n")
    (out/"evaluation_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    m=result["aggregate"]["metrics"]["metadata_paths"]
    report=[
        "# BCT 세션 4 — 동결된 AI 정답 200건과 실제 CPU 선별 결과 비교",
        "",
        "**원문 판독의 인간 정답이 아닙니다. 기존 AI 참고 정답과 RSS 제목·요약 자동 분류의 일치도만 측정합니다.**",
        "",
        f"- 평가 입력: 기존 AI 참조 200건, 실제 RSS 매칭 {result['aggregate']['matched']}건",
        f"- 원문 해시 정합성: 미입증. 새 외부 모델·원문 다운로드·증거 승격: 0.",
        "",
        "| 신호 | 정밀도 (TP / TP+FP) | 재현율 (TP / TP+FN) | UNKNOWN |",
        "|---|---:|---:|---:|",
    ]
    for sig in SIGNALS:
        val=m[sig]
        fmt=lambda x:"측정 불가" if x is None else f"{x*100:.1f}%"
        report.append(f"| {sig} | {fmt(val['precision'])} ({val['TP']}/{val['precision_denominator']}) | {fmt(val['recall'])} ({val['TP']}/{val['recall_denominator']}) | {val['UNKNOWN_REFERENCE']} |")
    report.extend([
        "",
        f"- 새 평가용 블라인드 자료: {len(fresh)}건, 분리된 PDF/원문 판독 전부 UNKNOWN.",
        f"- 과거 P4 자료 내 AI 양성/기존 본문 리드로 복구: {result['aggregate']['P4_hidden_reference']}",
        "- 과거 reference는 2026년 10월 자료이며 분석기 개발에 활용되었을 가능성을 배제할 수 없습니다.",
        "- 이번엔 새 원문 의미 판독이나 독립 인간 라벨을 생산하지 않았습니다.",
        "- 원문 본문·제품 규격·시점·적격 공급능력 검증과 S단계 판정은 후속 별도 작업.",
        "- 오류별 자료: metadata_errors.csv; 새로운 평가 후보: blind_reference_packet_240.csv",
    ])
    (out/"session4_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print("BCT_SESSION4_EVALUATION="+json.dumps({
        "status":result["status"],"matched":result["aggregate"]["matched"],
        "not_comparable_count":result["aggregate"]["not_comparable_count"],
        "metadata_paths":m,
        "aggregate_any":result["aggregate"]["metrics"]["metadata_any"]["ANY"],
        "combined_any":result["aggregate"]["metrics"]["combined_any"]["ANY"],
        "prior_full":result["aggregate"]["metrics"]["prior_full_body_any"].get("ANY"),
        "P4_hidden_reference":result["aggregate"]["P4_hidden_reference"],
        "new_blind_packet":result["new_blind_packet"],
        "metadata_error_rows":len(err),
        "sources":result["aggregate"]["source_counts"]},ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
