"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const view = require("../docs/view-model.js");

test("latest tracking judgment overrides frozen status, and current is distinct from future", () => {
  const tracking = {targets: [{id:"a",target:"A",history:[{status:"FUTURE"},{status:"CURRENT"}]},
    {id:"b",target:"B",history:[{status:"FUTURE"}]}]};
  const frozen = {as_of:"2026-09-30",items:[{id:"a",status:"FUTURE",sources:[]}]};
  const before = JSON.stringify(tracking), rows = view.targets(tracking,frozen);
  assert.deepEqual(rows.map(row=>row.id),["b","a"]);
  assert.equal(rows[1].status,"CURRENT");
  assert.equal(JSON.stringify(tracking),before);
});
test("only stored research priority breaks status ties; source count never ranks bottleneck intensity", () => {
  const tracking = {runs:[{evidence_gap_audit:[{id:"b",decisive_missing:"customer date"}],next_review_targets:["b"]}],
    targets:[{id:"a",target:"A",history:[{status:"OBSERVE",sources:["https://a.test/1","https://a.test/2"]}]},
    {id:"b",target:"B",history:[{status:"OBSERVE",sources:[]}]}]};
  const rows=view.targets(tracking,null);
  assert.deepEqual(rows.map(row=>row.id),["b","a"]);
  assert.equal(rows[0].audit.decisive_missing,"customer date");
  assert.equal(rows[0].priority,1);
  assert(!("score" in rows[0]));
});
test("historical fields retain their own date and unavailable figures stay unavailable", () => {
  const target={history:[{reviewed_on:"2026-09-01",demand:"confirmed order"},{reviewed_on:"2026-10-01",reason:"new review"}]};
  assert.deepEqual(view.field(target,["demand"]),{value:"confirmed order",on:"2026-09-01",sources:[]});
  assert.equal(view.field(target,["capacity"]).value,"자료 미확보");
});
test("evidence deduplicates safe URLs, keeps latest date and exact recorded paragraph metadata", () => {
  const target={history:[{reviewed_on:"old",sources:["https://a.test/1"]},
    {reviewed_on:"new",sources:["https://a.test/1","javascript:alert(1)"],comparison_inputs:{demand:{evidence:[{url:"https://a.test/1",published_on:"pub",locator:"p14"}]}}}]};
  const rows=view.evidence(target,{as_of:"base",sources:[{url:"https://b.test/2",label:"Official report"}]});
  assert.equal(rows.length,2);assert.equal(rows[0].reviewed,"new");
  assert.equal(rows[0].locator,"p14");assert.equal(rows[0].published,"pub");
  assert.equal(rows[1].baseline,true);assert.equal(view.url("data:text/html,x"),null);
});
test("empty current tracking stays empty rather than republishing frozen targets as current", () => {
  assert.equal(view.targets({targets:[]},{items:[{id:"a",sources:[]}]}).length,0);
});
test("legacy body and current version screening retain conservative availability and stored excerpts",()=>{
  const records={results:{a:{title:"A",body_status:"BODY_OK",body_sha256:"old",versions:{}},
    b:{title:"B",body_status:"UNAVAILABLE",current_body_sha256:"new",versions:{new:{body_status:"FULL",screening:{candidate:true,evidence:{DEMAND:["actual order"]}}}}}}};
  const before=JSON.stringify(records),docs=view.documents(records);
  assert.equal(docs[0].body_status,"PARTIAL");assert.equal(docs[1].body_status,"FULL");
  assert.equal(docs[1].candidate,true);assert.equal(docs[1].evidence.DEMAND[0],"actual order");
  assert.equal(JSON.stringify(records),before);
});
test("comparison input basis can be read without changing unknown numeric values",()=>{
  const target={history:[{reviewed_on:"2026-10-01",comparison_inputs:{demand:{min:null,max:null,basis:"confirmed 76 orders, timing unknown"}}}]};
  assert.equal(view.field(target,["comparison_inputs.demand.basis"]).value,"confirmed 76 orders, timing unknown");
  assert.equal(target.history[0].comparison_inputs.demand.min,null);
});
