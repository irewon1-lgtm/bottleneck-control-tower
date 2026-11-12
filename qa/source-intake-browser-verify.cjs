"use strict";
const {chromium}=require("playwright");
const fs=require("fs"),path=require("path"),assert=require("node:assert/strict");
const dir=path.join(process.cwd(),"qa","source-intake-proof");
fs.mkdirSync(dir,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true});
  const result={status:"NOT_RUN",views:[]};
  try{
    for(const [label,width,height] of [["laptop-1536",1536,960],["laptop-1366",1366,768],["mobile-390",390,844]]){
      const context=await browser.newContext({viewport:{width,height}});
      const page=await context.newPage();
      const errs=[];
      page.on("pageerror",e=>errs.push(e.message));
      await page.goto("http://127.0.0.1:8767/",{waitUntil:"domcontentloaded",timeout:40000});
      await page.locator(".bct-source-intake").waitFor({timeout:40000});
      const text=await page.locator(".bct-source-intake").innerText();
      assert(text.includes("32건")&&text.includes("13건")&&text.includes("19건"),label+" exact original capture counts");
      assert(text.includes("원출처 확인 보류 16건"),label+" proof-grounded HOLD count");
      assert((await page.locator(".bct-rank-table tbody tr").count())>0);
      const x=await page.evaluate(()=>({body:document.documentElement.scrollWidth,width:innerWidth}));
      assert(x.body<=x.width+4,label+" no lateral page clipping");
      await page.screenshot({path:path.join(dir,label+".png"),fullPage:true,animations:"disabled"});
      await page.locator('[data-nav="automation"]').click();
      await page.getByText("최신 기사 원문 확보 실행 · 실제 저장 확인").waitFor({timeout:20000});
      const note=await page.getByText("원출처 확인 보류", {exact:false}).first().innerText();
      assert(note.includes("16건"));
      assert.deepEqual(errs,[]);
      result.views.push({label,width,height,counts:"32/13/19",horizontalOverflow:false,errors:0});
      await context.close();
    }
    result.status="PASS_BROWSER_REAL_RECEIPT";
    console.log("BCT_SOURCE_INTAKE_BROWSER_PASS "+JSON.stringify(result));
  }catch(e){
    result.status="FAIL";result.error=e.stack||String(e);
    console.error(e);process.exitCode=1;
  }finally{
    fs.writeFileSync(path.join(dir,"result.json"),JSON.stringify(result,null,2));
    await browser.close();
  }
})();
