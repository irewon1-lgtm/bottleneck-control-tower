"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),crypto=require("node:crypto"),zlib=require("node:zlib");
const test=require("node:test");

test("display reader verifies bytes and rejects a stale generation",async()=>{
  const source=fs.readFileSync("docs/app.js","utf8"),start=source.indexOf("  async function readDisplayJSON("),end=source.indexOf("\n  async function ",start+10);
  const payload=JSON.stringify({results:{preserved:{}},summary:{review_queue:{completed_documents:184,failed_versions:3696}}});
  const envelope={format:"bct-sidecar-display-v1",source_document_sha256:"current",payload,payload_sha256:crypto.createHash("sha256").update(payload).digest("hex")};
  let expected="current",corrupt=false;
  const context={TextEncoder,crypto:crypto.webcrypto,Response,DecompressionStream,fetch:async url=>url.includes(".ui.json.gz")
    ?new Response(zlib.gzipSync(JSON.stringify({...envelope,payload_sha256:corrupt?"bad":envelope.payload_sha256})))
    :new Response(JSON.stringify({document_sha256:expected}))};
  vm.createContext(context);vm.runInContext(source.slice(start,end)+"\nglobalThis.readDisplay=readDisplayJSON;",context);
  const doc=await context.readDisplay("https://example.test/","future-candidates.json",{});
  assert.equal(doc.summary.review_queue.completed_documents,184);assert.equal(doc.summary.review_queue.failed_versions,3696);
  expected="later";await assert.rejects(context.readDisplay("https://example.test/","future-candidates.json",{}),/generation is stale/);
  expected="current";corrupt=true;await assert.rejects(context.readDisplay("https://example.test/","future-candidates.json",{}),/hash mismatch/);
});
