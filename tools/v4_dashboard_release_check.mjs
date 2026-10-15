import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const raw=fs.readFileSync(process.argv[2],"utf8");
const worker=(await import("data:text/javascript;base64,"+Buffer.from(raw).toString("base64"))).default;
const call=(path,method="GET")=>worker.fetch(new Request("https://local.test"+path,{method}));
const response=await call("/api/dashboard");
assert.equal(response.status,200);
const d=await response.json();
assert.equal(d.schema,"bct-v4-dashboard-1");
assert.equal(d.source.snapshot,true);
assert.equal(d.source.read_only,true);
assert.equal(d.records.length,d.counts.evidence);
assert.equal(d.counts.discovery+d.counts.reviewed+d.counts.structured,d.counts.evidence);
assert.match(d.source_db_sha256,/^[a-f0-9]{64}$/);
const recovery=d.research_updates?.cpu_recovery;
assert.ok(recovery,"Latest separate CPU research must be connected");
assert.equal(recovery.records.filter(r=>r.category==="cpu_product").length,recovery.summary.CPU_product_proposals_retained);
assert.equal(recovery.records.filter(r=>r.category==="reported").length,recovery.summary.new_source_reported_actual_event_reviews);
assert.equal(d.publication.source_branch,"codex/bct-v4-integration");
assert.equal(d.publication.status,"VERIFIED_READ_ONLY_SNAPSHOT");
for(const r of [...d.records,...recovery.records]){
  const e=await (await call("/api/evidence/"+r.id)).json();
  assert.equal(e.id,r.id);
  assert.equal(e.all_references_verified,true,"Unverified source reference: "+r.id);
}
const html=await (await call("/")).text();
for(const route of ["overview","candidates","evidence","automation"])assert.ok(html.includes(`data-nav="${route}"`));
assert.ok(html.includes('id="refresh"'));
const app=await (await call("/app.js")).text();
new vm.Script(app);
assert.ok(app.includes("고정 연구 자료"));
for(const path of ["/.env","/worker/index.js","/snapshot-manifest.json","/var/v4/cross-industry/ledger/v4.sqlite3"]){
  assert.equal((await call(path)).status,404);
}
for(const method of ["POST","PUT","DELETE"])assert.equal((await call("/api/dashboard",method)).status,405);
const exported=await call("/api/export");
assert.ok(exported.headers.get("content-disposition").includes("attachment"));
assert.deepEqual(await exported.json(),d);
console.log(`PASS: ${d.records.length+recovery.records.length} source-verified details across separate research scopes, assets, schema, immutable download and route boundaries.`);
