import assert from "node:assert/strict";
import fs from "node:fs";
import {pathToFileURL} from "node:url";
import path from "node:path";
const origin=(await import(pathToFileURL(path.resolve(process.argv[2])))).default;
const key="0".repeat(64); // Test credential only; never a deployment secret.
globalThis.Netlify={env:{get:()=>undefined}};
const request=(route,supplied)=>new Request("https://origin.test"+route,{headers:supplied?{"X-BCT-Origin-Secret":supplied}:{}});
for(const route of ["/","/app.js","/api/dashboard","/api/export","/api/evidence/"+"0".repeat(64)]){
  assert.equal((await origin(request(route))).status,403);
}
Netlify.env.get=()=>key;
for(const supplied of [undefined,"wrong","é".repeat(64)])assert.equal((await origin(request("/api/dashboard",supplied))).status,403);
assert.equal((await origin(request("/api/dashboard",key))).status,200);
assert.equal((await origin(request("/.env",key))).status,404);
const source=fs.readFileSync("deploy/v4-dashboard/sites-proxy.mjs","utf8");
const gateway=(await import("data:text/javascript;base64,"+Buffer.from(source).toString("base64"))).default;
assert.equal((await gateway.fetch(request("/"),{})).status,503);
assert.equal((await gateway.fetch(request("/.env"),{})).status,404);
assert.equal((await gateway.fetch(new Request("https://site.test/",{method:"POST"}),{})).status,405);
assert.equal((await gateway.fetch(request("/"),{BCT_ORIGIN_URL:"https://untrusted.test",BCT_ORIGIN_SECRET:key})).status,503);
const realFetch=globalThis.fetch;
globalThis.fetch=async(url,opts)=>{
  assert.equal(url,"https://bct-v4-ci-origin.netlify.app/api/dashboard");
  assert.equal(opts.redirect,"manual");
  assert.deepEqual(opts.headers,{"X-BCT-Origin-Secret":key});
  return new Response("redirect",{status:302,headers:{Location:"https://untrusted.test"}});
};
assert.equal((await gateway.fetch(request("/api/dashboard"),{BCT_ORIGIN_URL:"https://bct-v4-ci-origin.netlify.app",BCT_ORIGIN_SECRET:key})).status,502);
globalThis.fetch=realFetch;
console.log("PASS: fail-closed origin auth, Unicode/missing/wrong credential rejection, route allowlist, write rejection, destination pinning and credential-safe redirect rejection.");
