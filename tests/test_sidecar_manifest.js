"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const crypto = require("node:crypto");
const test = require("node:test");

test("Pages reads hash-verified legacy and content-addressed sidecars", async () => {
  const source = fs.readFileSync("docs/app.js", "utf8");
  const begin = source.indexOf("  async function readStoredJSON(");
  const end = source.indexOf("\n  async function ", begin + 10);
  assert.ok(begin >= 0 && end > begin);
  const raw = JSON.stringify({format: "bct-json-shard-v1", items: [
    {field: "results", key: "preserved", value: {body_sha256: "keep"}}
  ]}) + "\n";
  const digest = crypto.createHash("sha256").update(raw).digest("hex");
  for (const version of [1, 2]) {
    const partPath = version === 1 ? "future-candidates.shards/generation/future-candidates.part-001.json"
      : `future-candidates.shards/by-sha256/${digest}.json`;
    const manifest = {format: `bct-sharded-sidecar-v${version}`, document_sha256: "generation",
      fields: [{name: "results", kind: "dict"}], shards: [{path: partPath, sha256: digest, item_count: 1}],
      item_counts: {results: 1}, total_item_count: 1};
    let corrupt = false;
    const context = {TextEncoder, crypto: crypto.webcrypto, fetch: async url =>
      url.includes("future-candidates.json?") ? {ok: true, json: async () => manifest}
        : {ok: url.endsWith(partPath), text: async () => corrupt ? raw + " " : raw}};
    vm.createContext(context);
    vm.runInContext(source.slice(begin, end) + "\nglobalThis.reader = readStoredJSON;", context);
    const document = await context.reader("https://example.test/", "future-candidates.json", {});
    assert.equal(document.results.preserved.body_sha256, "keep");
    corrupt = true;
    await assert.rejects(context.reader("https://example.test/", "future-candidates.json", {}), /hash\/size/);
  }
});
