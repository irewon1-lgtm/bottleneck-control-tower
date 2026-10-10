"use strict";
(() => {
  const pages = {
    ranking: ["미래 병목 한눈에 보기", "병목 뉴스가 나오기 전에 후보를 만들고 있는지, 무엇을 보고 있고 무엇이 부족한지 확인합니다."],
    detail: ["TARGET 상세", ""],
    evidence: ["근거 보기", "판단에 연결된 원문과 실제로 확보된 내용을 확인합니다."],
    review: ["관찰 중", "아직 후보로 확정하지 못한 TARGET과 부족한 근거를 봅니다."],
    situation: ["상태 변화", "각 TARGET의 이전 판단과 최신 판단이 어떻게 바뀌었는지 확인합니다."],
    insights: ["부족한 자료", "다음 판단에 필요한 수요·공급·시점·완화 자료를 봅니다."],
    dashboard: ["수집 대시보드", "현재 수집 결과와 기존 SIGNAL·Family 현황"],
    future: ["초기 확인 자료", "기존 고정 검증 결과와 연결 근거"],
    tracking: ["기술 기록", "검토 단계·가설·대기열·누적 이력을 확인하는 내부 화면"],
    sectors: ["섹터 신호", "PRESSURE → 출처 수 → 최근 신호 → RELIEF 순서"],
    signals: ["수집 기사", "기존 SIGNAL 결과 · 제목과 요약문 기준"],
    ai: ["저장된 판독", "현재 DB에 저장된 AI 보조판독 결과"],
    families: ["후보 묶음", "기존 Candidate Family 집계"],
    system: ["시스템 상태", "본문 확보, 처리 대기, 수집 오류와 운영 관찰"]
  };
  const content = document.getElementById("content");
  const states = Object.fromEntries(Object.keys(pages).map(key => [key, {filter: "전체", query: "", period: "all", page: 1}]));
  const number = value => value == null ? "데이터 없음" : Number(value).toLocaleString("ko-KR");
  const DISPLAY = {
    PRESSURE: "압박", RELIEF: "완화", NEUTRAL: "중립",
    CURRENT_FACT: "현재 사실", CONDITIONAL: "조건부", FORECAST: "전망", PLAN: "계획",
    UNRESOLVED: "확인 필요", PRODUCT: "제품", COMPONENT: "부품", MATERIAL: "원재료",
    PROCESS: "공정", SUPPLY_CHAIN_STEP: "공급망 단계",
    SHORTAGE: "부족", LEAD_TIME: "납기", CAPACITY: "생산능력", BACKLOG: "수주잔고",
    DELAY: "지연", EXPANSION: "증설", RAMP: "생산 확대", NEW_SUPPLIER: "신규 공급자",
    NORMALIZATION: "정상화", OTHER: "기타", OK: "정상", ERROR: "오류",
    global: "글로벌", mining: "광업", manufacturing: "제조업", industrials: "산업재",
    fulfillment: "풀필먼트", "oil shipping": "원유 해운", "petroleum refining": "정유",
    "petroleum refining and logistics": "정유·물류", "material handling": "물류·자재 취급",
    brands: "브랜드", "small and medium-sized manufacturers": "중소 제조업체"
  };
  const display = value => value == null || value === "" ? "데이터 없음" : (DISPLAY[value] || value);
  const sectorDisplay = value => value && value !== "미분류" ? display(value) : "섹터 정보 없음";
  const aiMode = value => value === "scheduled" ? "예약 실행 설정" : value === "manual" ? "수동" : "데이터 없음";
  const date = value => {
    const parsed = new Date(value);
    return !value || Number.isNaN(parsed.getTime()) ? "데이터 없음" : new Intl.DateTimeFormat("ko-KR", {
      timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
    }).format(parsed);
  };
  const node = (tag, text, className) => {
    const value = document.createElement(tag);
    if (text != null) value.textContent = String(text);
    if (className) value.className = className;
    return value;
  };
  const pill = (text, className) => node("span", text || "데이터 없음", `pill ${className || (text || "").toLowerCase()}`);
  const empty = (title, message) => {
    const box = node("div", null, "empty");
    box.append(node("strong", title), node("span", message));
    return box;
  };
  const panel = (title, caption) => {
    const box = node("section", null, "panel");
    if (title) box.append(node("h2", title, "panel-title"));
    if (caption) box.append(node("p", caption, "panel-caption"));
    return box;
  };
  const metric = (label, value, note) => {
    const box = node("div", null, "metric");
    box.append(node("label", label), node("strong", typeof value === "number" ? number(value) : value ?? "데이터 없음"));
    if (note) box.append(node("small", note));
    return box;
  };
  function table(headers, rows, cells, onClick) {
    const wrap = node("div", null, "table-wrap");
    const element = node("table");
    const thead = node("thead");
    const header = node("tr");
    headers.forEach(label => { const th = node("th", label); th.scope = "col"; header.append(th); });
    thead.append(header);
    const body = node("tbody");
    rows.forEach((item, index) => {
      const row = node("tr");
      cells(item, index).forEach(value => {
        const cell = node("td");
        cell.append(value instanceof Node ? value : node("span", value ?? "데이터 없음"));
        row.append(cell);
      });
      if (onClick) {
        row.className = "clickable";
        row.tabIndex = 0;
        row.setAttribute("aria-label", `${item.name} 상세 보기`);
        row.addEventListener("click", () => onClick(item));
        row.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onClick(item); }
        });
      }
      body.append(row);
    });
    element.append(thead, body); wrap.append(element); return wrap;
  }
  function collectionList(rows) {
    const list = node("ul", null, "compact-list");
    rows.forEach(row => {
      const item = node("li");
      item.append(node("span", date(row.updated_at), "muted"), node("span", row.name),
        pill(row.status === "succeeded" ? "성공" : row.status === "failed" ? "실패" : row.status || "미기록", row.status === "succeeded" ? "ok" : row.status === "failed" ? "error" : "neutral"));
      list.append(item);
    });
    return rows.length ? list : empty("수집 기록 없음", "현재 snapshot에 수집 실행 기록이 없습니다.");
  }
  let snapshot = null;
  let verified = null;
  let verifiedError = false;
  let tracking = null;
  let queueResolution = null;
  let futureCandidates = null;
  let candidatesError = false;
  let trackingLoading = false;
  let trackingError = false;
  let loading = false;
  const route = () => Object.hasOwn(pages, location.hash.slice(1).split("/")[0]) ? location.hash.slice(1).split("/")[0] : "ranking";
  const researchRoutes = ["ranking", "detail", "evidence", "review", "situation", "insights", "system", "tracking"];
  const view = globalThis.BCTView;
  function toolbar(key, filters, usePeriod) {
    const state = states[key];
    const bar = node("div", null, "toolbar");
    const choices = node("div", null, "filters");
    filters.forEach(([label, count]) => {
      const button = node("button", `${display(label)} (${number(count)})`, "filter");
      button.type = "button";
      button.setAttribute("aria-pressed", String(state.filter === label));
      button.addEventListener("click", () => { state.filter = label; state.page = 1; render(); });
      choices.append(button);
    });
    const right = node("div", null, "toolbar-right");
    if (usePeriod) {
      const select = node("select", null, "select");
      select.setAttribute("aria-label", "기간 필터");
      [["all", "전체 기간"], ["7", "최근 7일"], ["30", "최근 30일"]].forEach(([value, label]) => {
        const option = node("option", label); option.value = value; select.append(option);
      });
      select.value = state.period;
      select.addEventListener("change", () => { state.period = select.value; state.page = 1; render(); });
      right.append(select);
    }
    const search = node("input", null, "search");
    search.type = "search"; search.placeholder = "검색…"; search.setAttribute("aria-label", "검색"); search.value = state.query;
    search.addEventListener("input", () => { state.query = search.value; state.page = 1; renderRows(key); });
    right.append(search); bar.append(choices, right); return bar;
  }
  const matches = (row, state) => JSON.stringify(row).toLocaleLowerCase().includes(state.query.toLocaleLowerCase());
  function inPeriod(value, state) {
    if (state.period === "all") return true;
    const stamp = new Date(value).getTime();
    return Number.isFinite(stamp) && stamp >= Date.now() - Number(state.period) * 86400000;
  }
  function paginate(key, rows, body, renderer, message) {
    const state = states[key], count = Math.max(1, Math.ceil(rows.length / 15));
    state.page = Math.min(state.page, count);
    body.replaceChildren();
    if (!rows.length) { body.append(empty(message || "표시할 결과 없음", "저장된 결과 또는 필터 조건을 확인해 주세요.")); return; }
    body.append(renderer(rows.slice((state.page - 1) * 15, state.page * 15)));
    const pager = node("div", null, "pager");
    const previous = node("button", "이전"), next = node("button", "다음");
    previous.disabled = state.page <= 1; next.disabled = state.page >= count;
    previous.addEventListener("click", () => { state.page--; renderRows(key); });
    next.addEventListener("click", () => { state.page++; renderRows(key); });
    pager.append(node("span", `${number(rows.length)}건 · ${state.page} / ${count}`), previous, next); body.append(pager);
  }
  function articleTitle(row) {
    const label = node("a", row.title, "title-link");
    try { const url = new URL(row.url); if (["http:", "https:"].includes(url.protocol)) { label.href = url.href; label.target = "_blank"; label.rel = "noopener noreferrer"; } } catch { /* A missing URL remains plain text. */ }
    return label;
  }
  function reviewCell(row, field) {
    const value = row.result?.[field];
    return display(value);
  }
  function renderRows(key) {
    const body = document.getElementById("table-body"), state = states[key];
    if (!body || !snapshot) return;
    if (key === "signals") {
      const rows = snapshot.signal_articles.filter(row => (state.filter === "전체" || row.directions.includes(state.filter)) && matches(row, state) && inPeriod(row.published_at || row.collected_at, state));
      paginate(key, rows, body, subset => table(["제목", "섹터", "신호", "출처", "사실 상태", "시간 (KST)"], subset, row => {
        const signals = node("div", null, "cell-stacked"); row.directions.forEach(value => signals.append(pill(display(value), value.toLowerCase())));
        return [articleTitle(row), sectorDisplay(row.sector), signals, row.source, display(row.fact_status), date(row.published_at || row.collected_at)];
      }));
    } else if (key === "ai") {
      const rows = snapshot.ai_reviews.filter(row => (state.filter === "전체" || row.status === state.filter) && matches(row, state) && inPeriod(row.created_at, state));
      paginate(key, rows, body, subset => table(["기사 제목", "대상 유형", "대상 이름", "지역", "산업", "고객", "사실 상태", "신호 방향", "신호 유형", "원출처", "근거 메모", "상태"], subset, row => [row.title, ...["TARGET_TYPE", "TARGET_NAME", "SCOPE_REGION", "SCOPE_INDUSTRY", "SCOPE_CUSTOMER", "FACT_STATUS", "SIGNAL_DIRECTION", "SIGNAL_TYPE", "UPSTREAM_SOURCE", "EVIDENCE_NOTE"].map(field => reviewCell(row, field)), pill(display(row.status), row.status?.toLowerCase())]), snapshot.ai_reviews.length ? null : "아직 수동 AI 판독 결과 없음");
    } else if (key === "families") {
      const rows = snapshot.families.filter(row => (state.filter === "전체" || (row.status || "데이터 없음") === state.filter) && matches(row, state));
      paginate(key, rows, body, subset => table(["Family 이름", "섹터", "관련 기사", "출처 수", "현재 상태", "최근 업데이트 (KST)"], subset, row => [row.name, row.sector || "미분류", number(row.article_count), number(row.source_count), pill(row.status || "데이터 없음", "review"), date(row.latest_at)], showFamily));
    } else if (key === "system") {
      const rows = snapshot.feeds.filter(row => matches(row, state) && (state.filter === "전체" || (state.filter === "성공" ? row.status === "succeeded" : row.status === "failed")));
      paginate(key, rows, body, subset => table(["RSS 이름", "최근 실행 상태", "시도 횟수", "최근 수집 (KST)", "오류"], subset, row => [row.name, pill(row.status === "succeeded" ? "성공" : row.status === "failed" ? "실패" : row.status || "미기록", row.status === "succeeded" ? "ok" : row.status === "failed" ? "error" : "neutral"), number(row.attempts), date(row.updated_at), row.last_error || (row.status === "succeeded" ? "기록된 오류 없음" : "데이터 없음")]));
    }
  }
  function showFamily(row) {
    document.getElementById("dialog-title").textContent = row.name;
    const body = document.getElementById("dialog-content"); body.replaceChildren();
    const values = [["섹터", row.sector || "미분류"], ["현재 상태", row.status || "데이터 없음"], ["구성 항목", row.members?.join(", ")], ["관련 기사 수", number(row.article_count)], ["출처 수", number(row.source_count)], ["PRESSURE", number(row.pressure_articles)], ["RELIEF", number(row.relief_articles)], ["확인된 범위", row.confirmed_scope?.join(", ")], ["미해결 범위", row.unresolved_scope?.join(", ")], ["최근 업데이트", date(row.latest_at)]];
    const list = node("dl");
    values.forEach(([label, value]) => { const pair = node("div", null, "key-value"); pair.append(node("dt", label), node("dd", value || "데이터 없음")); list.append(pair); });
    body.append(list); document.getElementById("family-dialog").showModal();
  }
  function verifiedPanels() {
    const box = panel("검증된 미래병목", verified ? `검증 기준 ${verified.as_of} · ${verified.note}` : "8단계 고정 검증 결과");
    if (!verified) {
      box.append(empty(verifiedError ? "고정 결과를 불러올 수 없음" : "고정 결과 확인 중", verifiedError ? "페이지를 다시 열어 주세요. 기존 수집 데이터와는 별도로 표시됩니다." : "검증된 3개 병목을 불러옵니다."));
      return box;
    }
    const cards = node("div", null, "verified-cards");
    verified.items.forEach(item => {
      const card = node("article", null, "verified-card");
      card.append(pill(item.status, item.status.toLowerCase()), node("h3", item.target));
      const connections = node("p", null, "verified-connections");
      connections.textContent = item.companies.map(company => `${company.ticker} · ${company.role}`).join(" / ");
      card.append(connections);
      const gaps = node("p", null, "verified-connections");
      gaps.append(pill(`UNRESOLVED ${item.unresolved.length}항목`, "unresolved"));
      if (item.no_public_play.length) gaps.append(node("span", " "), pill(`NO_PUBLIC_PLAY ${item.no_public_play.length}단계`, "unresolved"));
      card.append(gaps);
      const details = node("details");
      details.append(node("summary", "공급망·근거·기업 연결 보기"));
      const list = node("dl");
      [["병목 공급망 단계", item.stage], ["핵심 수요 근거", item.demand], ["핵심 공급제약", item.constraint], ["예상 수요 시점", item.demand_timing], ["공급완화·증설 시점", item.relief_timing]].forEach(([label, value]) => {
        const pair = node("div", null, "key-value");
        pair.append(node("dt", label), node("dd", value || "UNRESOLVED")); list.append(pair);
      });
      details.append(list, node("h4", "미국 상장사 연결"));
      item.companies.forEach(company => {
        const entry = node("div", null, "verified-company");
        const heading = node("p");
        heading.append(node("strong", `${company.ticker} · ${company.name} (${company.listing}) `), pill(company.role, company.role.toLowerCase()));
        entry.append(heading, node("p", company.evidence), node("p", company.business_share, "muted"), articleTitle({title: "공식 사업·공시 근거 ↗", url: company.source}));
        details.append(entry);
      });
      if (item.no_public_play.length) {
        details.append(node("h4", "NO_PUBLIC_PLAY · 투자표현 없음"));
        item.no_public_play.forEach(value => details.append(node("p", value)));
      }
      details.append(node("h4", "UNRESOLVED · 미확정 항목"));
      const unresolved = node("ul"); item.unresolved.forEach(value => unresolved.append(node("li", value))); details.append(unresolved);
      details.append(node("h4", "근거 출처"));
      const sources = node("ul"); item.sources.forEach(source => { const entry = node("li"); entry.append(articleTitle({title: source.label, url: source.url})); sources.append(entry); }); details.append(sources);
      card.append(details); cards.append(card);
    });
    box.append(cards); return box;
  }
  async function loadVerified() {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch("./verified-bottlenecks.json", {cache: "no-cache", signal: controller.signal});
      if (!response.ok) throw new Error("Verified results unavailable");
      const value = await response.json();
      if (value.version !== 1 || !value.as_of || !Array.isArray(value.items) || value.items.length !== 3 || !value.items.every(item => ["FUTURE", "EMERGING"].includes(item.status) && item.target && Array.isArray(item.companies) && Array.isArray(item.sources) && Array.isArray(item.unresolved) && Array.isArray(item.no_public_play))) throw new Error("Invalid verified results");
      verified = value;
    } catch { verifiedError = true; }
    finally { clearTimeout(timeout); if (["dashboard", "future", ...researchRoutes].includes(route())) render(); }
  }
  function trackingPanels() {
    const box = panel("지속 추적 기록", tracking ? `기록 갱신 ${tracking.updated_at || "데이터 없음"} · ${number(tracking.targets.length)}개 TARGET` : "정기 점검과 요청 조사의 누적 기록");
    if (!tracking || trackingError) {
      box.append(empty(trackingError ? "최신 추적 기록을 읽지 못했습니다" : "추적 기록 확인 중", tracking ? "아래는 마지막으로 읽은 기록입니다." : "기존 수집 결과와 고정 검증 결과는 다른 메뉴에서 확인할 수 있습니다."));
      if (trackingError) {
        const retry = node("button", "다시 확인", "filter"); retry.type = "button";
        retry.addEventListener("click", loadTracking); box.append(retry);
      }
      if (!tracking) return box;
    }
    box.append(node("p", "기존 상태·과거 이력을 보존합니다. S단계는 근거 수준이며 CURRENT/FUTURE와 구분합니다. 병목·기업 이익·시장 선반영은 각각 검토합니다.", "panel-caption"));
    const cards = node("div", null, "verified-cards");
    tracking.targets.forEach(target => {
      const latest = target.history[target.history.length - 1] || {};
      const card = node("article", null, "verified-card tracking-card");
      card.append(pill(latest.status || "UNRESOLVED", "unresolved"), node("h3", latest.target_detail || target.target));
      card.append(node("p", `최근 점검 ${latest.reviewed_on || "데이터 없음"} · ${target.history.length}개 판단 이력`, "verified-connections"));
      card.append(node("p", latest.reason || "판단 근거 데이터 없음"));
      const assessment = latest.supply_gap;
      if (assessment && assessment.version === "supply-gap-v1") {
        const labels = {UNRESOLVED: "확인 필요", FUTURE_MATCH: "현재 부족 아님 · 24개월 내 부족 근거 확인",
          CURRENT_REFERENCE: "현재 부족 · 참고 대상", OUTSIDE_WINDOW: "24개월 범위 밖",
          GAP_SUPPORTED: "수급 시간차 근거 있음", GAP_CONDITIONAL: "수요·공급 범위 겹침",
          NO_GAP_IN_RANGE: "입력 범위에서 부족 없음"};
        card.append(node("p", `목표 적합성: ${labels[assessment.objective_fit] || "확인 필요"} · 수급 판정: ${labels[assessment.gap_status] || "확인 필요"}`, "verified-connections"));
        const range = assessment.gap_range;
        if (Array.isArray(range) && range.length === 2 && range.every(Number.isFinite))
          card.append(node("p", `수요 − 적격 공급: ${number(range[0])} ~ ${number(range[1])} ${assessment.unit || ""}`));
        card.append(node("p", `시장 선반영: ${assessment.market_awareness || "UNRESOLVED"} · 기업 이익 귀속: ${assessment.economic_capture || "UNRESOLVED"}`, "muted"));
        if (Array.isArray(assessment.blockers) && assessment.blockers.length) {
          const details = node("details"); details.append(node("summary", `판정에 필요한 근거 (${assessment.blockers.length})`));
          assessment.blockers.forEach(text => details.append(node("p", text, "muted"))); card.append(details);
        }
      }
      if (latest.next_check) card.append(node("p", `다음 확인: ${latest.next_check}`));
      const sources = node("ul");
      [...new Set(latest.sources || [])].forEach(url => {
        let label; try { const parsed = new URL(url); if (!["http:", "https:"].includes(parsed.protocol)) return; label = parsed.hostname; } catch { return; }
        const entry = node("li"); entry.append(articleTitle({title: label, url})); sources.append(entry);
      });
      if (!sources.children.length && target.baseline_source) {
        const entry = node("li"); entry.append(articleTitle({title: "기존 고정 검증 기록", url: target.baseline_source})); sources.append(entry);
      }
      card.append(sources.children.length ? sources : node("p", "근거 링크 데이터 없음", "muted"));
      cards.append(card);
    });
    box.append(cards.children.length ? cards : empty("추적 TARGET 없음", "저장된 추적 기록에 TARGET이 없습니다."));
    return box;
  }
  function futureQueuePanel() {
    const box = panel("처리 대기 현황", "이 숫자는 시스템 작업량입니다. 미래병목 후보 수가 아니며 같은 문서가 여러 대기에 겹칠 수 있습니다.");
    const summary = futureCandidates?.summary || {}, queue = summary.review_queue;
    if (candidatesError) {
      box.append(node("p", futureCandidates ? "최신 대기 기록을 읽지 못했습니다. 표시된 내용은 마지막으로 읽은 집계입니다." : "대기 기록을 읽지 못했습니다. 연결 상태를 다시 확인해 주세요.", "muted"));
      const retry = node("button", "다시 확인", "filter"); retry.type = "button";
      retry.addEventListener("click", loadTracking); box.append(retry);
    }
    if (!futureCandidates) { if (!candidatesError) box.append(empty("대기 기록 확인 중", "최근 파일을 불러옵니다.")); return box; }
    if (!queue) { box.append(empty("검토 대기 집계 준비 중", "기존 후보 기록은 보존돼 있습니다.")); return box; }
    if (summary.recovery_queue?.counts) box.append(recoveryQueueMetrics(summary.recovery_queue));
    if (queueResolution?.data_store_status === "APPLIED_READBACK_VERIFIED"
        && Date.parse(queue.computed_at) < Date.parse(queueResolution.as_of)) {
      box.append(node("p", "아래는 실패 분리 전의 집계입니다. 처리 후 결과는 ‘정체 작업 처리 결과’에서 확인할 수 있습니다.", "data-note"));
    }
    box.append(node("p", `수집 완료 ${date(summary.checked_at)} · 대기 집계 ${date(queue.computed_at)}`, "muted"));
    const metrics = node("div", null, "metrics");
    [["자동으로 걸린 문서", queue.automatic_candidates], ["1차 읽기 대기", queue.quick_pending],
     ["정밀 검토 대기", queue.deep_pending], ["추가 자료 대기", queue.candidate_data_wait],
     ["원문 확보 대기", queue.material_pending], [summary.recovery_queue?.counts ? "보존된 판독 결과" : "판독 완료", queue.completed_documents]].forEach(([label, value]) => metrics.append(metric(label, value)));
    if (queue.failed_versions != null) metrics.append(metric("실패로 종료한 작업", queue.failed_versions, "미해결이며 판독 완료에 포함하지 않습니다."));
    box.append(metrics, node("p", `최장 대기 ${queue.oldest_wait_hours == null ? "데이터 없음" : Number(queue.oldest_wait_hours).toFixed(1) + "시간"} · 사건 ${number(queue.event_count)}개`, "panel-caption"));
    const guide = node("div", null, "queue-guide");
    [
      ["자동으로 걸린 문서", "규칙이 관심 문서로 표시했습니다. 병목 확정이라는 뜻은 아닙니다."],
      ["1차 읽기 대기", "본문은 있지만 아직 내용 분류가 끝나지 않았습니다."],
      ["원문 확보 대기", "본문이 없거나 일부만 있어 먼저 원문을 확보해야 합니다."],
      ["정밀 검토 대기", "1차 검토 뒤 수요·공급을 더 깊게 비교해야 합니다."],
      ["추가 자료 대기", "문서는 읽었지만 수량·날짜·독립 근거가 부족합니다."]
    ].forEach(([label, note]) => {
      const item = node("div", null, "queue-guide-item");
      item.append(node("strong", label), node("span", note));
      guide.append(item);
    });
    box.append(guide);
    const preview = node("ul", null, "compact-list");
    (queue.preview || []).slice(0, 5).forEach(item => {
      const record = futureCandidates.results?.[item.document_id] || {};
      const entry = node("li");
      entry.append(articleTitle({title: record.title || item.document_id, url: item.url || record.url}),
                   node("span", `${item.body_status || "미확인"} · 이어서 ${item.resume_at ?? 0}`, "muted"));
      preview.append(entry);
    });
    box.append(preview.children.length ? preview : empty("대표 대기 문서 없음", "저장된 집계 기준입니다."));
    const bundles = Object.values(futureCandidates.bundles || {});
    const details = node("details"); details.append(node("summary", `고정 검토 묶음 ${number(bundles.length)}개`));
    bundles.forEach(bundle => {
      const section = node("div"); section.append(node("h3", bundle.id || bundle.bundle_id));
      (bundle.documents || []).forEach(ref => {
        const record = futureCandidates.results?.[ref.document_id] || {};
        const row = node("p"); row.append(articleTitle({title: record.title || ref.document_id, url: ref.url || record.url}),
          node("span", ` · 버전 ${(ref.body_sha256 || "").slice(0, 12)} · 범위 ${ref.start ?? ref.read_start ?? 0}–${ref.end ?? ref.read_end ?? "전체"}`, "muted"));
        section.append(row);
      });
      details.append(section);
    });
    box.append(details, articleTitle({title: "전체 문서·묶음 기록 열기", url: "https://github.com/irewon1-lgtm/bottleneck-control-tower/blob/future-bottleneck-data/future-candidates.json"}));
    return box;
  }
  function recoveryQueueMetrics(recovery) {
    const box = node("div", null, "recovery-queue");
    box.setAttribute("data-recovery-generation", recovery.generation_run_id || "");
    const labels = {PENDING:"실제 판독 대기",PROCESSING:"판독 진행 중",COMPLETED:"FULL 판독 완료",SOURCE_WAIT:"원문 대기",EVIDENCE_WAIT:"근거 대기",FAILED:"남은 실패",RETRY_SCHEDULED:"재시도 예약"};
    const metrics = node("div", null, "metrics");
    Object.entries(labels).forEach(([state,label]) => {
      const value = metric(label,recovery.counts[state]);
      value.setAttribute("data-recovery-state",state);
      metrics.append(value);
    });
    box.append(metrics,node("p",`문서 버전 ${number(recovery.total_queue_versions)}개를 중복 없이 구분했습니다. 과거 실패 ${number(recovery.preserved_failure_versions)}건과 부분 본문 판독 결과 ${number(recovery.non_full_read_results ?? recovery.legacy_partial_read_results)}건은 이력으로 보존하며 FULL 완료에 더하지 않습니다.`,"data-note"));
    return box;
  }
  async function readStoredJSON(base, name, options) {
    const response = await fetch(`${base}${name}?t=${Date.now()}`, options);
    if (!response.ok) throw new Error("Record unavailable");
    const manifest = await response.json();
    if (!["bct-sharded-sidecar-v1", "bct-sharded-sidecar-v2"].includes(manifest?.format)) return manifest;
    const value = {}, counts = {}, kinds = {}, stem = name.replace(/\.json$/, "");
    for (const field of manifest.fields) {
      if (Object.hasOwn(kinds, field.name) || !["dict", "list", "value"].includes(field.kind)) throw new Error("Invalid manifest field");
      Object.defineProperty(kinds, field.name, {value: field.kind, enumerable: true});
      Object.defineProperty(value, field.name, {value: field.kind === "dict" ? {} : field.kind === "list" ? [] : null, enumerable: true, writable: true});
      Object.defineProperty(counts, field.name, {value: 0, enumerable: true, writable: true});
    }
    for (const [index, part] of manifest.shards.entries()) {
      const expectedPath = manifest.format === "bct-sharded-sidecar-v2"
        ? `${stem}.shards/by-sha256/${part.sha256}.json`
        : `${stem}.shards/${manifest.document_sha256}/${stem}.part-${String(index + 1).padStart(3, "0")}.json`;
      if (part.path !== expectedPath) throw new Error("Invalid shard path/order");
      const response = await fetch(`${base}${part.path}`, options);
      if (!response.ok) throw new Error("Shard unavailable");
      const raw = await response.text(), bytes = new TextEncoder().encode(raw);
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
      if (bytes.length > 10 * 1024 * 1024 || hash !== part.sha256) throw new Error("Shard hash/size mismatch");
      const shard = JSON.parse(raw);
      if (shard.format !== "bct-json-shard-v1" || shard.items.length !== part.item_count) throw new Error("Shard count mismatch");
      for (const item of shard.items) {
        if (!Object.hasOwn(kinds, item.field)) throw new Error("Unknown shard field");
        const kind = kinds[item.field];
        if (kind === "dict") {
          if (typeof item.key !== "string" || Object.hasOwn(value[item.field], item.key)) throw new Error("Duplicate shard record");
          Object.defineProperty(value[item.field], item.key, {value: item.value, enumerable: true, writable: true});
        } else if (kind === "list") {
          if (!Number.isInteger(item.key) || item.key !== value[item.field].length) throw new Error("Out-of-order shard record");
          value[item.field].push(item.value);
        } else {
          if (item.key !== null || counts[item.field]) throw new Error("Duplicate scalar");
          value[item.field] = item.value;
        }
        counts[item.field]++;
      }
    }
    if (Object.keys(counts).length !== Object.keys(manifest.item_counts).length || Object.entries(counts).some(([k, n]) => n !== manifest.item_counts[k]) || Object.values(counts).reduce((a, b) => a + b, 0) !== manifest.total_item_count) throw new Error("Manifest count mismatch");
    return value;
  }
  async function readDisplayJSON(base, name, options) {
    if (typeof DecompressionStream !== "function") return readStoredJSON(base, name, options);
    const response = await fetch(`${base}${name.replace(/\.json$/, ".ui.json.gz")}?t=${Date.now()}`, options);
    if (response.status === 404) return readStoredJSON(base, name, options);
    if (!response.ok) throw new Error("Display record unavailable");
    const raw = await new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).text();
    const envelope = JSON.parse(raw);
    if (envelope.format !== "bct-sidecar-display-v1" || typeof envelope.payload !== "string") throw new Error("Invalid display record");
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(envelope.payload))), b => b.toString(16).padStart(2, "0")).join("");
    if (hash !== envelope.payload_sha256) throw new Error("Display payload hash mismatch");
    if (["future-candidates.json", "future-tracking.json"].includes(name)) {
      const authoritative = await fetch(`${base}${name}?t=${Date.now()}`, options);
      if (!authoritative.ok) throw new Error("Latest generation unavailable");
      const root = await authoritative.text(), manifest = JSON.parse(root);
      const sourceHash = manifest.document_sha256 || Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(root))), b => b.toString(16).padStart(2, "0")).join("");
      if (sourceHash !== envelope.source_document_sha256) throw new Error("Display generation is stale");
    }
    return JSON.parse(envelope.payload);
  }
  async function loadTracking() {
    if (trackingLoading) return;
    trackingLoading = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const base = "https://raw.githubusercontent.com/irewon1-lgtm/bottleneck-control-tower/future-bottleneck-data/";
      const [record, queue] = await Promise.allSettled(["future-tracking.json", "future-candidates.json"].map(async name => {
        return readDisplayJSON(base, name, {cache: "no-store", signal: controller.signal});
      }));
      try {
        const value = record.status === "fulfilled" ? record.value : null;
        if (!value || value.version !== 1 || !Array.isArray(value.targets) || !value.targets.every(target => target && typeof target.id === "string" && typeof target.target === "string" && Array.isArray(target.history) && target.history.every(entry => entry && typeof entry === "object" && (!entry.sources || Array.isArray(entry.sources))))) throw new Error("Invalid tracking record");
        tracking = value; trackingError = false;
      } catch { trackingError = true; }
      try {
        const candidates = queue.status === "fulfilled" ? queue.value : null;
        if (!candidates || !candidates.results || typeof candidates.results !== "object" || Array.isArray(candidates.results)) throw new Error("Invalid candidates");
        futureCandidates = candidates; candidatesError = false;
      } catch { candidatesError = true; }
    } catch { trackingError = true; candidatesError = true; }
    finally { clearTimeout(timeout); trackingLoading = false; if (researchRoutes.includes(route())) render(); }
  }
  function resolutionPanel() {
    const report = queueResolution;
    if (!report) return null;
    const box = panel("정체 작업 처리 결과", `확인 ${date(report.as_of)} KST · 고정 운영 자료에 대한 처리 결과입니다.`);
    const metrics = node("div", null, "metrics");
    metrics.append(metric("기존 판독 완료 보존", report.preserved_completed_documents),
      metric("이번 신규 판독 완료", report.new_reading_completions),
      metric("실패로 종료한 작업", report.unresolved_versions, "원문과 이력은 보존하며 미해결로 계속 계산합니다."));
    box.append(metrics, node("p", "같은 조건의 실패를 반복하지 않습니다. 실패 작업은 실행 대기에서 분리했으며 운영채택은 HOLD, 예측성능은 UNVERIFIED입니다.", "data-note"));
    const labels = {ENVIRONMENT_DNS_RESOLUTION_FAILED: "원문 접근 실패: 확인 환경의 DNS 해석 오류",
      FULL_SOURCE_NOT_OBTAINED: "완전한 원문 확보 실패: 저장된 접근·추출 근거 확인",
      REQUIRED_EVIDENCE_MISSING: "판단 근거 부족: 저장된 DATA_INSUFFICIENT 판독 확인"};
    const list = node("ul", null, "compact-list");
    Object.entries(report.failure_reason_counts || {}).forEach(([reason, count]) => {
      list.append(node("li", `${labels[reason] || reason} ${number(count)}건 · 재개 조건: ${report.resume_conditions?.[reason] || "새 근거 확인"}`));
    });
    box.append(list, node("p", `실패 기록 저장: ${report.data_store_status} · 원문 접근 점검 ${number(report.access_checked_urls)}개 URL · 완료된 HTTP 요청 ${number(report.http_requests_completed)}회`, "record-meta"));
    if (report.tracking_url) box.append(articleTitle({title: "문서별 실패 근거와 재개 조건 전체 기록", url: report.tracking_url}));
    box.append(node("p", `수집 저장 실패 이력: GitHub HTTP 403, 작업 요약 1MB 초과, 저장 후 객체 재조회 실패. 최신 수집 실행: ${report.collector_latest?.status || "미확인"} · Pages 배포 확인: ${report.deployment?.status || "미확인"}.`, "data-note"));
    return box;
  }
  async function loadResolution() {
    try {
      const response = await fetch("./queue-resolution-report.json", {cache: "no-store"});
      if (!response.ok) return;
      const value = await response.json();
      if (value.version !== "bct-queue-resolution-v1") return;
      queueResolution = value;
      if (["system", "tracking"].includes(route())) render();
    } catch { /* Other existing live records remain independently readable. */ }
  }
  const targetRows = () => view.targets(tracking, verified);
  const detailHref = row => `#detail/${encodeURIComponent(row.id)}`;
  const link = (text, href, className = "text-link") => { const el = node("a", text, className); el.href = href; return el; };
  const statusPill = value => pill(view.status(value)[0], value.toLowerCase());
  const hypothesisField = value => ({target:"TARGET",specification:"규격",region:"지역",supply_pool:"공급 풀",period:"필요 기간",basis:"수급 비교 기준",
    "gate.change":"변화 확인","gate.remaining_demand":"잔여 수요","gate.matched_scope":"동일 범위 비교","gate.future_period":"미래 필요 시점",
    "gate.qualified_supply":"적격 공급","gate.relief_reviewed":"완화 근거 검토","gate.supply_gap":"공급공백 비교"}[value] || value);
  const hypothesisStatus = row => `${row.status}${row.reviewRequired === true ? " · 검토 필요" : ""}`;
  const detectedDate = value => !value || Number.isNaN(new Date(value).getTime()) ? "UNKNOWN" : `${new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(value))} KST`;
  function hypothesisPanel() {
    const box = panel("자동 생성 가설 초안", "저장된 후보 가설입니다. S1 / S2 / S3는 검토 단계이며 병목 확정이나 선행탐지 성능 통과를 뜻하지 않습니다.");
    box.id = "hypothesis-drafts";
    if (candidatesError) {
      box.append(node("p", futureCandidates ? "최신 가설을 읽지 못했습니다. 마지막으로 읽은 기록입니다." : "가설 기록을 읽지 못했습니다.", "data-note"));
      const retry = node("button", "다시 확인", "filter"); retry.type = "button"; retry.addEventListener("click", loadTracking); box.append(retry);
    }
    if (!futureCandidates) { if (!candidatesError) box.append(empty("가설 기록 확인 중", "저장된 후보 파일을 불러옵니다.")); return box; }
    const rows = view.hypotheses(futureCandidates), named = rows.filter(row => row.named), unnamed = rows.filter(row => !row.named);
    box.append(node("p", `자동 생성 가설 초안 ${number(named.length)}건 · TARGET 이름 특정 · 전체 ${number(rows.length)}건 · TARGET UNKNOWN ${number(unnamed.length)}건`, "record-meta"));
    box.append(node("p", ["S1", "S2", "S3"].map(stage => `${stage} ${number(named.filter(row => row.stage === stage).length)}건`).join(" · "), "record-meta"));
    function listing(items) {
      return table(["TARGET", "S1 / S2 / S3", "상태", "필요 시점", "최초 탐지일", "상세보기"], items, row => {
        const button = node("button", "상세보기", "filter"); button.type = "button";
        button.setAttribute("aria-label", `${row.name} 가설 상세보기`); button.addEventListener("click", () => showHypothesis(row));
        return [row.name, pill(row.stage, "neutral"), hypothesisStatus(row), row.period, detectedDate(row.firstDetected), button];
      });
    }
    box.append(named.length ? listing(named) : empty("이름이 특정된 가설 없음", "TARGET UNKNOWN 기록은 아래에 보존되어 있습니다."));
    if (unnamed.length) box.append(folding(`TARGET UNKNOWN ${number(unnamed.length)}건`, "이름이 아직 특정되지 않은 저장 초안", node("div", null, "detail-body")));
    // Build the larger unclassified list only when the existing disclosure opens.
    const disclosure = box.children[box.children.length - 1];
    if (unnamed.length) disclosure.addEventListener("toggle", () => {
      const body = disclosure.children[1]; if (disclosure.open && !body.children.length) body.append(listing(unnamed));
    });
    return box;
  }
  function showHypothesis(row) {
    document.getElementById("dialog-title").textContent = `${row.name} · ${row.stage}`;
    const body = document.getElementById("dialog-content"); body.replaceChildren();
    body.append(table(["확인 항목", "저장된 내용"], [
      ["TARGET", row.name], ["S1 / S2 / S3", row.stage], ["상태", hypothesisStatus(row)],
      ["필요 시점", row.period], ["최초 탐지일", detectedDate(row.firstDetected)],
      ["공개 선행성", row.current.public_classification || "UNKNOWN"],
      ["실제 발생", row.current.outcome?.actual_occurred || "UNKNOWN"]], entry => entry));
    body.append(node("h3", "미래 공급공백 가설"), node("p", row.text, "verdict-text"));
    for (const [role, label] of [["DEMAND", "수요 근거"], ["SUPPLY", "공급 근거"], ["CHANGE", "변화 근거"], ["RELIEF", "완화 근거"]]) {
      const refs = row.evidence.filter(ref => ref.role === role);
      if (!refs.length && !["DEMAND", "SUPPLY"].includes(role)) continue;
      body.append(node("h3", label));
      body.append(refs.length ? table(["원문·문서", "저장된 근거", "본문 버전 / 위치"], refs, ref => [
        articleTitle({title: ref.title, url: view.url(ref.url)}),
        `${ref.target || "UNKNOWN"} · 수량 ${ref.quantity ?? "UNKNOWN"}${ref.unit && ref.unit.toUpperCase() !== "UNKNOWN" ? " " + ref.unit : ""} · 필요일 ${ref.need_date || "UNKNOWN"} · 공급일 ${ref.available_date || "UNKNOWN"} · ${ref.actual_statement === true ? "실제 진술" : ref.actual_statement === false ? "조건·전망 진술" : "진술 유형 UNKNOWN"}`,
        `${ref.body_sha256 || "UNKNOWN"} · 문자 ${ref.locator?.start ?? "UNKNOWN"}–${ref.locator?.end ?? "UNKNOWN"}`
      ]) : node("p", "UNKNOWN · 저장된 근거 없음", "data-note"));
    }
    body.append(node("h3", "UNKNOWN 항목"), node("p", `미확인: ${row.unknown.map(hypothesisField).join(" · ") || "별도 미확인 항목 미기록"}`));
    if (row.draft.refutation) body.append(node("h3", "반박 조건"), node("p", row.draft.refutation));
    if (row.draft.next_material?.length) body.append(node("h3", "다음 확인 자료"), node("p", row.draft.next_material.map(hypothesisField).join(" · ")));
    document.getElementById("family-dialog").showModal();
  }
  function sourceLinks(sources) {
    const wrap = node("div", null, "source-links");
    sources.forEach(source => {
      const raw = typeof source === "string" ? source : source.url, safe = view.url(raw);
      if (!safe) return;
      wrap.append(articleTitle({title: typeof source === "object" && source.label ? source.label : new URL(safe).hostname, url: safe}));
    });
    return wrap.children.length ? wrap : node("span", "원문 연결 미기록", "muted");
  }
  function dataNote(box) {
    if (!tracking) box.append(node("p", trackingError ? "최신 추적 자료를 읽지 못해 초기 확인 자료만 표시합니다. 최신 상태와 다를 수 있습니다." : "최신 추적 자료 확인 중입니다. 초기 확인 자료가 먼저 표시될 수 있습니다.", "data-note"));
    else if (trackingError) box.append(node("p", "최신 자료를 읽지 못했습니다. 마지막으로 읽은 추적 기록을 표시합니다.", "data-note"));
    box.append(node("p", `판단 기록 ${tracking ? date(tracking.updated_at) + " KST" : verified?.as_of || "확인 중"} · 원문 수는 연결된 고유 URL 수입니다.`, "record-meta"));
  }
  function researchStats(rows) {
    const metrics = node("div", null, "research-stats");
    for (const key of ["FUTURE", "EMERGING", "OBSERVE", "CURRENT"]) {
      const count = rows.filter(row => row.status === key).length;
      const card = link("", "#ranking", `stat stat-${key.toLowerCase()}`);
      card.addEventListener("click",()=>{states.ranking.filter=key;states.ranking.query="";if(route()==="ranking")render();});
      const notes={FUTURE:"미래 공급 제약 근거",EMERGING:"부족량·시점 확인 필요",OBSERVE:"공급 부족 미확인",CURRENT:"이미 발생한 부족"};
      card.append(node("span", view.status(key)[0]), node("strong", tracking ? number(count) : "—"), node("small", tracking ? notes[key] : "최신 분류 확인 중"));
      metrics.append(card);
    }
    return metrics;
  }
  const readableStatus = value => ({
    FUTURE: "미래 병목 후보",
    EMERGING: "가능성 높아지는 중",
    REVIEW_LEAD: "조사 대상",
    OBSERVE: "관찰 중",
    UNRESOLVED: "자료 부족",
    CURRENT: "이미 발생"
  }[value] || view.status(value)[0]);

  function objectiveDashboard() {
    const rows = targetRows();
    const box = node("section", null, "objective-board");

    const head = node("div", null, "objective-head");
    const copy = node("div");
    copy.append(node("span", "BCT의 한 가지 목표", "objective-kicker"),
      node("h2", "병목 뉴스가 나오기 전에 먼저 잡는다"),
      node("p", "여러 독립적인 선행 신호를 합쳐, 앞으로 수요가 공급을 추월할 TARGET을 미리 후보로 등록하는 것이 목적입니다."));
    const badge = node("div", null, "objective-badge");
    badge.append(node("strong", "선행탐지"), node("span", "뉴스 확인보다 후보 등록이 먼저여야 성공"));
    head.append(copy, badge);
    box.append(head);

    const flow = node("div", null, "objective-flow");
    [
      ["01", "수요가 늘어날 조짐", "주문·투자계획·제품계획·예약"],
      ["02", "공급이 못 따라올 조짐", "생산량·납기·고객인증·생산확대"],
      ["03", "미래병목 후보 등록", "명시적 병목 뉴스가 나오기 전"],
      ["04", "나중에 실제 확인", "후보일 → 공개확인일 선행일수 측정"]
    ].forEach(([num,title,note], index) => {
      const step = node("div", null, "objective-step");
      step.append(node("span", num, "objective-step-num"), node("strong", title), node("small", note));
      flow.append(step);
      if(index < 3) flow.append(node("span", "→", "objective-arrow"));
    });
    box.append(flow);

    const prospective = futureCandidates?.prospective || futureCandidates?.summary?.prospective || null;
    const health = node("div", null, "objective-health");
    const healthCopy = node("div");
    healthCopy.append(node("span", "현재 목표 달성 상태", "objective-kicker"));
    if (prospective) {
      const open = prospective.open_candidates ?? prospective.open ?? prospective.live_candidates;
      const success = prospective.success ?? prospective.success_count;
      const missed = prospective.missed ?? prospective.missed_count;
      healthCopy.append(node("h3", "LIVE 선행탐지 성적표가 연결되어 있습니다."),
        node("p", "후보 생성 시각과 공개 확인 시각을 비교한 기록만 성과로 봅니다."));
      const metrics = node("div", null, "objective-mini-metrics");
      [["공개 확인 전 후보", open], ["선행탐지 성공", success], ["늦게 잡은 후보", missed]].forEach(([label,value]) => metrics.append(metric(label, value, "선행탐지 기록")));
      health.append(healthCopy, metrics);
    } else {
      health.classList.add("needs-link");
      healthCopy.append(node("h3", "선행탐지 성적표는 아직 이 화면 데이터와 연결되지 않았습니다."),
        node("p", "실제 후보를 처음 기록한 시각과 공개 병목 확인 시각 데이터가 아직 이 화면에 연결되지 않았습니다. 그래서 이 화면만 보고 ‘미리 잡았다’고 표시하지 않습니다."));
      const mark = node("div", null, "health-mark");
      mark.append(node("strong", "확인 불가"), node("span", "성과 데이터 연결 필요"));
      health.append(healthCopy, mark);
    }
    box.append(health);

    const counts = node("div", null, "objective-counts");
    const future = rows.filter(row => row.status === "FUTURE").length;
    const watching = rows.filter(row => ["REVIEW_LEAD","EMERGING","OBSERVE","UNRESOLVED"].includes(row.status)).length;
    const current = rows.filter(row => row.status === "CURRENT").length;
    const drafts = futureCandidates ? view.hypotheses(futureCandidates).filter(row => row.named).length : null;
    [
      ["미래 병목으로 보는 대상", future, "저장된 판단 기준"],
      ["관찰·자료보충 중", watching, "아직 부족 확정 전"],
      ["이미 발생한 대상", current, "미래 후보와 분리해서 봄"],
      ["저장된 가설 초안", drafts, "성과가 아니라 검토 재료"]
    ].forEach(([label,value,note]) => counts.append(metric(label,value,note)));
    box.append(counts);
    return box;
  }

  function focusTargetsPanel() {
    const rows = targetRows();
    const box = panel("지금 무엇을 보고 있나", "후보가 되기 전이라도 수요·공급 신호가 쌓이는 TARGET을 쉬운 말로 봅니다.");
    const candidates = rows.filter(row => row.status !== "CURRENT").slice(0, 8);
    if (!candidates.length) {
      box.append(empty(trackingLoading ? "TARGET 확인 중" : "관찰 중인 TARGET 없음", "자료가 없을 때 임의로 후보를 만들지 않습니다."));
      return box;
    }
    const grid = node("div", null, "simple-target-grid");
    candidates.forEach(row => {
      const card = node("article", null, "simple-target-card");
      const top = node("div", null, "simple-target-top");
      top.append(pill(readableStatus(row.status), row.status.toLowerCase()), node("span", row.sector, "simple-sector"));
      card.append(top, node("h3", row.name));
      card.append(node("p", view.clean(row.latest.reason) || "왜 관찰하는지 아직 기록되지 않았습니다.", "simple-reason"));

      const demand = view.field(row.target, ["demand_evidence","demand","comparison_inputs.demand.basis"], row.baseline);
      const supply = view.field(row.target, ["constraint_evidence","constraint","comparison_inputs.supply.basis"], row.baseline);
      const need = view.field(row.target, ["demand_timing"], row.baseline);
      const available = view.field(row.target, ["supply_timing","relief_timing"], row.baseline);
      const facts = node("div", null, "simple-facts");
      [["수요 쪽 근거", demand.value], ["공급 쪽 근거", supply.value], ["필요 시점", need.value], ["공급 가능 시점", available.value]].forEach(([label,value]) => {
        const item = node("div", null, "simple-fact");
        item.append(node("span", label), node("strong", view.clean(value) || "자료 미확보"));
        facts.append(item);
      });
      card.append(facts);

      const blockers = row.latest.supply_gap?.blockers || row.baseline?.unresolved || [];
      const missing = row.audit?.decisive_missing || blockers[0] || row.latest.next_check || "다음 확인 자료가 아직 기록되지 않았습니다.";
      const missingBox = node("div", null, "simple-missing");
      missingBox.append(node("span", "지금 부족한 것"), node("strong", view.clean(missing)));
      card.append(missingBox, link("상세 근거 보기", detailHref(row), "simple-detail-link"));
      grid.append(card);
    });
    box.append(grid);
    const late = rows.filter(row => row.status === "CURRENT");
    if (late.length) {
      const lateBox = node("div", null, "late-strip");
      lateBox.append(node("strong", "이미 발생한 병목은 따로 봅니다."));
      lateBox.append(node("span", late.map(row => row.name).join(" · ")));
      lateBox.append(link("상태 변화에서 보기", "#situation"));
      box.append(lateBox);
    }
    return box;
  }

  function rankingPanel(key = "ranking") {
    const all = targetRows(), state = states[key];
    const box = panel(key === "review" ? "추가 근거가 필요한 TARGET" : "전체 추적 TARGET", key === "review" ? "왜 아직 후보가 아닌지와 다음에 필요한 자료를 확인합니다." : "기술적인 단계명보다 현재 판단과 근거를 먼저 보여줍니다.");
    if (key === "ranking") {
      const basis=node("details",null,"ranking-basis");basis.append(node("summary","목록을 보는 법"),node("p","미래 병목 후보 → 가능성 높아지는 중 → 관찰·자료 부족 → 이미 발생 순서입니다. 이것은 병목 강도 점수나 투자 순위가 아닙니다."));box.append(basis);
    }
    dataNote(box);
    if (key === "ranking") box.append(link(futureCandidates ? `새 가설 초안 ${number(view.hypotheses(futureCandidates).filter(row => row.named).length)}건 · 검증 중에서 보기` : "새 가설 초안 · 검증 중에서 보기", "#review"));
    const bar = node("div", null, "toolbar"), filters = node("div", null, "filters");
    const list = node("div", null, "rank-list"), count = node("p", null, "record-meta");
    const buttons = [];
    const filterKeys = key === "review" ? ["전체", "REVIEW_LEAD", "OBSERVE", "EMERGING", "UNRESOLVED"] : ["전체", "FUTURE", "EMERGING", "REVIEW_LEAD", "OBSERVE", "CURRENT"];
    for (const value of filterKeys) {
      const button = node("button", value === "전체" ? "전체" : view.status(value)[0], "filter"); button.type = "button";
      button.setAttribute("aria-pressed", String(state.filter === value));
      button.addEventListener("click", () => {state.filter = value; draw();}); filters.append(button); buttons.push([button,value]);
    }
    const search = node("input", null, "search"); search.type = "search"; search.placeholder = "대상·섹터·기업 검색";
    search.setAttribute("aria-label", "병목 대상 검색"); search.value = state.query;
    search.addEventListener("input", () => {state.query = search.value; draw();});
    bar.append(filters, search); box.append(bar, count, list);
    function draw() {
      const rows = all.filter(row => (key !== "review" || ["REVIEW_LEAD", "OBSERVE", "EMERGING", "UNRESOLVED"].includes(row.status)) && (state.filter === "전체" || state.filter === row.status) && matches(row, state));
      buttons.forEach(([button,value]) => button.setAttribute("aria-pressed", String(state.filter === value)));
      count.textContent = `${number(rows.length)}개 대상 · 필터 후에도 전체 표시 순서를 유지합니다.`;
      list.replaceChildren();
      if (!rows.length) {list.append(empty(all.length ? "검색 결과가 없습니다" : "추적 기록 확인 중", all.length ? "검색어 또는 분류를 바꿔 주세요." : "자료를 읽지 못했을 때 0건으로 확정하지 않습니다."));return;}
      const headings = node("div", null, "rank-heading"); ["표시 순서", "섹터 · 세부 병목 대상", "최신 판단의 핵심", "판단 상태"].forEach(text => headings.append(node("span", text))); list.append(headings);
      for (const row of rows) {
        const article = node("article", null, "rank-row");
        const rank = link(String(all.indexOf(row)+1).padStart(2,"0"), detailHref(row), "rank-number"); rank.setAttribute("aria-label", `${all.indexOf(row)+1}번 ${row.name} 상세`);
        const identity = node("div", null, "rank-identity"); identity.append(link(row.sector, detailHref(row), "sector-link"), link(row.name, detailHref(row), "target-link"));
        const evidence=["FUTURE","EMERGING"].includes(row.status)?view.field(row.target,["constraint_evidence","constraint"],row.baseline):null;
        const summary = node("div", null, "rank-summary"); summary.append(node("p", view.clean(key === "review" && row.audit?.decisive_missing ? row.audit.decisive_missing : evidence?.on ? evidence.value : row.latest.reason) || "판단 사유 미기록", "clamp-text"));
        const meta = node("div", null, "row-meta"); meta.append(node("span", `원문 ${row.sources.length}개`), node("span", `검토 ${row.latest.reviewed_on || "미기록"}`));
        if(evidence?.on && evidence.on!==row.latest.reviewed_on)meta.append(node("span",`근거 ${evidence.on}`));
        if (row.priority) meta.append(node("span", `다음 조사 ${row.priority}순위`, "priority")); summary.append(meta);
        const status = node("div", null, "rank-status"); status.append(statusPill(row.status), link("상세·근거", detailHref(row)));
        article.append(rank, identity, summary, status); list.append(article);
      }
    }
    draw(); return box;
  }
  function folding(title, description, child, open = false) {
    const section = node("details", null, "detail-section"); section.open = open;
    const summary = node("summary"); summary.append(node("span", title), node("small", description || "")); section.append(summary, child);return section;
  }
  function sourceTable(row) {
    return table(["원문·문서", "발행일 / 확인 위치", "연결된 검토일", "자료 범위"], row.sources, source => [
      sourceDocument(source),
      [source.published || "발행일 미기록", source.locator || "본문 위치 미기록"].join(" · "),
      source.reviewed || "미기록", source.baseline ? "초기 확인 자료" : "추적 기록에 연결된 원문"
    ]);
  }
  function sourceDocument(source) {
    const cell=node("div",null,"cell-stacked");cell.append(articleTitle({title:source.label,url:source.url}));
    const saved=view.documents(futureCandidates).find(doc=>view.url(doc.url)===source.url);
    if(saved)cell.append(node("span",saved.title,"source-document"));
    else if(source.label===new URL(source.url).hostname){
      const parts=new URL(source.url).pathname.split("/").filter(Boolean);
      const title=parts.at(-1)==="default.aspx"?parts.at(-2):parts.at(-1);
      cell.append(node("span",`URL 문서명: ${(title||"제목 미기록").replaceAll("-"," ")}`,"source-document"));
    }
    return cell;
  }
  function detailPanel() {
    let id; try {id = decodeURIComponent(location.hash.slice(1).split("/").slice(1).join("/"));} catch {id = "";}
    const row = targetRows().find(item => item.id === id), box = node("div", null, "detail-view");
    box.append(link("전체 병목 순위로 돌아가기", "#ranking", "back-link"));
    if (!row) {box.append(empty(trackingLoading ? "대상 확인 중" : "이 대상을 찾을 수 없습니다", "전체 목록에서 대상을 다시 선택해 주세요."));return box;}
    document.getElementById("page-title").textContent = row.name;
    document.getElementById("page-subtitle").textContent = `${row.sector} · 최근 검토 ${row.latest.reviewed_on || "미기록"}`;
    const verdict = panel("현재 판단"); verdict.classList.add("verdict");
    verdict.append(statusPill(row.status), node("p", view.clean(row.latest.reason) || "판단 사유 미기록", "verdict-text"));
    verdict.append(node("p", view.status(row.status)[1], "muted")); dataNote(verdict); box.append(verdict);
    const fields = [
      ["무엇이 부족할 대상인가", {value: row.name, on: row.latest.reviewed_on}],
      ["수요 관련 근거", view.field(row.target, ["demand_evidence", "demand", "comparison_inputs.demand.basis"], row.baseline)],
      ["공급이 따라가기 어려운 근거", view.field(row.target, ["constraint_evidence", "constraint", "comparison_inputs.supply.basis"], row.baseline)],
      ["고객이 필요한 시점", view.field(row.target, ["demand_timing"], row.baseline)],
      ["공급 가능한 시점", view.field(row.target, ["supply_timing", "relief_timing"], row.baseline)],
      ["병목을 완화할 자료", view.field(row.target, ["relief_evidence", "relief_timing"], row.baseline)],
      ["공급망 단계", {value: row.target.stage || row.baseline?.stage || "자료 미확보", on: row.baseline?.as_of}],
      ["다음에 확인할 자료", view.field(row.target, ["next_check"])]];
    const core = panel("수요와 공급, 이렇게 비교했습니다", "최신 기록에서 항목별로 마지막 확인 내용을 표시합니다. 과거 자료의 날짜도 함께 표시합니다.");
    core.append(table(["확인 항목", "저장된 판단·근거", "기록일"], fields, ([label, value]) => [label, view.clean(value.value), value.on || "미기록"])); box.append(core);
    const missing = panel("판단에 남아 있는 빈칸");
    if (row.audit?.decisive_missing) missing.append(node("p", view.clean(row.audit.decisive_missing)));
    const blockers = row.latest.supply_gap?.blockers || row.baseline?.unresolved || [];
    missing.append(blockers.length ? table(["번호", "미확인 근거"], blockers, (value,i) => [i+1,view.clean(value)]) : node("p", view.clean(row.latest.outcome) || "별도 미확인 항목 미기록"));
    if (row.audit?.next_evidence) missing.append(node("p", `다음 자료: ${view.clean(row.audit.next_evidence)}`, "next-evidence"));
    box.append(missing);
    const comparison = row.latest.comparison_inputs, gap = row.latest.supply_gap;
    if (comparison) {
      const labels = {current:"현재 부족",shortage_window:"미래 부족 시점",demand:"같은 규격의 수요량",supply:"납품 가능한 적격 공급량",timing:"고객 필요일과 공급일",relief:"증설·대체 공급",market_awareness:"시장 선반영",economic_capture:"기업 이익 귀속"};
      const entries = Object.entries(comparison);
      const body = node("div", null, "detail-body");
      body.append(node("p", "계획·주문·생산능력은 같은 수치가 아닙니다. 미확인 값은 계산하지 않습니다.", "muted"));
      body.append(table(["비교 항목", "공개된 입력", "근거 설명", "연결 원문"], entries, ([key,value]) => [labels[key] || key,
        value.min != null || value.max != null ? `${value.min ?? "미확인"} ~ ${value.max ?? "미확인"} ${value.unit || ""}` : view.clean(value.state) || (value.review_complete === false ? "점검 미완료" : "정량·일정 미확인"),
        view.clean(value.basis) || "미기록", sourceLinks(value.evidence || [])]));
      if (gap) body.append(node("p", `수급 비교 판정: ${view.clean(gap.gap_status)} · 부족량 범위: ${gap.gap_range ? gap.gap_range.join(" ~ ") : "미확인"}`, "data-note"));
      box.append(folding("수급 비교 입력표", "수요량·적격 공급량·고객 필요일·반증 자료", body));
    }
    const companies = row.latest.companies || [], companyBody = node("div", null, "detail-body");
    companyBody.append(node("p", "공급망과 연결된 기업입니다. 제품별 이익 귀속·주가 선반영은 별도 확인이 필요합니다.", "muted"));
    companyBody.append(companies.length ? table(["기업", "공급망 역할", "연결 범위·근거", "사업 비중"], companies, company => [[company.ticker, company.name].filter(Boolean).join(" · ") || "상장 투자수단 미확인", ({DIRECT:"직접 공급",ENABLEMENT:"지원·장비·공정",UNRESOLVED:"연결 미확인"}[company.role] || company.role), view.clean(company.scope || company.evidence) || "범위 미기록", view.clean(company.business_share) || "미확인"]) : empty("최신 기업 연결 미기록", "회사명을 임의로 추가하지 않습니다."));
    if (row.baseline?.companies?.length) {
      companyBody.append(node("h3", `초기 확인 기업 · ${row.baseline.as_of}`));
      companyBody.append(table(["기업", "당시 역할", "당시 확인 범위", "공시·원문"], row.baseline.companies, company => [[company.ticker, company.name].filter(Boolean).join(" · ") || "상장 투자수단 미확인", ({DIRECT:"직접 공급",ENABLEMENT:"지원·장비·공정",UNRESOLVED:"연결 미확인"}[company.role] || company.role), view.clean(company.evidence), sourceLinks([{url:company.source}])]));
    }
    box.append(folding("관련 기업", `최신 기록 ${companies.length}개 · 초기 자료는 날짜를 구분`, companyBody));
    const sources = node("div", null, "detail-body"); sources.append(node("p", "원문 링크와 해당 검토 기록의 연결입니다. 문장별 인용 위치가 없으면 미기록으로 표시합니다. 전체 본문은 원문 사이트에서 확인합니다.", "muted"), sourceTable(row));
    box.append(folding("판단 근거 원문", `${row.sources.length}개 고유 URL · 발행일·본문 위치는 저장된 경우만 표시`, sources, true));
    const history = node("div", null, "detail-body"); history.append(table(["검토일", "당시 판단", "판단 이유", "다음 확인"], [...row.target.history].reverse(), entry => [entry.reviewed_on || "미기록",statusPill(entry.status || "UNRESOLVED"),view.clean(entry.reason) || "미기록",view.clean(entry.next_check) || "미기록"]));
    box.append(folding("판단 변경 이력", `${row.target.history.length}개 기록 · 과거 판단을 보존`, history));return box;
  }
  function evidencePanel() {
    const box = panel("대상별 근거 자료", "같은 원문이 여러 대상과 연결될 수 있습니다. 출처 수를 독립 사건 수로 해석하지 않습니다."); dataNote(box);
    for (const row of targetRows()) {
      const body = node("div", null, "detail-body"); body.append(link("이 대상의 판단·수급 비교 보기", detailHref(row)), sourceTable(row));
      box.append(folding(row.name, `${view.status(row.status)[0]} · 원문 ${row.sources.length}개`, body));
    }
    return box;
  }
  const bodyLabels = {FULL:"본문 확보",PARTIAL:"부분 본문",UNAVAILABLE:"본문 미확보"};
  const evidenceLabels = {DEMAND:"수요 변화",CONSTRAINT:"공급 제약",CAPACITY_LEAD_TIME:"생산능력·납기",TIMING:"시점",RELIEF:"완화 근거"};
  function showDocument(row) {
    document.getElementById("dialog-title").textContent=row.title;
    const body=document.getElementById("dialog-content");body.replaceChildren();
    body.append(node("p",`자동 추출 · ${bodyLabels[row.body_status] || row.body_status} · ${row.candidate ? "자동 후보" : "일반 수집 문서"}`,"record-meta"),articleTitle({title:"전체 원문 열기",url:row.url}));
    body.append(node("p","아래는 저장된 자동 발췌입니다. 병목 확정이나 전체 본문 판독 완료를 의미하지 않습니다.","data-note"));
    const excerpts=Object.entries(row.evidence).flatMap(([key,values])=>(Array.isArray(values)?values:[values]).map((value,i)=>({key,value,location:row.locations[key]?.[i]})));
    body.append(excerpts.length ? table(["근거 종류","저장된 원문 발췌","본문 위치"],excerpts,entry=>[evidenceLabels[entry.key]||entry.key,typeof entry.value==="string"?entry.value:JSON.stringify(entry.value),entry.location ? `문단 ${entry.location.paragraph ?? "미기록"} · 문장 ${entry.location.sentence ?? "미기록"}`:"위치 미기록"]) : empty("저장된 발췌 없음","원문에서 내용을 확인해 주세요."));
    body.append(node("p",`처리 확인 ${date(row.checked_at)} KST · 본문 버전 ${row.hash ? row.hash.slice(0,12) : "미확보"}`,"record-meta"));
    document.getElementById("family-dialog").showModal();
  }
  function documentsPanel() {
    const box=panel("수집 문서와 자동 발췌","문서명을 누르면 저장된 근거 발췌를 볼 수 있습니다. 자동 후보와 검토가 끝난 대상은 구분합니다.");
    if(!futureCandidates){box.append(empty(candidatesError?"수집 문서를 읽지 못했습니다":"수집 문서 확인 중","추적 대상의 원문 목록은 아래에서 확인할 수 있습니다."));return box;}
    if(candidatesError) box.append(node("p","최신 자료를 읽지 못했습니다. 아래는 마지막으로 읽은 문서 기록입니다.","data-note"));
    const rows=view.documents(futureCandidates),state=states.evidence,bar=node("div",null,"toolbar"),filters=node("div",null,"filters"),list=node("div"),controls=[];
    for(const value of ["전체","자동 후보","FULL","PARTIAL","UNAVAILABLE"]){const button=node("button",bodyLabels[value]||value,"filter");button.type="button";button.addEventListener("click",()=>{state.filter=value;state.page=1;draw();});filters.append(button);controls.push([button,value]);}
    const search=node("input",null,"search");search.type="search";search.placeholder="문서·출처·발췌 검색";search.setAttribute("aria-label","근거 문서 검색");search.value=state.query;search.addEventListener("input",()=>{state.query=search.value;state.page=1;draw();});
    bar.append(filters,search);box.append(bar,list);
    function draw(){const subset=rows.filter(row=>(state.filter==="전체"||(state.filter==="자동 후보"?row.candidate:row.body_status===state.filter))&&matches(row,state));
      controls.forEach(([button,value])=>button.setAttribute("aria-pressed",String(state.filter===value)));list.replaceChildren();
      const max=Math.max(1,Math.ceil(subset.length/15));state.page=Math.min(state.page,max);
      list.append(node("p",`${subset.length}개 문서 · ${state.page} / ${max}페이지`,"record-meta"));
      list.append(subset.length?table(["수집 문서","분류","본문 상태","출처","근거 종류"],subset.slice((state.page-1)*15,state.page*15),row=>{
        const button=node("button",row.title,"document-button");button.type="button";button.addEventListener("click",()=>showDocument(row));
        return [button,row.candidate?"자동 후보":"일반 문서",bodyLabels[row.body_status]||row.body_status,row.source||"미기록",Object.keys(row.evidence).map(key=>evidenceLabels[key]||key).join(" · ")||"발췌 없음"];
      }):empty("문서 검색 결과 없음","검색어나 분류를 바꿔 주세요."));
      const pager=node("div",null,"pager"),previous=node("button","이전"),next=node("button","다음");previous.disabled=state.page<=1;next.disabled=state.page>=max;
      previous.addEventListener("click",()=>{state.page--;draw();});next.addEventListener("click",()=>{state.page++;draw();});pager.append(previous,next);list.append(pager);
    }draw();return box;
  }
  function situationPanel() {
    const rows = targetRows(), box = panel("대상별 최신 상태", "현재 부족과 아직 발생하지 않은 미래 부족을 구분합니다. 일별 변화가 저장되지 않은 날은 추정하지 않습니다.");
    content.append(researchStats(rows));dataNote(box);
    box.append(table(["대상", "직전 → 최신 상태", "최신 검토일", "최신 판단 이유", "이력"], rows, row => {
      const past = row.target.history.at(-2), cell = node("div", null, "cell-stacked");
      if(past) cell.append(node("span", view.status(past.status)[0], "muted"));cell.append(statusPill(row.status));
      return [link(row.name,detailHref(row)),cell,row.latest.reviewed_on,view.clean(row.latest.reason),`${row.target.history.length}개 기록`];
    }));return box;
  }
  function insightsPanel() {
    const box = panel("확보된 자료로 판단하기", "시계열·노출도·예측 확률 대신, 현재 기록에서 확인할 수 있는 자료만 제공합니다."); dataNote(box);
    const specs = [["01", "수요와 고객 필요 시점", ["demand_evidence","demand","demand_timing"], "확정 주문과 계획을 구분하고, 고객별 필요량·필요일을 확인합니다."],
      ["02", "적격 공급과 납기",["supply_timing","constraint_evidence","constraint"],"생산능력 발표와 고객 인증·납품 가능한 물량을 구분합니다."],
      ["03", "증설·대체·완화 근거",["relief_evidence","relief_timing"],"부족이 풀릴 수 있는 증설, 대체 공급, 실제 생산 진전을 확인합니다."],
      ["04", "판단을 바꿀 다음 자료",["next_check"],"각 대상의 미확인 근거와 다음 확인 자료를 확인합니다."]];
    for (const [num,title,fields,note] of specs) {
      const body = node("div", null, "detail-body"); body.append(node("p",note,"muted"));
      body.append(table(["대상", "현재 확보한 내용", "기록일"],targetRows(),row => {const value=view.field(row.target,fields,row.baseline);return [link(row.name,detailHref(row)),value.value,value.on || "미기록"];}));
      box.append(folding(`${num} · ${title}`,note,body));
    }
    return box;
  }
  function collectionPanel() {
    const box = panel("수집·처리 상태", "여기는 시스템 작업량을 보는 곳입니다. 미래병목 후보 화면과 분리해서 표시합니다.");
    if (!futureCandidates) {box.append(empty(candidatesError ? "본문·검토 기록을 읽지 못했습니다" : "본문·검토 기록 확인 중", "수집 기사 기록과 별도로 불러옵니다."));return box;}
    if(candidatesError) box.append(node("p","최신 자료를 읽지 못했습니다. 아래는 마지막으로 읽은 집계입니다.","data-note"));
    const summary = futureCandidates.summary || {}, queue = summary.review_queue || {};
    const recovery = summary.recovery_queue;
    if (recovery?.counts) box.append(recoveryQueueMetrics(recovery));
    const metrics=node("div",null,"research-stats");
    [["처리 기록",summary.processed_total,"문서 처리 결과 수"],["자동으로 걸린 문서",queue.automatic_candidates,"미래병목 확정 수와 다름"],[recovery?.counts ? "보존된 판독 결과" : "판독 완료",queue.completed_documents,"부분 본문 판독을 포함한 과거 이력"],["검토 목록",queue.review_list_versions,"문서 버전 기준"]].forEach(([label,value,note])=>metrics.append(metric(label,value,note)));box.append(metrics);
    const statuses = {}; view.documents(futureCandidates).forEach(record=>{const s=record.body_status;statuses[s]=(statuses[s]||0)+1;});
    const labels={FULL:"본문 확보",PARTIAL:"부분 본문",UNAVAILABLE:"본문 미확보",UNAVAILABLE_THIS_RUN:"이번 실행 미확보"};
    if (!recovery?.counts) box.append(table(["본문 확보 상태", "저장된 결과 수"],Object.entries(statuses),([key,value])=>[labels[key]||key,value]));
    const counts=[["수집 범위 기사",summary.scope_articles],["이번 처리 문서",summary.processed_this_run],["이번 본문 확보",summary.body_ok_this_run],["1차 읽기 대기",queue.quick_pending],["원문 확보 대기",queue.material_pending],["정밀 검토 대기",queue.deep_pending],["보존된 문서 버전",queue.preserved_versions],["고정 검토 묶음",Object.keys(futureCandidates.bundles || {}).length]];
    box.append(node("p", "빠른 검토와 자료 확인 대기는 같은 문서가 겹칠 수 있어 합산하지 않습니다. 본문 캐시는 공개되지 않으며 원문 재접근 가능 여부는 달라질 수 있습니다.","data-note"),table(["확인 항목","저장된 수치"],counts,([label,value])=>[label,number(value)]));
    box.append(node("p",`수집 확인 ${date(summary.checked_at)} KST · 대기 집계 ${date(queue.computed_at)} KST · 최장 대기 ${queue.oldest_wait_hours == null ? "미기록" : queue.oldest_wait_hours+"시간"}`,"record-meta"));
    const observation=summary.operation_observation;
    if(observation) {
      const body=node("div",null,"detail-body");
      body.append(table(["운영 관찰 항목","현재 기록"],[["상태",({PENDING:"관찰 진행 중",HOLD:"점검 필요",PASS:"7일 관찰 통과"}[observation.status]||observation.status)],["실제 관찰 표본",number(observation.sample_count)],["관찰 시작",date(observation.start_at)+" KST"],["가장 빠른 종료 시점",date(observation.expected_earliest_finish)+" KST"],["최근 관찰",date(observation.last_observed_at)+" KST"]],row=>row));
      body.append(node("p","7일 관찰은 운영 상태 점검입니다. 미래 예측 정확도를 뜻하지 않습니다.","muted"));box.append(folding("7일 운영 관찰","실제 표본과 경과시간으로 확인",body,true));
    }
    return box;
  }
  function render() {
    const key = route(), [title, subtitle] = pages[key];
    document.getElementById("page-title").textContent = title;
    document.getElementById("page-subtitle").textContent = subtitle;
    document.querySelector(".eyebrow").textContent = key === "ranking" ? "EARLY BOTTLENECK DETECTION" : "BCT · EVIDENCE FIRST";
    document.querySelectorAll("nav a").forEach(link => {
      if (link.dataset.page === key || (key === "detail" && link.dataset.page === "ranking")) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    content.replaceChildren();
    if(key === "ranking") {content.append(objectiveDashboard(), focusTargetsPanel(), rankingPanel(key));return;}
    if(key === "review") {content.append(hypothesisPanel(), rankingPanel(key));return;}
    if(key === "detail") {content.append(detailPanel());return;}
    if(key === "evidence") {content.append(documentsPanel(),evidencePanel());return;}
    if(key === "situation") {content.append(situationPanel());return;}
    if(key === "insights") {content.append(insightsPanel());return;}
    if (key === "tracking") {
      const resolution = resolutionPanel(); if (resolution) content.append(resolution);
      content.append(hypothesisPanel(), futureQueuePanel(), trackingPanels());
      if (!tracking && !trackingLoading && !trackingError) loadTracking();
      return;
    }
    if (key === "future") { content.append(verifiedPanels()); return; }
    if (key === "system") { const resolution = resolutionPanel(); if (resolution) content.append(resolution); }
    if (!snapshot) {
      content.append(empty("데이터 확인 중", "저장된 snapshot을 불러옵니다."));
      if(key === "system") content.append(collectionPanel());
      if (key === "dashboard") content.append(verifiedPanels());
      return;
    }
    const overview = snapshot.overview;
    if (key === "dashboard") {
      const metrics = node("div", null, "metrics");
      metrics.append(metric("활성 RSS", overview.configured_rss, "현재 설정에 등록된 피드"), metric("최근 DB 추가 기사", overview.new_articles, "직전 DB 저장본 대비"), metric("누적 기사", overview.total_articles), metric("SIGNAL 기사", overview.signal_articles), metric("후보 Family", overview.candidate_families));
      const columns = node("div", null, "two-col");
      const collections = panel("최근 수집 내역", "최근 저장된 RSS 실행 기록 · KST"); collections.append(collectionList(snapshot.recent_collections));
      const summary = panel("수집 결과", "현재 DB에 기록된 최근 실행 기준");
      summary.append(metric("성공 / 실패", `${number(overview.successful_feeds)} / ${number(overview.failed_feeds)}`), metric("최근 수집 시각", date(overview.last_collection_at)), metric("AI 실행 방식", aiMode(overview.ai_mode)));
      columns.append(collections, summary); content.append(metrics, columns);
      const fixed = verifiedPanels(); fixed.classList.add("section-gap"); content.append(fixed);
    } else if (key === "sectors") {
      const box = panel("섹터별 SIGNAL 집계", snapshot.sector_note);
      const rows = [...snapshot.sector_rankings].sort((a, b) => b.pressure - a.pressure || b.source_count - a.source_count || (Date.parse(b.latest_at) || 0) - (Date.parse(a.latest_at) || 0) || a.relief - b.relief);
      box.append(table(["순위", "섹터", "압박", "완화", "후보군", "출처 수", "최근 신호 (KST)"], rows, (row, index) => [row.sector === "미분류" ? "집계" : index + 1, sectorDisplay(row.sector), row.pressure, row.relief, row.family_count, row.source_count, date(row.latest_at)]));
      if (!rows.length) box.append(empty("섹터 집계 결과 없음", snapshot.sector_note)); content.append(box);
    } else {
      let filters;
      if (key === "signals") filters = [["전체", snapshot.signal_articles.length], ...["PRESSURE", "RELIEF", "NEUTRAL"].map(label => [label, snapshot.signal_articles.filter(row => row.directions.includes(label)).length])];
      if (key === "ai") filters = [["전체", snapshot.ai_reviews.length], ...["OK", "ERROR"].map(label => [label, snapshot.ai_reviews.filter(row => row.status === label).length])];
      if (key === "families") filters = [["전체", snapshot.families.length], ...[...new Set(snapshot.families.map(row => row.status || "데이터 없음"))].map(label => [label, snapshot.families.filter(row => (row.status || "데이터 없음") === label).length])];
      if (key === "system") {
        content.append(collectionPanel());
        const queue=futureQueuePanel();queue.classList.add("section-gap");content.append(queue);
        const grid = node("div", null, "status-grid");
        grid.append(metric("DB 기사 수", overview.total_articles), metric("AI 실행 방식", aiMode(overview.ai_mode)), metric("최근 수집 시각", date(overview.last_collection_at)));
        content.append(grid); filters = [["전체", snapshot.feeds.length], ["성공", overview.successful_feeds], ["실패", overview.failed_feeds]];
      }
      const box = panel(); box.append(toolbar(key, filters, key === "signals" || key === "ai"));
      const body = node("div"); body.id = "table-body"; box.append(body); content.append(box); renderRows(key);
      if (key === "system") {
        const errors = panel("최근 오류"); errors.classList.add("section-gap");
        if (snapshot.recent_errors.length) snapshot.recent_errors.forEach(row => { const item = node("p", null, "key-value"); item.append(node("span", row.name, "muted"), node("span", row.last_error || row.status)); errors.append(item); });
        else errors.append(empty("저장된 최근 오류 없음", "현재 실행 기록 기준")); content.append(errors);
      }
    }
  }
  function validate(value) {
    if (!value || value.version !== 1 || !value.overview || !value.generated_at || !["sector_rankings", "signal_articles", "ai_reviews", "families", "feeds", "recent_collections", "recent_errors"].every(field => Array.isArray(value[field]))) throw new Error("Invalid snapshot");
    return value;
  }
  async function refresh() {
    if (researchRoutes.includes(route())) loadTracking();
    if (loading) return;
    loading = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(`./snapshot.json?t=${Date.now()}`, {cache: "no-store", signal: controller.signal});
      if (!response.ok) throw new Error("Snapshot unavailable");
      const next = validate(await response.json());
      const changed = !snapshot || next.generated_at !== snapshot.generated_at;
      snapshot = next;
      document.getElementById("snapshot-time").textContent = `갱신 ${date(snapshot.generated_at)} KST`;
      document.getElementById("notice").textContent = "";
      if (changed) render();
    } catch {
      document.getElementById("notice").textContent = snapshot ? "최신 snapshot을 읽지 못했습니다. 마지막으로 확인한 데이터를 표시합니다." : "snapshot을 읽지 못했습니다. 잠시 후 자동으로 다시 확인합니다.";
      if (!snapshot && !["future", ...researchRoutes].includes(route())) {
        content.replaceChildren(empty("데이터를 불러올 수 없음", "snapshot 연결 상태를 확인해 주세요."));
        if (route() === "dashboard") content.append(verifiedPanels());
      }
    } finally { clearTimeout(timeout); loading = false; }
  }
  document.getElementById("dialog-close").addEventListener("click", () => document.getElementById("family-dialog").close());
  window.addEventListener("hashchange", () => {render();if(researchRoutes.includes(route()) && !tracking && !trackingLoading && !trackingError) loadTracking();});
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  setInterval(() => { if (!document.hidden) refresh(); }, 300000);
  render(); refresh(); loadVerified(); loadResolution();
})();
