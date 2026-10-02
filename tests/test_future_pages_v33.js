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

async function app(data, failures = {}) {
  const ids = Object.fromEntries(["content", "page-title", "page-subtitle", "snapshot-time", "notice", "dialog-close", "family-dialog", "dialog-title", "dialog-content"].map(id => [id, new Element("div")]));
  const eyebrow = new Element("span");
  const nav = ["dashboard", "tracking", "future"].map(page => { const el = new Element("a"); el.dataset.page = page; return el; });
  const calls = [];
  let interval;
  const context = {
    Node: Element, URL, AbortController, Intl, Date, console,
    location: {hash: "#tracking"},
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
  return {content: ids.content, calls, nav, async refresh() { interval(); await settle(); }};
}

test("tracking renders existing TARGET history beside separate queue counts, capped preview and exact frozen ranges", async () => {
  const data = fixtures(), before = clone(data), page = await app(data);
  assert.equal(page.nav.find(el => el.dataset.page === "tracking").attributes["aria-current"], "page");
  const targets = byClass(page.content, "tracking-card");
  assert.equal(targets.length, 1);
  assert.match(targets[0].textContent, /기존 TARGET/);
  assert.match(targets[0].textContent, /2개 판단 이력/);
  assert.match(targets[0].textContent, /기존 최근 판단/);
  const queue = headingPanel(page.content, "미래병목 검토 대기");
  assert.deepEqual(metricValues(queue), {"자동 후보": "27", "빠른검토 대기": "19", "심화 대기": "3", "후보 자료 대기": "4", "자료확인 대기": "8", "판독 완료": "2"});
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

test("generated hypothesis drafts render separately from verified TARGETs and retain UNKNOWN outcomes", async () => {
  const data = fixtures();
  data.candidates.hypotheses = {h1: {id: "h1", current: {stage: "S2", scope: {target: "novel optical sleeves"},
    draft: {text: "Demand and qualified supply need comparison", unconfirmed: ["supply pool"]},
    public_classification: "UNKNOWN", outcome: {actual_occurred: "UNKNOWN"}, evidence: []}}};
  const before = clone(data), page = await app(data), queue = headingPanel(page.content, "미래병목 검토 대기");
  assert.match(queue.textContent, /자동 생성 가설 초안 1건/);
  assert.match(queue.textContent, /novel optical sleeves · S2/);
  assert.match(queue.textContent, /공개 선행성 UNKNOWN · 실제 발생 UNKNOWN/);
  assert.match(queue.textContent, /미확인: supply pool/);
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  assert.deepEqual(data, before);
});

test("legacy candidate state without queue aggregation remains visibly pending, without invented zero completion", async () => {
  const data = fixtures(); delete data.candidates.summary.review_queue;
  const page = await app(data), queue = headingPanel(page.content, "미래병목 검토 대기");
  assert.match(queue.textContent, /검토 대기 집계 준비 중/);
  assert.equal(byClass(queue, "metric").length, 0);
  assert.equal(byClass(page.content, "tracking-card").length, 1);
});

test("failed refresh preserves last TARGET and queue but explicitly labels the queue as last read data", async () => {
  const data = fixtures(), failures = {}, page = await app(data, failures);
  failures.candidates = "network";
  await page.refresh();
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  assert.equal(metricValues(headingPanel(page.content, "미래병목 검토 대기"))["판독 완료"], "2");
  assert.match(headingPanel(page.content, "미래병목 검토 대기").textContent, /마지막|이전|최신.*읽지|대기.*오류/);
  assert(!page.content.textContent.includes("검토 완료"));
});

test("malformed null candidate results cannot replace last queue with fabricated completed counts", async () => {
  const data = fixtures(), page = await app(data);
  data.candidates.results = null;
  data.candidates.summary.review_queue.completed_documents = 100;
  await page.refresh();
  const queue = headingPanel(page.content, "미래병목 검토 대기");
  assert.equal(metricValues(queue)["판독 완료"], "2");
  assert.match(queue.textContent, /마지막|이전|최신.*읽지|대기.*오류/);
});

test("unavailable new candidate file does not suppress readable legacy TARGET tracking", async () => {
  const page = await app(fixtures(), {candidates: "http"});
  assert.equal(byClass(page.content, "tracking-card").length, 1);
  const queue = headingPanel(page.content, "미래병목 검토 대기");
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
  const queue = headingPanel(page.content, "미래병목 검토 대기");
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
  const queue = headingPanel(page.content, "미래병목 검토 대기");
  assert.match(targets.textContent, /최신 추적 기록을 읽지 못했습니다/);
  assert.match(targets.textContent, /마지막으로 읽은 기록/);
  assert.match(targets.textContent, /기존 최근 판단/);
  assert.equal(metricValues(queue)["빠른검토 대기"], "18");
  assert(!queue.textContent.includes("최신 대기 기록을 읽지 못했습니다"));
  assert.equal(metricValues(queue)["판독 완료"], "2");
});
