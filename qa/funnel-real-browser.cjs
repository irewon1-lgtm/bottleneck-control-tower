"use strict";
const { chromium }=require("playwright");
const assert=require("node:assert/strict"),path=require("node:path"),fs=require("node:fs");
const proof=path.join(process.cwd(),"qa","funnel-proof");fs.mkdirSync(proof,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true});const report={status:"NOT_RUN",screens:[]};
  try{
    for(const [label,width,height] of [["laptop-1536",1536,960],["laptop-1366",1366,768],["mobile-390",390,844]]){
      const ctx=await browser.newContext({viewport:{width,height}});
      const pg=await ctx.newPage();const errors=[];
      pg.on("pageerror",x=>errors.push(x.message));
      const http=await pg.goto("http://127.0.0.1:8771/",{waitUntil:"domcontentloaded",timeout:45000});
      assert.equal(http.status(),200);
      await pg.locator(".bct-source-backlog").waitFor({timeout:30000});
      const text=await pg.locator(".bct-source-backlog").innerText();
      assert(text.includes("10,604건"),label+" RSS pinned corpus");
      assert(text.includes("5,727건"),label+" FULL body snapshot");
      assert(text.includes("497건"),label+" unlinked articles");
      assert(text.includes("511건"),label+" historical rank");
      const count=await pg.locator(".bct-rank-table tbody tr").count();assert(count>0,label+" rank preserved");
      assert.deepEqual(errors,[]);
      const dims=await pg.evaluate(()=>({innerWidth,doc:document.documentElement.scrollWidth}));
      assert(dims.doc<=dims.innerWidth+4,label+" horizontal overflow "+JSON.stringify(dims));
      await pg.screenshot({path:path.join(proof,label+".png"),fullPage:false,animations:"disabled"});
      report.screens.push({label,width,height,oldEvidence:511,pinnedBodyFull:5727,pageErrors:errors.length});
      await ctx.close();
    }
    report.status="PASS_REAL_RSS_FUNNEL_BROWSER";
    console.log("BCT_REAL_RSS_FUNNEL_BROWSER_PASS "+JSON.stringify(report));
  }catch(e){report.status="FAIL";report.error=e.stack||String(e);console.error(e);process.exitCode=1;}
  finally{fs.writeFileSync(path.join(proof,"proof.json"),JSON.stringify(report,null,2));await browser.close();}
})();
