"use strict";
(() => {
  const pages = {
    dashboard: ["대시보드", "현재 수집 결과와 기존 SIGNAL·Family 현황"],
    sectors: ["섹터 랭킹", "PRESSURE → 출처 수 → 최근 신호 → RELIEF 순서"],
    signals: ["SIGNAL 기사", "기존 SIGNAL 결과 · 제목과 요약문 기준"],
    ai: ["AI 리뷰", "현재 DB에 저장된 AI 보조판독 결과"],
    families: ["후보 Family", "기존 Candidate Family 집계"],
    system: ["수집 현황 / 시스템 상태", "최근 RSS 실행 기록과 확인 가능한 상태"]
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
  let loading = false;
  const route = () => Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : "dashboard";
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
  function render() {
    const key = route(), [title, subtitle] = pages[key];
    document.getElementById("page-title").textContent = title;
    document.getElementById("page-subtitle").textContent = subtitle;
    document.querySelector(".eyebrow").textContent = `BCT / ${key.toUpperCase()}`;
    document.querySelectorAll("nav a").forEach(link => {
      if (link.dataset.page === key) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    content.replaceChildren();
    if (!snapshot) { content.append(empty("데이터 확인 중", "저장된 snapshot을 불러옵니다.")); return; }
    const overview = snapshot.overview;
    if (key === "dashboard") {
      const metrics = node("div", null, "metrics");
      metrics.append(metric("활성 RSS", overview.configured_rss, "현재 설정에 등록된 피드"), metric("최근 DB 추가 기사", overview.new_articles, "직전 DB 저장본 대비"), metric("누적 기사", overview.total_articles), metric("SIGNAL 기사", overview.signal_articles), metric("후보 Family", overview.candidate_families));
      const columns = node("div", null, "two-col");
      const collections = panel("최근 수집 내역", "최근 저장된 RSS 실행 기록 · KST"); collections.append(collectionList(snapshot.recent_collections));
      const summary = panel("수집 결과", "현재 DB에 기록된 최근 실행 기준");
      summary.append(metric("성공 / 실패", `${number(overview.successful_feeds)} / ${number(overview.failed_feeds)}`), metric("최근 수집 시각", date(overview.last_collection_at)), metric("AI 실행 방식", aiMode(overview.ai_mode)));
      columns.append(collections, summary); content.append(metrics, columns);
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
      if (!snapshot) content.replaceChildren(empty("데이터를 불러올 수 없음", "snapshot 연결 상태를 확인해 주세요."));
    } finally { clearTimeout(timeout); loading = false; }
  }
  document.getElementById("dialog-close").addEventListener("click", () => document.getElementById("family-dialog").close());
  window.addEventListener("hashchange", render);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  setInterval(() => { if (!document.hidden) refresh(); }, 300000);
  render(); refresh();
})();
