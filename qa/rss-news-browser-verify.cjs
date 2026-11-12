"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const { chromium }=require("playwright");
const root=path.resolve(__dirname,"..");
const news=JSON.parse(fs.readFileSync(path.join(root,"var/v4/pages-site/api/rss-news.json")));
const manifest=JSON.parse(fs.readFileSync(path.join(root,"var/v4/pages-site/build-manifest.json")));
assert.equal(news.articles.length,news.visible_article_count);
assert(news.visible_article_count>10000);
assert.equal(news.new_article_count,news.articles.filter(r=>r.is_new).length);
assert.equal(news.source_run_id,manifest.rss_source_run_id);
fs.mkdirSync(path.join(root,"qa/rss-news-browser-proof"),{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const results={status:"NOT_RUN",kind:"PREVIEW_REAL_DATA_NO_DEPLOYMENT",run_id:news.source_run_id,
   count:news.visible_article_count,new:news.new_article_count,failed:news.feed_failed,views:[]};
 try{
  for(const [label,width,height] of [["desktop-1536",1536,960],["desktop-1366",1366,768],["phone-390",390,844]]){
   const ctx=await browser.newContext({viewport:{width,height}});
   const pg=await ctx.newPage();
   const errors=[]; const requests=[];
   pg.on("pageerror",x=>errors.push(x.message));
   pg.on("requestfailed",x=>requests.push(x.url()));
   const response=await pg.goto("http://127.0.0.1:8766/",{waitUntil:"domcontentloaded",timeout:40000});
   assert.equal(response.status(),200);
   await pg.locator(".bct-news-teaser").waitFor();
   const teaser=await pg.locator(".bct-news-teaser").innerText();
   assert(teaser.includes(news.new_article_count.toLocaleString("ko-KR")+"건"));
   assert(teaser.includes(news.visible_article_count.toLocaleString("ko-KR")+"건"));
   assert((await pg.locator(".bct-news-teaser-item").count())>0);
   await pg.locator('[data-nav="news"]').click();
   await pg.locator("#rss-news-results .bct-news-article").first().waitFor({timeout:45000});
   assert.equal(await pg.locator("#rss-news-results .bct-news-article").count(),24);
   const heading=await pg.locator(".bct-news-result-heading strong").innerText();
   assert(heading.includes(news.visible_article_count.toLocaleString("ko-KR")+"건"),label+" initial all-news total");
   assert((await pg.locator(".bct-news-article-foot").first().innerText()).includes("수집 "));
   assert((await pg.locator(".bct-news-source-link").count())>0);
   const before=await pg.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
   assert(before.document<=before.viewport+4,label+" horizontal overflow "+JSON.stringify(before));
   await pg.screenshot({path:path.join(root,"qa/rss-news-browser-proof",label+"-all.png"),fullPage:true,animations:"disabled"});
   await pg.locator(".bct-news-check input").check();
   const onlyNews=await pg.locator(".bct-news-result-heading strong").innerText();
   assert(onlyNews.includes(news.new_article_count.toLocaleString("ko-KR")+"건"),label+" exact new articles");
   const pgNext=pg.locator(".bct-news-pagination .button.primary");
   if(news.new_article_count>24){
     assert(await pgNext.isEnabled());
     await pgNext.click();
     assert((await pg.locator(".bct-news-result-heading span").innerText()).includes("2/"));
   }
   await pg.locator(".bct-news-check input").uncheck();
   await pg.locator(".bct-news-filter input[type=search]").fill("pharma");
   assert((await pg.locator(".bct-news-article").count())>0);
   await pg.screenshot({path:path.join(root,"qa/rss-news-browser-proof",label+"-search.png"),fullPage:true,animations:"disabled"});
   await pg.locator(".bct-news-filter input[type=search]").fill("");
   const categories=pg.locator(".bct-news-filter").filter({hasText:"출처 등록 분야(참고)"}).locator("select");
   const matching=news.articles.filter(a=>a.source_group==="바이오·의약").length;
   assert(matching>0,"Current canonical RSS should have biopharma feed domain sources");
   await categories.selectOption("바이오·의약");
   const categoryCount=await pg.locator(".bct-news-result-heading strong").innerText();
   assert(categoryCount.includes(matching.toLocaleString("ko-KR")+"건"),label+" source group match count");
   const displayed=await pg.locator(".bct-news-source-group").allInnerTexts();
   assert(displayed.length>0 && displayed.every(s=>s.includes("바이오·의약")),label+" visible source group tags");
   await categories.selectOption("");

   await pg.locator(".bct-feed-failures summary").click();
   assert.equal(await pg.locator(".bct-feed-error-line").count(),news.feed_failed);
   const after=await pg.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
   assert(after.document<=after.viewport+4,label+" after-interaction horizontal overflow "+JSON.stringify(after));
   assert.deepEqual(errors,[]);
   assert.deepEqual(requests,[]);
   results.views.push({label,width,height,initial:heading,newOnly:onlyNews,pageErrors:errors,overflow:false});
   await ctx.close();
  }
  results.status="PASS_REAL_DATA_BROWSER";
  console.log("BCT_RSS_NEWS_BROWSER_PASS "+JSON.stringify(results));
 }catch(e){
   results.status="FAIL";results.error=e.stack||String(e);
   console.error(e);process.exitCode=1;
 }finally{fs.writeFileSync(path.join(root,"qa/rss-news-browser-proof/summary.json"),JSON.stringify(results,null,2));await browser.close();}
})();
