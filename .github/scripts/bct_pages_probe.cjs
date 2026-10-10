"use strict";
// Real deployed Pages, real requests and real rendered DOM; no fixture routes.
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");

async function main() {
  const expected = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const output = process.argv[3];
  if (expected.url !== "https://irewon1-lgtm.github.io/bottleneck-control-tower/") {
    throw new Error("Unexpected deployment host");
  }
  const {chromium} = require(process.env.BCT_PLAYWRIGHT_MODULE || "playwright");
  const receipt = {status:"FAIL", actual_browser_execution:true,
    execution_id:crypto.randomUUID(), started_at:new Date().toISOString(),
    url:expected.url, browser_errors:[]};
  let browser;
  try {
    browser = await chromium.launch({headless:true});
    const context = await browser.newContext({serviceWorkers:"block"});
    const page = await context.newPage();
    page.on("pageerror", error => receipt.browser_errors.push(error.name));
    const candidateBase = "https://raw.githubusercontent.com/irewon1-lgtm/bottleneck-control-tower/future-bottleneck-data/";
    const observed = [];
    page.on("response", response => {
      if (response.url().startsWith(candidateBase+"future-candidates.json")) {
        observed.push(response.text().then(text => {
          const manifest = JSON.parse(text);
          return manifest.document_sha256 || hash(Buffer.from(text));
        }));
      }
    });
    const app = await context.request.get(expected.url+"app.js?check="+receipt.execution_id);
    if (!app.ok()) throw new Error("Deployed app unavailable");
    receipt.app_sha256 = hash(await app.body());
    if (receipt.app_sha256 !== expected.app_sha256) throw new Error("Deployed app is stale");
    await page.goto(expected.url+"?check="+receipt.execution_id+"#tracking", {waitUntil:"domcontentloaded"});
    await page.locator("[data-recovery-generation]").first().waitFor({timeout:45000});
    receipt.generation_run_id = await page.locator("[data-recovery-generation]").first().getAttribute("data-recovery-generation");
    receipt.counts = {};
    for (const state of ["PENDING","PROCESSING","COMPLETED","SOURCE_WAIT","EVIDENCE_WAIT","FAILED","RETRY_SCHEDULED"]) {
      const value = await page.locator(`[data-recovery-state="${state}"] strong`).first().innerText();
      if (!/^\d[\d,]*$/.test(value.trim())) throw new Error("Missing numeric queue count");
      receipt.counts[state] = Number(value.replaceAll(",", ""));
      if (receipt.counts[state] !== expected.counts[state]) throw new Error("Displayed queue count differs");
    }
    const sources = await Promise.all(observed);
    if (!sources.length || sources.some(value => value !== expected.source_document_sha256)) {
      throw new Error("Page did not consume the verified generation");
    }
    receipt.source_document_sha256 = expected.source_document_sha256;
    if (receipt.generation_run_id !== String(expected.generation_run_id) || receipt.browser_errors.length) {
      throw new Error("UI generation or browser execution failed");
    }
    await page.screenshot({path:path.join(path.dirname(output), "operating-pages.png"), fullPage:true});
    receipt.status = "PASS";
  } catch (error) {
    receipt.error_type = error.name;
    receipt.failure_code = error.message;
  } finally {
    if (browser) await browser.close();
    receipt.finished_at = new Date().toISOString();
    fs.writeFileSync(output, JSON.stringify(receipt, null, 2)+"\n");
  }
  if (receipt.status !== "PASS") process.exitCode = 1;
}
main().catch(error => { console.error(error.name); process.exitCode = 1; });
