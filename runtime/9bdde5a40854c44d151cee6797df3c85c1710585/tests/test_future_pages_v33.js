"use strict";

// The existing Pages CI command also covers the new presentation adapter.
require("./test_readable_view_model.js");

// Run the real dependency-free Pages app with a small DOM, rather than checking
// source strings. Fixtures intentionally distinguish frozen and current bodies.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.dataset = {};
    this.className = "";
    this.ownText = "";
    this.classList = {add: (...names) => { this.className += " " + names.join(" "); }};
  }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(""); }
  append(...children) {
    for (const child of children) {
      if (!(child instanceof Element)) throw new Error("DOM fixture expects nodes");
      this.children.push(child);
    }
  }
  replaceChildren(...children) { this.children = []; this.ownText = ""; this.append(...children); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  showModal() { this.open = true; }
}

const clone = value => JSON.parse(JSON.stringify(value));
const walk = root => [root, ...root.children.flatMap(walk)];
const byClass = (root, name) => walk(root).filter(el => el.className.split(/\s+/).includes(name));
const headingPanel = (root, heading) => walk(root).find(el => el.tagName === "SECTION" && el.children.some(child => child.tagName === "H2" && child.textContent === heading));
const metricValues = root => Object.fromEntries(byClass(root, "metric").map(el => [el.children.find(child => child.tagName === "LABEL").textContent, el.children.find(child => child.tagName === "STRONG").textContent]));

function fixtures() {
  const results = Object.fromEntries(Array.from({length: 7}, (_, i) => ["doc" + i, {
    title: "검토 기사 " + i, url: "https://example.test/article/" + i,
    current_body_sha256: "new-body-" + i
  }]));
  return {
    tracking: {
      version: 1, updated_at: "2026-10-02T01:00:00Z",
      targets: [{id: "legacy", target: "기존 TARGET", history: [
        {status: "UNRESOLVED", reviewed_on: "2026-07-01", reason: "최초 가설"},
        {status: "S2", reviewed_on: "2026-10-01", reason: "기존 최근 판단", sources: ["https://example.test/evidence", "javascript:alert(1)"]}
      ]}]
    },
    candidates: {
      version: "future-candidates-v33", results,
      summary: {checked_at: "2026-10-02T01:00:00Z", review_queue: {
        computed_at: "2026-10-02T01:01:00Z", automatic_candidates: 27,
        quick_pending: 19, deep_pending: 3, candidate_data_wait: 4,
        material_pending: 8, completed_documents: 2, oldest_wait_hours: 72.5,
        event_count: 23,
        preview: Array.from({length: 7}, (_, i) => ({document_id: "doc" + i, url: results["doc" + i].url,
          body_status: i === 0 ? "PARTIAL" : "FULL", resume_at: i === 0 ? 123 : 0}))
      }},
      bundles: {fixed: {id: "fixed-review-bundle-1", documents: [
        {document_id: "doc0", body_sha256: "old-frozen-sha256-0123456789abcdef",
          reader_version: "reader-v33", start: 123, end: 900,
          url: "https://example.test/frozen-article"}
      ]}}
    }
  };
}

async function app(data, failures = {}, hash = "#tracking") {
  const ids = Object.fromEntries(["content", "page-title", "page-subtitle", "snapshot-time", "notice", "dialog-close", "family-dialog", "dialog-title", "dialog-content"].map(id => [id, new Element("div")]));
  const eyebrow = new Element("span");
  const nav = ["dashboard", "tracking", "future"].map(page => { const el = new Element("a"); el.dataset.page = page; return el; });
  const calls = [];
  let interval;
  const context = {
    Node: Element, URL, AbortController, Intl, Date, console,
    location: {hash},
    setTimeout: () => 1, clearTimeout: () => {},
    setInterval: fn => { interval = fn; return 1; },
    window: {addEventListener: () => {}},
    document: {hidden: false, createElement: tag => new Element(tag), getElementById: id => ids[id],
      querySelector: () => eyebrow, querySelectorAll: () => nav, addEventListener: () => {}},
    fetch: async (url, options) => {
      calls.push({url, options});
      const kind = url.includes("future-tracking.json") ? "tracking" : url.includes("future-candidates.json") ? "candidates" : "other";
      if (kind === "other") return {ok: false};
      if (failures[kind] === "network") throw new Error("fixture network failure");
      if (failures[kind] === "http") return {ok: false};
      return {ok: true, json: async () => clone(data[kind])};
    }
  };
  const source = fs.readFileSync(path.join(__dirname, "..", "docs", "app.js"), "utf8");
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "docs", "view-model.js"), "utf8"), context);
  vm.runInNewContext(source, context, {filename: "docs/app.js"});
  const settle = async () => { for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve)); };
  await settle();
  return {content: ids.content, ids, calls, nav, async refresh() { interval(); await settle(); }};
}

test("tracking renders existing TARGET history beside separate queue counts, capped preview and exact frozen ranges", async () => {
  const data = fixtures(), before = clone(data), page = await app(data);
  assert.equal(page.nav.find(el => el.dataset.page === "tracking").attributes["aria-current"], "page");
  const targets = byClass(page.content, "tracking-card");
  assert.equal(targets.length, 1);
  assert.match(targets[0].textContent, /기존 TARGET/);
  assert.match(targets[0].textContent, /2개 판단 이력/);
  assert.match(targets[0].textContent, /기존 최근 판단/);
  const queue = headingPanel(page.content, "처리 대기 현황");
  assert.deepEqual(metricValues(queue), {"자동으로 걸린 문서": "27", "1차 읽기 대기": "19", "정밀 검토 대기": "3", "추가 자료 대기": "4", "원문 확보 대기": "8", "판독 완료": "2"});
  assert.match(queue.textContent, /72\.5시간/);
  assert.match(queue.textContent, /사건 23개/);
  assert.match(queue.textContent, /수집 완료/);
  assert.match(queue.textContent, /대기 집계/);
  const preview = byClass(queue, "compact-list")[0];
  assert.equal(preview.children.length, 5);
  assert.match(preview.children[0].textContent, /PARTIAL · 이어서 123/);
  assert.match(queue.textContent, /fixed-review-bundle-1/);
  assert.match(queue.textContent, /old-frozen-s · 범위 123–900/);
  const links = walk(queue).filter(el => el.tagName === "A");
  assert(links.some(el => el.href === "https://example.test/frozen-article"));
  assert(links.some(el => el.href?.endsWith("/future-candidates.json")));
  assert(links.every(el => !el.href || (el.target === "_blank" && el.rel === "noopener noreferrer")));
  assert(walk(targets[0]).filter(el => el.tagName === "A").every(el => !el.href?.startsWith("javascript:")));
  assert(page.calls.filter(call => call.url.includes("future-")).every(call => call.options.cache === "no-store"));
  assert.deepEqual(data, before, "rendering links and opening bundles must not mutate review completion");
});

test("ranking starts with the objective, explains the early-detection flow, and does not pretend performance is connected", async () => {
  const data = fixtures();
  data.tracking.targets = [
    {id:"watch", target:"미래 TARGET", history:[{status:"OBSERVE", reviewed_on:"2026-10-02", reason:"수요는 늘지만 공급량이 아직 미확인", demand_timing:"2027", supply_timing:"UNKNOWN", next_check:"적격 공급량 확인", sources:["https://example.test/watch"]}]},
    {id:"late", target:"이미 발생 TARGET", history:[{status:"CURRENT", reviewed_on:"2026-10-02", reason:"현재 부족 공개 확인", sources:["https://example.test/late"]}]}
  ];
  const page = await app(data, {}, "#ranking");
  const objective = byClass(page.content, "objective-board")[0];
  assert(objective);
  assert.match(objective.textContent, /병목 뉴스가 나오기 전에 먼저 잡는다/);
  assert.match(objective.textContent, /수요가 늘어날 조짐/);
  assert.match(objective.textContent, /공급이 못 따라올 조짐/);
  assert.match(objective.textContent, /미래병목 후보 등록/);
  assert.match(objective.textContent, /확인 불가/);
  assert.match(objective.textContent, /실제 후보를 처음 기록한 시각과 공개 병목 확인 시각 데이터가 아직 이 화면에 연결되지 않았습니다/);
  const focus = headingPanel(page.content, "지금 무엇을 보고 있나");
  assert.match(focus.textContent, /미래 TARGET/);
  assert.match(focus.textContent, /지금 부족한 것/);
  assert.match(focus.textContent, /적격 공급량 확인/);
  assert.match(focus.textContent, /이미 발생한 병목은 따로 봅니다/);
});

test("generated hypothesis drafts render separately from verified TARGETs and retain UNKNOWN outcomes", async () => {
  const data = fixtures();
  data.candidates.hypotheses = {h1: {id: "h1", current: {stage: "S2", scope: {target: "novel optical sleeves"},
    draft: {text: "Demand and qualified supply need comparison", unconfirmed: ["supply pool"]},
    public_classification: "UNKNOWN", outcome: {actual_occurred: "UNKNOWN"}, evidence: []}}};
  const before = clone(data), page = await app(data), drafts = headingPanel(page.content, "자동 생성 가설 초안");
  assert.match(drafts.textContent, /자동 생성 가설 초안 1건/);
  assert.match(drafts.textContent, /novel optical sleeves/);
  assert.match(drafts.textContent, /S2 1건/);
  walk(drafts).find(el => el.tagName === "BUTTON" && el.textContent === "상세보기").listeners.click();
  assert.equal(page.ids["family-dialog"].open, true);
  assert.match(page.ids["dialog-title"].textContent, /novel optical sleeves · S2/);
  assert.match(page.ids["dialog-content"].textContent, /공개 선행성UNKNOWN.*실제 발생UNKNOWN/);
  assert.match(page.ids["dialog-content"].textContent, /미확인: supply pool/);
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  assert.deepEqual(data, before);
});

test("existing review menu shows named hypotheses with exact saved stages and details even without queue aggregation", async () => {
  const data = fixtures(); delete data.candidates.summary.review_queue;
  data.candidates.hypotheses = Object.fromEntries(["S1", "S2", "S3"].map((stage, i) => [`h${i}`, {
    first_detected_at: "2026-10-02T15:26:14Z", current: {stage, scope: {target: `TARGET ${i}`, period: {start:"2027-01-01",end:"2027-12-31"}},
      draft: {text:"Stored future supply gap hypothesis",unconfirmed:["supply_pool"]},
      outcome:{status:"OPEN",actual_occurred:"UNKNOWN"}, review_required:true,
      evidence:[{role:"DEMAND",document_id:"doc0",url:"https://example.test/demand",body_sha256:"frozen-demand",locator:{start:10,end:20},quantity:120,unit:"slots",need_date:"2027-01-01",actual_statement:true},
        {role:"SUPPLY",document_id:"doc1",url:"https://example.test/supply",body_sha256:"frozen-supply",locator:{start:30,end:40},quantity:100,unit:"slots",available_date:"2028-01-01",actual_statement:true}]}
  }]));
  data.candidates.hypotheses.unknown = {current:{stage:"S1",scope:{target:"UNKNOWN"}}};
  const before=clone(data), page=await app(data,{},"#review"), drafts=headingPanel(page.content,"자동 생성 가설 초안");
  assert.match(drafts.textContent,/자동 생성 가설 초안 3건.*전체 4건/);
  assert.match(drafts.textContent,/S1 1건 · S2 1건 · S3 1건/);
  const rows=walk(drafts).filter(el=>el.tagName==="TBODY")[0].children;
  assert.equal(rows.length,3);
  assert.match(rows[0].textContent,/TARGET 0S1OPEN · 검토 필요2027-01-01 ~ 2027-12-31/);
  assert.match(rows[0].textContent,/2026.*10.*03/);
  walk(rows[0]).find(el=>el.tagName==="BUTTON").listeners.click();
  const detail=page.ids["dialog-content"];
  for(const label of ["TARGET","S1 / S2 / S3","상태","필요 시점","미래 공급공백 가설","수요 근거","공급 근거","UNKNOWN 항목","최초 탐지일"]) assert(detail.textContent.includes(label),label);
  assert.match(detail.textContent,/Stored future supply gap hypothesis/);
  assert.match(detail.textContent,/수량 120 slots/); assert.match(detail.textContent,/수량 100 slots/);
  assert.match(detail.textContent,/frozen-demand · 문자 10–20/);
  assert(walk(detail).some(el=>el.href==="https://example.test/supply"));
  assert(headingPanel(page.content,"추가 근거가 필요한 TARGET"),"existing reviewed targets remain visible");
  assert.deepEqual(data,before);
});

test("hypothesis load failure never claims zero drafts and stale refresh keeps existing drafts", async () => {
  const data=fixtures(), failures={candidates:"http"}, page=await app(data,failures,"#review");
  assert.match(headingPanel(page.content,"자동 생성 가설 초안").textContent,/가설 기록을 읽지 못했습니다/);
  assert(!page.content.textContent.includes("자동 생성 가설 초안 0건"));
  delete failures.candidates;
  data.candidates.hypotheses={h:{current:{stage:"S1",scope:{target:"Saved target"}}}};
  await page.refresh(); failures.candidates="network"; await page.refresh();
  assert.match(headingPanel(page.content,"자동 생성 가설 초안").textContent,/마지막으로 읽은 기록.*Saved target/);
});

test("legacy candidate state without queue aggregation remains visibly pending, without invented zero completion", async () => {
  const data = fixtures(); delete data.candidates.summary.review_queue;
  const page = await app(data), queue = headingPanel(page.content, "처리 대기 현황");
  assert.match(queue.textContent, /검토 대기 집계 준비 중/);
  assert.equal(byClass(queue, "metric").length, 0);
  assert.equal(byClass(page.content, "tracking-card").length, 1);
});

test("failed refresh preserves last TARGET and queue but explicitly labels the queue as last read data", async () => {
  const data = fixtures(), failures = {}, page = await app(data, failures);
  failures.candidates = "network";
  await page.refresh();
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  assert.equal(metricValues(headingPanel(page.content, "처리 대기 현황"))["판독 완료"], "2");
  assert.match(headingPanel(page.content, "처리 대기 현황").textContent, /마지막|이전|최신.*읽지|대기.*오류/);
  assert(!page.content.textContent.includes("검토 완료"));
});

test("malformed null candidate results cannot replace last queue with fabricated completed counts", async () => {
  const data = fixtures(), page = await app(data);
  data.candidates.results = null;
  data.candidates.summary.review_queue.completed_documents = 100;
  await page.refresh();
  const queue = headingPanel(page.content, "처리 대기 현황");
  assert.equal(metricValues(queue)["판독 완료"], "2");
  assert.match(queue.textContent, /마지막|이전|최신.*읽지|대기.*오류/);
});

test("unavailable new candidate file does not suppress readable legacy TARGET tracking", async () => {
  const page = await app(fixtures(), {candidates: "http"});
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  const queue = headingPanel(page.content, "처리 대기 현황");
  assert.equal(byClass(queue, "metric").length, 0);
  assert.match(queue.textContent, /읽지|오류|불러올 수|연결/);
});

test("fresh TARGET records and stale queue have independent status and retained as-of times", async () => {
  const data = fixtures(), failures = {}, page = await app(data, failures);
  data.tracking.updated_at = "2026-10-02T02:00:00Z";
  data.tracking.targets[0].history.push({status: "S2", reviewed_on: "2026-10-02", reason: "새로 저장된 TARGET 판단"});
  failures.candidates = "http";
  await page.refresh();
  const targets = headingPanel(page.content, "지속 추적 기록");
  const queue = headingPanel(page.content, "처리 대기 현황");
  assert.match(targets.textContent, /새로 저장된 TARGET 판단/);
  assert.match(targets.textContent, /2026-10-02T02:00:00Z/);
  assert(!targets.textContent.includes("최신 추적 기록을 읽지 못했습니다"));
  assert.match(queue.textContent, /마지막으로 읽은 집계/);
  assert.match(queue.textContent, /수집 완료.*대기 집계/);
  assert.equal(metricValues(queue)["판독 완료"], "2");
});

test("fresh queue still renders when TARGET refresh fails, with stale TARGET warning only", async () => {
  const data = fixtures(), failures = {}, page = await app(data, failures);
  failures.tracking = "network";
  data.candidates.summary.review_queue.quick_pending = 18;
  data.candidates.summary.review_queue.computed_at = "2026-10-02T03:01:00Z";
  await page.refresh();
  const targets = headingPanel(page.content, "지속 추적 기록");
  const queue = headingPanel(page.content, "처리 대기 현황");
  assert.match(targets.textContent, /최신 추적 기록을 읽지 못했습니다/);
  assert.match(targets.textContent, /마지막으로 읽은 기록/);
  assert.match(targets.textContent, /기존 최근 판단/);
  assert.equal(metricValues(queue)["1차 읽기 대기"], "18");
  assert(!queue.textContent.includes("최신 대기 기록을 읽지 못했습니다"));
  assert.equal(metricValues(queue)["판독 완료"], "2");
});
