"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");
const SITE = "https://irewon1-lgtm.github.io/bottleneck-control-tower/";
const ROOT = process.env.GITHUB_WORKSPACE || path.resolve(__dirname, "..");
const OUTPUT = path.join(ROOT, "qa", "preview-output");
const toSha = body => crypto.createHash("sha256").update(body).digest("hex");
fs.mkdirSync(OUTPUT, {recursive:true});
let sourceHtml = fs.readFileSync(path.join(ROOT, "src/bct/v4/dashboard_web/index.html"), "utf8");
assert.equal(sourceHtml.split('href="/style.css"').length,2);
assert.equal(sourceHtml.split('src="/app.js"').length,2);
sourceHtml = sourceHtml.replace('href="/style.css"','href="./style.css"').replace('src="/app.js"','src="./app.js"');
const sourceCss = fs.readFileSync(path.join(ROOT, "src/bct/v4/dashboard_web/style.css"), "utf8");
const results = {kind:"PREVIEW_ONLY", source:"public-Pages-data-unchanged", status:"NOT_RUN", viewports:[]};

(async function(){
 const browser = await chromium.launch({headless:true});
 try {
  const context = await browser.newContext();
  const dataResp = await context.request.get(SITE+"api/dashboard.json", {timeout:45000});
  const metaResp = await context.request.get(SITE+"build-manifest.json", {timeout:45000});
  assert.equal(dataResp.status(),200, "public data no login");
  assert.equal(metaResp.status(),200, "public manifest no login");
  const bytes = await dataResp.body(), manifest = await metaResp.json(), data = JSON.parse(bytes.toString("utf8"));
  assert.equal(toSha(bytes),manifest.dashboard_sha256,"untouched public dataset");
  results.public_data_sha256 = toSha(bytes);
  results.published_code = manifest.code_commit;
  results.actual_records = data.records?.length;
  assert(results.actual_records>0, "source-linked data from real site");
  await context.close();
  for(const [name,width,height,expectColumns] of [
   ["laptop-1920",1920,1200,2],
   ["laptop-1536",1536,960,2],
   ["laptop-1366",1366,768,1],
   ["laptop-1250",1250,800,1],
   ["mobile-390",390,844,0]
  ]){
    const ctx = await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
    const page = await ctx.newPage();
    const errors = [],requestFailures=[];
    page.on("pageerror",e=>errors.push(e.message));
    page.on("requestfailed",r=>requestFailures.push(r.url()+":"+r.failure()?.errorText));
    await page.route(SITE,route=>route.fulfill({status:200,contentType:"text/html;charset=utf-8",body:sourceHtml}));
    await page.route(SITE+"style.css",route=>route.fulfill({status:200,contentType:"text/css;charset=utf-8",body:sourceCss}));
    const apiReady = page.waitForResponse(r => r.url()===SITE+"api/dashboard.json",{timeout:60000});
    const siteResponse = await page.goto(SITE,{waitUntil:"domcontentloaded",timeout:60000});
    assert.equal(siteResponse.status(),200);
    const uiDataResponse = await apiReady;
    assert.equal(toSha(await uiDataResponse.body()), results.public_data_sha256);
    await page.locator(".bct-rank-table tbody tr").first().waitFor({timeout:60000});
    assert.equal(await page.locator(".bct-process-item").count(),5,"five automation cards");
    assert((await page.locator(".bct-rank-table tbody tr").count())>0);
    const geometry = await page.evaluate(() => {
      const row=document.querySelector(".bct-rank-table tbody tr");
      const sector=row.querySelector(".bct-sector-name");
      const tableArea=document.querySelector(".bct-table-scroll");
      const columns=document.querySelector(".bct-rank-columns");
      const grid=getComputedStyle(columns).gridTemplateColumns.split(" ").filter(Boolean);
      const view=document.querySelector(".bct-view-button");
      const tgl=document.querySelector(".bct-reader-toggle");
      return {
        win:innerWidth,document:document.documentElement.scrollWidth,
        sectorPx:parseFloat(getComputedStyle(sector).fontSize),
        actionHeight:view.getBoundingClientRect().height,
        gridColumns:grid.length,
        tableScroll:tableArea.scrollWidth,tableWidth:tableArea.clientWidth,
        mobileCard:getComputedStyle(row).display==="grid",
        toggleVisible:getComputedStyle(tgl).display!=="none"
      };
    });
    assert(geometry.document<=geometry.win+4, name+" document horizontal overflow: "+JSON.stringify(geometry));
    assert(geometry.tableScroll<=geometry.tableWidth+4, name+" table horizontal overflow: "+JSON.stringify(geometry));
    if(expectColumns) {
       assert.equal(geometry.gridColumns,expectColumns,name+" responsive panel layout");
       assert(geometry.sectorPx>=18,name+" sector font should be readable");
       assert(geometry.actionHeight>=44,name+" detail button keyboard/mouse target");
       assert(geometry.toggleVisible,name+" enlarged text control must be visible");
    } else {
       assert(geometry.mobileCard,name+" preserve phone card layout");
       assert(!geometry.toggleVisible,name+" desktop-only toggle hidden on phone");
    }
    await page.screenshot({path:path.join(OUTPUT,name+"-default.png"),fullPage:true,animations:"disabled"});
    if(expectColumns){
       await page.locator("#bct-large-text").check();
       const larger = await page.locator(".bct-sector-name").first().evaluate(n=>parseFloat(getComputedStyle(n).fontSize));
       assert(larger>geometry.sectorPx, name+" extra large text actually increases the font");
       const largeGeometry=await page.evaluate(()=>({width:innerWidth,doc:document.documentElement.scrollWidth,tableWidth:document.querySelector(".bct-table-scroll").clientWidth,tableScroll:document.querySelector(".bct-table-scroll").scrollWidth}));
       assert(largeGeometry.doc<=largeGeometry.width+4,name+" extra-large mode document overflow");
       assert(largeGeometry.tableScroll<=largeGeometry.tableWidth+4,name+" extra-large mode rank table overflow");
       await page.screenshot({path:path.join(OUTPUT,name+"-large.png"),fullPage:true,animations:"disabled"});
    }
    await page.locator(".bct-view-button").first().click();
    const link=page.locator(".bct-evidence-open").first();
    await link.waitFor({timeout:20000});
    await link.click();
    await page.locator("dialog[open] #detail-title").waitFor({timeout:30000});
    assert((await page.locator("#detail-title").innerText()).length>0);
    await page.locator("#close-detail").click();
    await page.locator('[data-nav="automation"]').click();
    await page.locator(".process-card").first().waitFor({timeout:20000});
    assert.equal(await page.locator(".process-card").count(),3);
    assert.deepEqual(errors,[],name+" browser errors");
    assert.deepEqual(requestFailures,[],name+" failed network requests");
    results.viewports.push({name,width,height,layout:geometry,passed:true});
    await ctx.close();
  }
  results.status="PASS_PREVIEW_BROWSER";
  console.log("BCT_LAPTOP_PREVIEW_PASS "+JSON.stringify(results));
 } catch(e){
  results.status="FAIL";results.error=String(e.stack||e); console.error(e);process.exitCode=1;
 } finally{
  fs.writeFileSync(path.join(OUTPUT,"summary.json"),JSON.stringify(results,null,2));
  await browser.close();
 }
})();
