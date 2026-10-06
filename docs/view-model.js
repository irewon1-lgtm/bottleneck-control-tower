"use strict";
// Presentation only. Never changes a stored judgment or computes a new score.
((root) => {
  const statuses = {
    FUTURE: ["미래 병목", "미래 공급 제약 근거가 있는 대상", 0],
    EMERGING: ["병목 가능성", "변화는 확인됐으나 부족 범위·시점은 추가 확인", 1],
    OBSERVE: ["관찰 중", "관련 변화가 있지만 공급 부족은 미확인", 2],
    UNRESOLVED: ["판단 보류", "판정에 필요한 자료가 부족한 대상", 3],
    CURRENT: ["현재 병목", "이미 발생한 부족으로, 미래 병목과 별도 표시", 4]
  };
  const groups = {
    "us-defense-feoc-independent-high-energy-suas-cells": "미국 방산·드론 배터리",
    "large-gas-turbine-slots": "전력·발전", "uk-regional-grid-connections": "전력·계통",
    "novalt16-qualified-production-slots": "전력·발전",
    "compliant-non-china-tungsten": "방산·소재", "srm-ammonium-perchlorate": "방산·소재",
    "ai-package-tglass": "반도체·소재", "unobligated-haleu-us-qualified-supply": "핵연료",
    "inp-qualified-exportable-substrates": "광통신·기판", "cpo-qualified-cw-lasers": "광통신·레이저",
    "cpo-optical-electrical-volume-test": "광통신·검사", "silicon-photonics-wafer-level-burn-in": "광통신·검사",
    "cpo-els-garnet-optical-isolators": "광통신·부품"
  };
  const latest = target => target.history?.at(-1) || {};
  const status = value => statuses[value] || [value || "판단 미기록", "분류 설명이 아직 없습니다", 5];
  const clean = value => typeof value === "string" ? value.replaceAll("UNRESOLVED", "미확인").replaceAll("NO_PUBLIC_PLAY", "상장 투자수단 미확인") : value;
  const field = (target, names, baseline) => {
    for (const record of [...(target.history || [])].reverse()) {
      for (const name of names) {
        const value=name.split(".").reduce((current,key)=>current?.[key],record);
        if(value!=null && value!=="")return {value:clean(value),on:record.reviewed_on,sources:record.sources||[]};
      }
    }
    if (baseline) for (const name of names) if (baseline[name]) return {value: clean(baseline[name]), on: baseline.as_of, sources: baseline.sources || [], baseline: true};
    return {value: "자료 미확보", on: null, sources: []};
  };
  const url = value => { try { const parsed = new URL(value); return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null; } catch { return null; } };
  function documents(candidates) {
    return Object.entries(candidates?.results || {}).map(([id, record]) => {
      const hash = record.current_body_sha256 || record.body_sha256;
      const version = record.versions?.[hash] || {};
      const current = {...record, ...version, ...(version.screening || {})};
      return {id, title: record.title || id, name: record.title || id, url: record.url,
        source: record.source, checked_at: record.checked_at,
        candidate: current.candidate === true, reason: current.reason,
        body_status: ({BODY_OK:"PARTIAL",BODY_UNAVAILABLE:"UNAVAILABLE"}[current.body_status] || current.body_status || "UNAVAILABLE"),
        evidence: current.evidence || {}, locations: current.evidence_locations || {}, hash};
    });
  }
  function evidence(target, baseline) {
    const rows = [], seen = new Set();
    for (const record of [...(target.history || [])].reverse()) {
      const refs = new Map();
      for (const [kind, value] of Object.entries(record.comparison_inputs || {})) {
        for (const ref of value.evidence || []) if (url(ref.url)) {
          const old = refs.get(ref.url) || {published: ref.published_on, locator: ref.locator, kinds: []};
          old.kinds.push(kind); refs.set(ref.url, old);
        }
      }
      const all = [...(record.sources || []), ...refs.keys()];
      for (const raw of all) {
        const href = url(typeof raw === "string" ? raw : raw.url);
        if (!href || seen.has(href)) continue;
        seen.add(href); const ref = refs.get(href) || {};
        rows.push({url: href, label: typeof raw === "object" ? raw.label : new URL(href).hostname,
          reviewed: record.reviewed_on, published: ref.published, locator: ref.locator,
          kinds: [...new Set(ref.kinds || [])], reason: clean(record.reason), baseline: false});
      }
    }
    for (const ref of baseline?.sources || []) {
      const href = url(ref.url); if (!href || seen.has(href)) continue;
      seen.add(href); rows.push({url: href, label: ref.label, reviewed: baseline.as_of, baseline: true, kinds: []});
    }
    return rows;
  }
  function targets(tracking, verified) {
    const fixed = new Map((verified?.items || []).map(item => [item.id, {...item, as_of: verified.as_of}]));
    const auditRun = [...(tracking?.runs || [])].reverse().find(run => Array.isArray(run.evidence_gap_audit));
    const audit = new Map((auditRun?.evidence_gap_audit || []).map(item => [item.id, item]));
    const priorityIds = auditRun?.next_review_targets || [];
    const source = tracking ? tracking.targets : (verified?.items || []).map(item => ({id: item.id, target: item.target,
      history: [{...item, reviewed_on: verified.as_of, reason: item.constraint, sources: item.sources.map(s => s.url)}]}));
    return (source || []).map((target, index) => {
      const record = latest(target), base = fixed.get(target.id);
      return {target, latest: record, baseline: base, index, id: target.id,
        name: record.target_detail || target.target, sector: groups[target.id] || "분류 미등록",
        status: record.status || "UNRESOLVED", sources: evidence(target, base),
        audit: audit.get(target.id),
        priority: priorityIds.includes(target.id) ? priorityIds.indexOf(target.id) + 1 : null};
    }).sort((a,b) => status(a.status)[2] - status(b.status)[2] || (a.priority ?? 999) - (b.priority ?? 999) || a.index - b.index);
  }
  const known = value => value != null && value !== "" && String(value).toUpperCase() !== "UNKNOWN";
  const period = value => typeof value === "object" && value ? `${value.start || "UNKNOWN"} ~ ${value.end || "UNKNOWN"}` : known(value) ? String(value) : "UNKNOWN";
  function hypotheses(candidates) {
    return Object.entries(candidates?.hypotheses || {}).map(([id, stored]) => {
      const current = stored.current || {}, scope = current.scope || {}, draft = current.draft || {};
      const unknown = [...(draft.unconfirmed || [])];
      for (const [key, value] of Object.entries(scope)) if (!known(value)) unknown.push(key);
      for (const [key, value] of Object.entries(current.gates || {})) if (!known(value)) unknown.push(`gate.${key}`);
      if (!known(current.public_classification)) unknown.push("공개 선행성");
      if (!known(current.outcome?.actual_occurred)) unknown.push("실제 발생");
      return {id, name: known(scope.target) ? scope.target : "UNKNOWN", named: known(scope.target),
        stage: current.stage || "UNKNOWN", status: current.outcome?.status || "UNKNOWN",
        reviewRequired: current.review_required, period: period(scope.period),
        firstDetected: stored.first_detected_at || "UNKNOWN", text: draft.text || "UNKNOWN",
        unknown: [...new Set(unknown)], current, draft,
        evidence: (current.evidence || []).map(ref => ({...ref, title: candidates.results?.[ref.document_id]?.title || ref.document_id}))};
    });
  }
  const api = {statuses, status, clean, latest, field, evidence, targets, documents, hypotheses, url};
  root.BCTView = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
