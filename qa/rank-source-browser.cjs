const {chromium}=require("playwright");
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const out=path.join(process.cwd(),"qa/rank-source-proof");fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const report={status:"NOT_RUN",views:[]};
 try{
  for(const [label,width,height] of [["laptop-1536",1536,960],["laptop-1366",1366,768],["mobile-390",390,844]]){
   const context=await browser.newContext({viewport:{width,height}}),page=await context.newPage(),errors=[];
   page.on("pageerror",e=>errors.push(e.message));
   const response=await page.goto("http://127.0.0.1:8792/",{waitUntil:"domcontentloaded",timeout:45000});
   assert.equal(response.status(),200);
   await page.locator(".bct-rank-table tbody tr").first().waitFor({timeout:45000});
   const header=await page.locator(".bct-rank-table thead").innerText();
   assert(header.includes("RSS 원문검증")&&header.includes("RSS 검토대기"));
   const rows=await page.locator(".bct-rank-table tbody tr").count();
   assert(rows>0);
   const vals=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,window:innerWidth}));
   assert(vals.doc<=vals.window+4,label+" overflow: "+JSON.stringify(vals));
   assert.deepEqual(errors,[]);
   await page.screenshot({path:path.join(out,label+".png"),fullPage:false});
   report.views.push({label,width,height,rows,error_count:0});
   await context.close();
  }
  report.status="PASS_REAL_SOURCE_RANK_RESPONSIVE";
  console.log("BCT_SOURCE_RANK_REAL_BROWSER_PASS "+JSON.stringify(report));
 }catch(e){report.status="FAIL";report.error=e.stack||String(e);console.error(e);process.exitCode=1}
 finally{fs.writeFileSync(path.join(out,"result.json"),JSON.stringify(report,null,2));await browser.close()}
})();
