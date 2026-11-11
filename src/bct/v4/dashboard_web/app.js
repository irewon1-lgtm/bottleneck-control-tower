"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = String(text); if (cls) n.className = cls; return n; };
  const add = (n, ...children) => { n.append(...children.filter(Boolean)); return n; };
  const number = n => n == null ? "미확인" : Number(n).toLocaleString("ko-KR");
  const known = v => v != null && v !== "" && v !== "UNKNOWN";
  const value = v => known(v) ? String(v) : "아직 확인되지 않음";
  const date = v => {
    if (!known(v) || Number.isNaN(new Date(v).getTime())) return "시각 미확인";
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v.replaceAll("-", ".");
    return new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul", year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(v));
  };
  const badge = (text, tone="") => el("span", text, `badge ${tone}`);
  const btn = (text, action, cls="button") => { const n=el("button",text,cls); n.type="button"; if(action)n.addEventListener("click",action); return n; };
  const link = (text, href, cls="text-link") => { const n=el("a",text,cls); n.href=href; return n; };
  const external = (text, raw) => { try { const u=new URL(raw); if(!["http:","https:"].includes(u.protocol)||u.username||u.password)return null; const n=link(text,u.href);n.target="_blank";n.rel="noopener noreferrer";return n; } catch {return null;} };
  const displayStage = s => ({S1:"변화 신호 · S1",S2:"대상 구체화 · S2",S3:"공급 공백 근거 · S3"}[s]||"단계 판정 전");
  const detailButton = (r, text="근거 보기") => { const b=btn(text,()=>openDetail(r.id),"button small");b.setAttribute("aria-label",`${r.product} ${text}`);b.dataset.evidence=r.id;return b; };
  const panels = {
    overview:["한눈에 보기","자료가 얼마나 읽혔는지, 어떤 변화가 확인됐는지 살펴봅니다."],
    candidates:["미래 병목 후보","향후 12~36개월의 공급 부족 후보와 아직 검토 중인 변화를 구분합니다."],
    evidence:["판단 근거","저장된 원문과 공식 표를 열어, 판단이 어디에서 나왔는지 확인합니다."],
    automation:["자동화 현황","자동화 설정과 실제 실행 기록을 구분해 보여줍니다."]
  };
  let data=null, currentPage="overview", loadBusy=false, detailRequest=0;
  const state={candidates:{tab:"reviewed",query:"",industry:"",role:"",page:1},evidence:{source:"base",category:"",query:"",industry:"",role:"",page:1}};
  const content=$("content");
  function notify(text, tone=""){ $("notice").replaceChildren(text ? el("div",text,`notice ${tone}`) : document.createTextNode("")); }
  async function request(path){const r=await fetch(path,{cache:"no-store"});const body=await r.json();if(!r.ok)throw Error(body.error||"자료를 불러오지 못했습니다.");return body;}
  async function load(){
    if(loadBusy)return;loadBusy=true;$("refresh").disabled=true;
    try{data=await request("/api/dashboard");data.loaded_at=new Date().toISOString();render();notify(data.publication?`저장된 연구 자료 · 화면 배포 ${date(data.publication.last_sync_at)} · ${data.publication.status_label}. 새로 읽기는 수집·분석을 실행하지 않습니다.`:data.source.snapshot?"검증된 연구 백업을 보고 있습니다. 현재 수집기의 실시간 상태를 뜻하지 않습니다.":"");}
    catch(e){notify(`${e.message}${data?" 마지막으로 읽은 자료를 표시하고 있습니다.":""}`,"error");if(!data){content.replaceChildren(empty("연구 자료를 읽지 못했습니다","데이터 연결을 복구한 뒤 다시 읽을 수 있습니다.",btn("다시 읽기",load)));}}
    finally{loadBusy=false;$("refresh").disabled=false;}
  }
  function empty(title,text,action){return add(el("div",null,"empty"),el("div","◎","empty-icon"),el("h2",title),el("p",text),action);}
  function panel(title,caption,action){const n=el("section",null,"panel");if(title)n.append(add(el("div",null,"panel-head"),add(el("div"),el("h2",title),caption?el("p",caption):null),action));return n;}
  function stat(title,n,note,symbol,unit="건"){return add(el("div",null,"stat"),add(el("div",null,"stat-top"),el("span",title),el("span",symbol,"stat-symbol")),add(el("strong",number(n),"stat-value"),el("span",unit)),el("p",note,"stat-note"));}
  function head(){const [title,desc]=panels[currentPage];const g=data.operating_research?.generation;return add(el("div",null,"page-head"),add(el("div"),el("span","전 산업 탐색 · 연구 기록","eyebrow"),el("h1",title),el("p",desc)),add(el("div",null,"head-meta"),el("span","데이터 기준 · 한국 시간"),el("b",date(data.data_at)),el("span",`코드 버전 ${data.publication?.code_commit?.slice(0,12)||"로컬 미게시"}`),g?el("span",`저장 세대 ${g.ack_sequence} · ${g.private_commit.slice(0,12)}`):null,el("span",`화면 배포 ${date(data.snapshot_generated_at)}`),el("span",`화면에서 읽은 시각 ${date(data.loaded_at)}`)));}
  function recordsFor(page){const source=state[page]?.source;return page==="evidence"&&source&&source!=="base"?(data.research_updates?.cpu_recovery?.records||[]).filter(r=>r.category===source):data.records;}
  function recoverySummary(){const r=data.research_updates?.cpu_recovery;if(!r)return;const s=r.summary,p=panel(data.operating_research?"보존된 CPU 연구 결과":"최신 CPU 연구 결과",`별도 판독 범위 · ${date(r.at)} · 기존 110문서와 합산하지 않습니다.`);p.append(add(el("div",null,"stats-grid"),stat("이번 판독 문서",s.documents_processed,`처음 판독 ${number(s.first_CPU_documents)} · 기존 부분 판독 확대 ${number(s.previous_partial_document_expanded)}`,"◫"),stat("CPU 제품 표기 제안",s.CPU_product_proposals_retained,"중복·오분류 가능성을 보존 · 고유 TARGET 수 아님","◎"),stat("새 보도 내용 검토",s.new_source_reported_actual_event_reviews,"공식 1차 확인 전 · 후보 승격 없음","▤"),stat("공식 1차 검증 사건",s.new_official_primary_verified_events,`기존 엔진 최종 채택 ${number(s.strict_downstream_event_adoptions)} · 신규 S1/S2/S3 ${s.S1_S2_S3_change.join("/")}`,"✓")),el("p",`실제 CPU 판독 ${number(s.actually_CPU_read_characters)} / ${number(s.body_characters)}자 (${(100*s.actually_CPU_read_characters/s.body_characters).toFixed(2)}%). 미판독 ${number(s.unread_characters)}자는 공백·줄바꿈이며 내용 문자 미판독 ${number(s.unread_nonwhitespace_characters)}자입니다.`,"section-note"),el("p",`AI 도입 품질 ${s.AI_quality.startsWith("FAIL")?"FAIL":s.AI_quality} · 독립 평가 ${s.independent20.startsWith("BLOCKED")?"BLOCKED":s.independent20}. 기사 보도 검토를 공식 사건이나 미래 병목으로 바꾸지 않았습니다.`,"notice"),link("최신 CPU 제안·새 보도 근거 보기 →","#evidence"));content.append(p);}
  function coverage(){const c=data.coverage;const pct=c.body_characters>0?100*c.read_characters/c.body_characters:null;return {c,pct};}
  function render(){
    const route=location.hash.slice(1);currentPage=Object.hasOwn(panels,route)?route:"overview";
    document.querySelectorAll("[data-nav]").forEach(a=>{if(a.dataset.nav===currentPage)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
    document.title=`${panels[currentPage][0]} · BCT V4 연구실`;
    if(!data)return;
    content.replaceChildren(head());
    ({overview:overview,candidates:candidates,evidence:evidence,automation:automation}[currentPage])();
  }
  function overview(){
    const c=data.counts; const future=Object.values(c.future_candidates).reduce((a,b)=>a+b,0);
    const hero=el("section",null,"hero");
    add(hero,add(el("div"),badge("근거를 모으는 단계","green"),el("h2",future?"저장된 후보와 근거를 함께 확인하세요":"아직 미래 병목 후보로 확정된 대상은 없습니다"),el("p","수요·공급 변화가 있다는 것만으로 병목을 판단하지 않습니다. 같은 제품과 기간의 독립적인 근거를 연결하고, 공급을 늘릴 대안까지 확인합니다."),link("검토 중인 변화 살펴보기  →","#candidates")),add(el("div",null,"hero-number"),el("label","향후 12~36개월 후보"),el("strong",number(future)),el("small",data.operating_research?"과거 고정 연구 집계 · 신규 CPU 상태는 아래 별도 표시":"자료 부족은 ‘병목 없음’을 뜻하지 않습니다.")));
    hero.querySelector("strong").append(el("span","건"));content.append(hero);
    if(data.operating_research||data.collection_observation||data.workflow_observation)operatingSummary();
    content.append(add(el("div",null,"stats-grid"),stat(data.collection_observation?"과거 본문 확보 문서":"본문을 확보한 문서",c.body_nonempty,data.collection_observation?`고정 연구 수집 기준 ${date(data.historical_data_at)}`:"이번 수집 · 본문이 비어 있지 않은 문서","▤"),stat("기존 CPU 판독 범위",data.coverage.documents,"기존 동결 범위 · 최신 별도 연구는 아래 표시","◫"),stat("검토된 수요·공급 변화",c.reviewed,"과거 별도 AI 원문 검토 · 사람 검증 전","⌁"),stat(data.collection_observation?"과거 본문 확보 대기":"본문 확보 대기",c.pending,data.collection_observation?"과거 고정 수집 기록의 미시도 URL":"최근 수집 완료 기록의 미시도 URL","◷")));
    recoverySummary();
    const columns=el("div",null,"two-col");
    const signals=panel("근거가 있는 변화부터","과거 연구에서 검토된 사건 · 미래 병목 확정 아님",link("모두 보기 →","#candidates"));
    const choices=[];const seen=new Set();for(const r of data.records.filter(r=>r.category==="reviewed")){if(!seen.has(r.industry)){choices.push(r);seen.add(r.industry);}if(choices.length===4)break;}
    const list=el("div",null,"mini-list");for(const r of choices){const a=btn("↗",()=>openDetail(r.id),"icon-button");a.setAttribute("aria-label",`${r.product} 근거 열기`);add(list,add(el("div",null,"mini-row"),el("div",r.role.startsWith("DEMAND")?"↗":r.role==="RELIEF"?"↘":"⌁","mini-icon"),add(el("div"),el("b",r.product),el("p",`${r.industry} · ${r.role_label} · ${r.actuality}`)),a));}
    signals.append(list);columns.append(signals);
    const flow=panel(data.operating_research?"과거 자료 판독 범위":"자료는 어디까지 읽혔나요?",data.operating_research?`고정 연구 기준 ${date(data.historical_data_at)} · 신규 CPU 상태와 별도`:"이번 확보량과 전체 판독 범위를 나누어 봅니다.");
    const f=el("div",null,"flow");[[c.discovered_urls,"발견 URL"],[c.captured,"원본 확보"],[c.body_nonempty,"본문 있음"]].forEach(([n,t],i)=>{if(i)f.append(el("span","›","flow-arrow"));f.append(add(el("div",null,"flow-item"),el("strong",number(n)),el("span",t)));});flow.append(f);
    const {c:read,pct}=coverage();flow.append(add(el("div",null,"coverage-line"),el("span","평가한 본문 중 실제 판독 범위"),el("b",pct==null?"미확인":`${pct.toFixed(2)}%`)));
    const p=el("progress");p.max=read.body_characters||1;p.value=read.read_characters;p.setAttribute("aria-label","원문 문자 기준 실제 판독 범위");flow.append(add(el("div",null,"progress-track"),p));flow.append(el("p",`${number(read.read_characters)}자 / ${number(read.body_characters)}자 · 읽지 않은 구간은 판단하지 않았습니다.`,"caption"));flow.append(el("p",`전체 본문 ${number(c.body_status.FULL||0)}건 · 부분 본문 ${number(c.body_status.PARTIAL||0)}건 · 이용 불가 ${number(c.body_status.UNAVAILABLE||0)}건. 전체 본문 표기는 첨부·표 전체 판독을 보장하지 않습니다.`,"section-note"));columns.append(flow);content.append(columns);
    const sectors=panel("여러 산업을 동시에 탐색합니다","출처 분류 기준입니다. 관측하지 못한 산업은 병목이 없는 것으로 판단하지 않습니다.",link("수집 상태 →","#automation"));const grid=el("div",null,"sector-grid");
    for(const s of data.sectors)grid.append(add(el("div",null,"sector"),el("b",s.name),add(el("p"),el("em",`본문 ${number(s.bodies)}건`),document.createTextNode(` · 판독 ${number(s.read_documents)}건`))));sectors.append(grid,el("p","본문 수와 판독 수는 과거 고정 연구의 저장된 평가 범위입니다. 석유·가스·화학 등 자료 공백은 개별 보류됩니다.","section-note"));content.append(sectors);
  }
  function stageExplanation(){const g=el("div",null,"stage-explainer");for(const [s,t]of[["S1 · 변화 신호","수요 증가 또는 공급 감소·지연을 확인"],["S2 · 대상 구체화","제품·규격·지역·고객·공급 범위를 구체화"],["S3 · 공급 공백 근거","같은 기간의 적격 공급 부족 근거를 연결"]])g.append(add(el("div",null,"stage-box"),el("b",s),el("p",t)));return g;}
  function controls(page,withCategory=false){
    const s=state[page],box=el("div",null,"filters");
    const label=el("label",null,"filter search");label.append(el("span","제품·산업 찾기"));const input=el("input");input.type="search";input.placeholder="제품명이나 산업을 입력하세요";input.value=s.query;input.id=`${page}-search`;input.addEventListener("input",()=>{s.query=input.value;s.page=1;renderList(page);});label.append(input);box.append(label);
    function select(name,title,options){const lab=el("label",null,"filter");lab.append(el("span",title));const n=el("select");n.id=`${page}-${name}`;for(const [val,text]of options){const o=el("option",text);o.value=val;n.append(o);}n.value=s[name];n.addEventListener("change",()=>{s[name]=n.value;s.page=1;renderList(page);});lab.append(n);box.append(lab);}
    select("industry","산업",[["","모든 산업"],...[...new Set(recordsFor(page).map(r=>r.industry))].sort().map(x=>[x,x])]);
    if(withCategory)select("category","검토 상태",[["","모든 상태"],["reviewed","별도 원문 검토"],["discovery","제품 탐색 · 검토 대기"],["structured","공식 표의 변화"]]);
    select("role","수요·공급 역할",[["","모든 역할"],...[...new Map(recordsFor(page).map(r=>[r.role,r.role_label]))].sort((a,b)=>a[1].localeCompare(b[1],"ko"))]);
    box.append(btn("초기화",()=>{Object.assign(s,{query:"",industry:"",role:"",page:1});if(withCategory)s.category="";render();},"button"));return box;
  }
  function candidates(){
    content.append(stageExplanation());
    const s=state.candidates;const tabs=el("div",null,"tabs");tabs.setAttribute("role","tablist");tabs.setAttribute("aria-label","후보와 변화 구분");
    for(const [key,title,count]of[["reviewed","검토 중인 변화",data.counts.reviewed],["future","미래 병목 후보",Object.values(data.counts.future_candidates).reduce((a,b)=>a+b,0)]]){const b=btn(title,()=>{s.tab=key;s.page=1;render();},"tab");b.setAttribute("role","tab");b.setAttribute("aria-selected",String(s.tab===key));b.append(el("span",number(count),"count"));tabs.append(b);}content.append(tabs);
    if(s.tab==="future"){const total=Object.values(data.counts.future_candidates).reduce((a,b)=>a+b,0);content.append(empty(`저장된 평가 범위의 미래 병목 후보 ${number(total)}건`,total===0?"필요 시기와 같은 범위의 적격 공급을 확인한 후보가 아직 없습니다. 이 화면은 새 후보를 만들거나 단계를 올리지 않습니다.":"연구 보고서에 후보 집계가 있습니다. 개별 후보의 근거와 기간 연결 기록을 확인해야 상세 후보로 표시할 수 있습니다.",btn("검토 중인 변화 보기",()=>{s.tab="reviewed";render();},"button primary")));content.append(el("p",data.candidate_scope,"section-note"));return;}
    content.append(el("p",`저장된 검토 사건 ${number(data.counts.reviewed)}건 중 변화 신호(S1) 표기 ${number(data.counts.s1_signals)}건입니다. 별칭이 섞인 사건 기록이며 고유한 미래 병목 후보 수가 아닙니다.`,"notice"));
    content.append(controls("candidates"),el("div",null,"list-container"));content.lastChild.id="candidates-list";renderList("candidates");
  }
  function evidence(){
    const recovery=data.research_updates?.cpu_recovery;if(recovery){const tabs=el("div",null,"tabs");tabs.setAttribute("role","tablist");tabs.setAttribute("aria-label","근거 자료 범위");for(const [key,title,count]of[["base","전 산업 근거",data.counts.evidence],["cpu_product",data.operating_research?"보존된 CPU 제안":"최신 CPU 제안",recovery.summary.CPU_product_proposals_retained],["reported","새 보도 검토",recovery.summary.new_source_reported_actual_event_reviews]]){const b=btn(`${title} ${number(count)}`,()=>{Object.assign(state.evidence,{source:key,category:"",query:"",industry:"",role:"",page:1});render();},"tab");b.setAttribute("role","tab");b.setAttribute("aria-selected",String(state.evidence.source===key));tabs.append(b);}content.append(tabs,el("p","전 산업 근거·CPU 원문 표기 제안·공식 확인 전 보도 검토는 서로 다른 범위입니다. 합산해 후보나 고유 사건 수로 세지 않습니다.","section-note"));}
    content.append(add(el("div",null,"stats-grid"),stat("저장된 근거 기록",data.counts.evidence,"문서 수와 사건 수는 다릅니다","▤"),stat("별도 원문 검토",data.counts.reviewed,"AI 검토 기록 · 사람 검증 아님","✓"),stat("제품 탐색 결과",data.counts.discovery,"제품 정체와 사건 관계 확인 필요","◎"),stat("공식 표의 변화",data.counts.structured,"과거 보고 상태 · 공급 확정 아님","▦")));
    content.append(controls("evidence",state.evidence.source==="base"),el("div"));content.lastChild.id="evidence-list";renderList("evidence");
    content.append(add(el("div",null,"download-row"),add(el("div"),el("h3","현재 화면의 연결 자료 보관"),el("p","전체 목록과 집계를 자료 파일로 내려받습니다. 필터와 무관한 전체 연구 조회 결과입니다.")),link("연구 자료 내려받기 ↓","/api/export","button")));
  }
  function renderList(page){
    const s=state[page],root=$(`${page}-list`);if(!root)return;
    const q=s.query.trim().toLocaleLowerCase();const all=recordsFor(page).filter(r=>(page!=="candidates"||r.category==="reviewed")&&(!s.category||r.category===s.category)&&(!s.industry||r.industry===s.industry)&&(!s.role||r.role===s.role)&&(!q||`${r.product} ${r.industry}`.toLocaleLowerCase().includes(q)));
    const pages=Math.max(1,Math.ceil(all.length/12));s.page=Math.min(s.page,pages);const rows=all.slice((s.page-1)*12,s.page*12);
    root.replaceChildren(add(el("div",null,"list-summary"),add(el("span"),el("b",`${number(all.length)}건`),document.createTextNode("의 기록")),el("span",page==="candidates"?"예상 시기는 원문으로 확인된 경우만 표시":"인용 위치 검증과 의미 검증은 별개입니다")));
    if(!rows.length){root.append(empty("조건에 맞는 기록이 없습니다","검색어나 산업·역할 조건을 바꿔 보세요."));return;}
    if(page==="candidates"){
      const wrap=el("div",null,"panel table-panel"),table=el("table",null,"research-table");const tr=el("tr");["산업 · 제품","수요·공급 변화","예상 시기","검증 상태","근거"].forEach(t=>tr.append(el("th",t)));table.append(add(el("thead"),tr));const body=el("tbody");
      for(const r of rows){const tr=el("tr");const product=add(el("td",null,"product-cell"),el("span",r.product,"product-title"),el("span",r.industry,"product-meta"));const role=add(el("td"),el("span",r.role_label,"cell-main"),badge(r.actuality,r.actuality==="계획"?"amber":""));role.dataset.label="변화";const time=add(el("td"),el("span",r.period,"cell-main"),el("span",`공개 ${date(r.published_at)}`,"product-meta"));time.dataset.label="예상 시기";const status=add(el("td"),badge(displayStage(r.stage),r.stage==="S1"?"green":""),el("p","원문 AI 검토 · 사람 검증 전","product-meta"));status.dataset.label="검증 상태";tr.append(product,role,time,status,add(el("td"),detailButton(r)));body.append(tr);}table.append(body);wrap.append(table);root.append(wrap);
    }else{
      const grid=el("div",null,"evidence-grid");for(const r of rows){const card=el("article",null,"evidence-card");add(card,add(el("div",null,"card-meta"),badge({reviewed:"별도 원문 검토",structured:"공식 표의 변화",discovery:"제품 탐색 · 검토 대기",cpu_product:"CPU 제품 표기 · 의미 검증 전",reported:"보도 검토 · 공식 1차 확인 전"}[r.category],r.category==="reviewed"?"green":r.category==="structured"?"blue":"amber"),el("span",r.industry)),el("h3",r.product),el("p",`${r.role_label} · ${r.actuality}`),add(el("div",null,"card-bottom"),el("span",known(r.published_at)?`공개 ${date(r.published_at)}`:"공개일 확인 필요"),detailButton(r,"원문 대조")));grid.append(card);}root.append(grid);
    }
    if(pages>1){const p=el("div",null,"pagination");const prev=btn("← 이전",()=>{s.page--;renderList(page);});prev.disabled=s.page===1;const next=btn("다음 →",()=>{s.page++;renderList(page);});next.disabled=s.page===pages;p.append(prev,el("span",`${s.page} / ${pages} 페이지`),next);root.append(p);}
  }
  const stateLabel=s=>({UNREAD:"미판독",PARTIAL:"부분 판독",FAILED:"처리 실패",SOURCE_VERIFICATION_PENDING:"원문 검증 대기",GRAPH_CONTEXT_PENDING:"독립 근거 문맥 대기",READ_EVIDENCE_HOLD:"판독 후 근거 보류",NO_VALIDATED_EVENT:"검증된 사건 없음",RESEARCH_FORECAST_REVIEW:"연구 후보 검토",READ_COMPLETE:"판독 범위 완료"}[s]||s);
  function workflowLabel(row){if(!row)return "상태 미확인";return `${row.conclusion||row.status} · 실행 ${row.id}`;}
  function cpuWorkflowLabel(row){if(!row)return "작업 상태 미확인";return `판독 작업 ${row.processing_jobs?.research||"미확인"} · 저장 작업 ${row.processing_jobs?.publish||"미확인"}`;}
  function operatingSummary(){
    const r=data.operating_research,c=data.collection_observation,p=panel("현재 자동화 관측","수집 기록과 CPU 저장 세대는 각자의 실행 번호로 구분합니다.",link("처리·보류 상태 보기 →","#automation"));
    p.append(add(el("div",null,"stats-grid"),stat("최근 발견 URL",c?.counts.new_URLs,"마지막 수집 관측 · CPU 판독 수와 별도","▤"),stat("이번 저장 세대 신규 판독",r?.counts.new_CPU_windows,"실제 모델 판독 시도 창 · 검증 성공과 별도","◫","창"),stat("검증 성공 창",r?.counts.successful_new_CPU_windows,"실제 성공한 새 창만 집계","✓","창"),stat("미판독 대기 창",r?.counts.pending_windows,"저장된 CPU 대기열 기준","◷","창")),el("p",`최근 수집 ${date(c?.collection_started_at)} · 실제 판독 시도 ${date(r?.clocks.last_read_at)} · 영속 저장 ${date(r?.clocks.persisted_at)}. 과거 상세 연구 기준 ${date(data.historical_data_at)}는 별도 보존합니다.` ,"section-note"));content.append(p);
  }
  function operatingAutomation(){
    const r=data.operating_research,c=data.collection_observation,w=data.workflow_observation?.workflows||{},n=r?.counts,b=r?.last_read_batch;
    if(data.public_transport&&data.public_transport.pending_reason!=="NONE")content.append(el("p",`공개 요약 연결 확인 대기 · ${data.public_transport.pending_reason}. 확인된 저장 세대는 보존하며, 대기 중인 실행을 완료로 세지 않습니다.`,"notice"));
    const grid=el("div",null,"automation-grid");
    const review=r?Object.entries(r.analysis.states).map(([key,count])=>`${stateLabel(key)} ${number(count)}`).join(" · "):"영속 저장된 공개 연구 요약 대기";
    for(const [idx,title,status,description,last]of[
      ["01","자료 수집",workflowLabel(w.rss),c?`발견 URL ${number(c.counts.new_URLs)} · 시드 처리 결과 ${number(c.counts.new_seed_attempts)}건 · 신규 검증 문서 ${number(c.counts.new_verified_documents)}건. 시드 처리 수는 HTTP 요청 수가 아닙니다. 본문 HTTP 요청·대기 수는 아직 측정하지 않았습니다.`:"현재 형식의 수집 요약이 없습니다. 실행 상태만으로 본문 확보를 추정하지 않습니다.",c?.collection_started_at],
      ["02","CPU 판독",cpuWorkflowLabel(w.cpu),r?`이번 저장 세대: 판독 시도 문서 ${number(n.new_CPU_documents)} · 신규 창 ${number(n.new_CPU_windows)} · 검증 성공 ${number(n.successful_new_CPU_windows)} · 실제 판독 문자 ${number(n.new_CPU_characters)}. 완전 범위 분석 문서 ${number(n.complete_analyzed_new_CPU_documents)} · 분석 오류 ${number(n.analysis_runtime_failures)} · 미판독 대기 ${number(n.pending_windows)}창. 모델 판독은 의미 검토 완료를 뜻하지 않습니다.`:"새 CPU 저장 세대의 검증된 공개 요약을 기다립니다.",r?.clocks.last_read_at],
      ["03","근거·후보 검토",r?.analysis.status||"상태 미확인",`${review}. 독립 근거 쌍 ${number(n?.independent_pairs)}. S2/S3 또는 LIVE 승격은 별도 검증 전입니다.`,r?.clocks.persisted_at]])grid.append(add(el("section",null,"process-card"),el("span",`단계 ${idx}`,"process-index"),add(el("h2",title),badge(status,idx==="03"?"amber":"")),el("p",description),el("p",`${idx==="02"?"마지막 실제 판독 시도":idx==="03"?"저장 검증":"마지막 수집"} · ${date(last)}`,"process-last")));
    content.append(grid);
    if(w.cpu&&r&&w.cpu.id!==r.generation.producer_run_id)content.append(el("p",`최근 CPU 실행 ${w.cpu.id}와 공개 저장 실행 ${r.generation.producer_run_id}가 다릅니다. 최근 실행의 새 영속 저장·공개 연결은 확인 대기이며, 마지막 검증된 세대를 표시합니다.`,"notice"));
    if(c){const p=panel("최근 수집·본문 처리 관측",`수집 실행 ${c.RSS_run_id} / 시도 ${c.RSS_run_attempt} · 본문 처리 ${c.run_id} / 시도 ${c.run_attempt}`);p.append(el("p",`완료 ${date(c.completed_at)} · 원문 상태 ${c.source_integrity_state} · 미검증 보류 ${number(c.unverified_source_holds)}건`,"section-note"),el("p",Object.entries(c.counts.new_seed_statuses||{}).map(([k,v])=>`${k} ${number(v)}`).join(" · ")||"신규 시드 처리 결과 없음","section-note"));if(r&&c.RSS_run_id!==r.generation.RSS_run_id)p.append(el("p","이 수집 실행은 아래 CPU 저장 세대와 다릅니다. 새 자료의 CPU 처리 완료는 아직 연결되지 않았습니다.","notice"));content.append(p);}
    if(r){content.append(add(el("div",null,"stats-grid"),stat("보류된 입력",n.held_inputs,"원문·버전·이전 입력 공백을 개별 보류","!"),stat("실패 창",n.failed_windows,"성공한 창과 분리 보존","!","창"),stat("의미 검토 대기 창",n.review_pending_windows,"모델 판독 성공과 별도","◷","창"),stat("보존된 완료 창",n.preserved_windows,"기존 완료 기록을 포함한 저장 상태","▤","창")));
      const p=panel("영속 저장 세대와 판독 연결",`세대 ${r.generation.ack_sequence} · 원격 저장과 별도 프로세스의 8개 표 복구 검증 완료`);p.append(kv([["원래 저장 실행",`${r.generation.producer_run_id} / 시도 ${r.generation.producer_attempt}`],["CPU 입력 수집 / 본문",`${r.generation.RSS_run_id??"미확인"} / ${r.generation.acquisition_run_id??"미확인"}`],["마지막 실제 판독 실행",`${b.consumer_run_id??"미확인"} / 시도 ${b.consumer_attempt??"미확인"}`],["마지막 판독 묶음",`${number(b.new_CPU_windows)}창 · 검증 성공 ${number(b.successful_new_CPU_windows)}창 · ${number(b.new_CPU_characters)}자`],["자료 기준",date(r.clocks.data_at)],["영속 저장",date(r.clocks.persisted_at)],["private ACK",r.generation.private_commit],["저장 DB SHA256",r.generation.sqlite_sha256],["공개 요약 SHA256",r.snapshot_sha256]]));
      for(const issue of r.source_issues)p.append(el("p",`${issue.reason_code} · ${number(issue.count)}건`,"section-note"));
      const details=el("details");details.append(el("summary",`문서별 판독·보류 연결 ${number(r.trace.length)} / ${number(r.analysis.trace_total)}건`));for(const t of r.trace)details.append(add(el("div",null,"run-row"),el("b",`${stateLabel(t.read_state)} · ${stateLabel(t.review_state)}`),el("p",`${t.reason_code} · 원문 검증 ${t.source_verification}`,"section-note"),el("p",`창 전체/성공/실패/미판독 ${["total","success","failed","unread"].map(k=>number(t.window_counts[k])).join(" / ")}`,"section-note"),el("p",`ID ${t.document_id} · 본문 버전 ${t.source_version} · 원본 ${t.raw_sha256}`,"mono"),el("p",`모델 ${t.model||"미확인"} · 리비전 ${t.revision||"미확인"} · 분석 결과 ${t.analysis_sha256}`,"mono"),el("p",`미확인 필드 ${t.missing_fields.join(", ")||"기록 없음"}`,"section-note")));p.append(details);content.append(p);
    }
    content.append(el("p",`Actions 상태 관측 ${date(data.workflow_observation?.observed_at)} · 본문 처리 ${workflowLabel(w.acquisition)} · REVIEW ${workflowLabel(w.review)}. 과거 상세 연구 자료 기준 ${date(data.historical_data_at)}를 유지합니다.`,"section-note"));
  }
  function automation(){
    if(data.operating_research||data.collection_observation||data.workflow_observation){operatingAutomation();return;}
    const a=data.automation,c=data.counts;
    const grid=el("div",null,"automation-grid");
    const collectionLabel=a.collection_mode==="MANUAL_TWO_BOUNDED_PASSES"?"수동 실행 기록":"설정 확인 필요";
    const aiLabel=a.ai_mode==="DISABLED"?"자동 판독 중단":"설정 확인 필요";
    for(const [idx,title,status,description,last,tone]of[
      ["01","자료 수집",collectionLabel,`수동으로 ${number(a.collection_runs)}회 실행했습니다. 매일 갱신하는 코드 시험은 끝났지만 예약 실행 성공은 확인되지 않았습니다.`,a.last_collection_at,"green"],
      ["02","AI 분석",aiLabel,"판독 품질 기준을 충족하지 못해 정기 실행을 보류했습니다. 기존 CPU 판독과 보존된 연구 기록을 확인할 수 있습니다.",a.last_cpu_at,"amber"],
      ["03","후보 생성","연구 검토만 실행",`${number(a.reviews)}개 기존 신호의 반대편 근거를 검토했습니다. 적격 공급·필요 시기 부족으로 신규 후보 승격은 없었습니다.`,a.last_review_at,""]]){
      grid.append(add(el("section",null,"process-card"),el("span",`단계 ${idx}`,"process-index"),add(el("h2",title),badge(status,tone)),el("p",description),el("p",`${idx==="02"?"마지막 CPU 기록":"마지막 실행 기록"} · ${date(last)}`,"process-last")));}content.append(grid);
    content.append(add(el("div",null,"stats-grid"),stat("신규 API 호출",a.api_calls,"최근 전 산업 수집 연구 범위","↗","회"),stat("사용한 API 토큰",a.api_tokens,"과거 실험 누적량과 별도","◫","개"),stat("API 비용",a.api_cost_krw,"플랫폼·CPU 비용은 별도 미확인","₩","원"),stat("분리 보관된 오류",a.errors.length,`접근 표시 자료 ${number(c.quarantined)}건은 별도 격리`,"!")));
    const history=panel("AI는 실행됐지만, 결과 채택은 보류했습니다","과거 시험 기록입니다. 이번 수집의 API 0회와 별도로 보며, 서로 다른 시험을 하나의 성능으로 합치지 않습니다.");
    for(const trial of a.ai_history||[])history.append(add(el("div",null,"run-row"),el("b",`${trial.name} · ${date(trial.at)}`),el("p",`생성 요청 ${number(trial.attempted)}회 · 응답 ${number(trial.received)}건 · ${trial.scope}`),...trial.notes.map(t=>el("p",t))));content.append(history);history.classList.add("history-panel");
    const cols=el("div",null,"two-col"),errors=panel("수집을 멈춘 이유","같은 실패를 반복하지 않고 다른 자료 처리를 계속했습니다.");
    const ebox=el("div");ebox.id="errors-list";errors.append(ebox);let expanded=false;
    function renderErrors(){ebox.replaceChildren();for(const e of a.errors.slice(0,expanded?undefined:4)){let host="출처 미확인";try{host=new URL(e.url).hostname;}catch{}ebox.append(add(el("div",null,"error-row"),el("span","!","error-mark"),add(el("div"),el("strong",`${e.step} · ${host}${e.http_status?` · HTTP ${e.http_status}`:""}`),el("p",e.message),el("p",`${date(e.at)} · ${e.action}`,"caption"),external("해당 출처 열기 ↗",e.url))));}if(a.errors.length>4)ebox.append(btn(expanded?"오류 접기":`오류 ${a.errors.length}건 모두 보기`,()=>{expanded=!expanded;renderErrors();},"button small"));}renderErrors();cols.append(errors);
    const runs=panel("실제로 남은 실행 기록","수동 실행을 정기 자동화 성공으로 세지 않습니다.");for(const r of a.runs)runs.append(add(el("div",null,"run-row"),el("b",date(r.at)),el("p",`출처 ${number(r.source_attempts)}개 · 본문 시도 ${number(r.article_attempts)}건`),el("p",`원본 ${number(r.captured)}건 확보 · 남은 대기 ${number(r.pending)}건`)));
    const kv=el("dl",null,"kv");for(const [k,v]of[["자동 예약 실행","확인된 실행 없음"],["7일 연구 관측",a.shadow_mode==="NOT_ACTIVATED"?"시작하지 않음":"기록 확인 필요"],["현재 백그라운드 실행","별도 실시간 감시가 없어 확인 불가"],["연결 자료",data.source.mode],["설정 기록 시각",date(a.scope_at)]])add(kv,el("dt",k),el("dd",v));runs.append(kv);cols.append(runs);content.append(cols);
    const gaps=panel("다음 확인이 필요한 자료","분야별 공백이 다른 산업의 탐색을 막지는 않습니다.");gaps.append(el("p","산업마다 수집·판독 범위가 다릅니다. 최신 CPU 제안과 보도 검토도 공식 1차 원문, 제품별 필요 시기, 전체 적격 공급량과 독립 반대편 근거 확인이 필요합니다.","muted"));content.append(gaps);
  }
  function kv(rows){const n=el("dl",null,"kv");for(const [k,v]of rows)add(n,el("dt",k),el("dd",value(v)));return n;}
  async function openDetail(id){
    const token=++detailRequest;const dialog=$("detail"),body=$("detail-body");body.replaceChildren(el("h2","근거를 읽고 있습니다","loading"));if(!dialog.open)dialog.showModal();
    try{const r=await request(`/api/evidence/${id}`);if(token!==detailRequest||!dialog.open)return;body.replaceChildren();
      const title=el("h2",r.product);title.id="detail-title";body.append(title,add(el("div",null,"detail-status"),badge(r.status,r.category==="reviewed"?"green":"amber"),badge(displayStage(r.stage)),badge(r.actuality)));
      if(r.category==="discovery"||r.category==="cpu_product")body.append(el("p","제품명과 역할은 CPU가 제안한 값입니다. 수요·공급 사실로 채택하지 않은 탐색 기록입니다.","notice"));
      body.append(kv([["산업",r.industry],["제품",r.product],["제품 규격",r.target.specification],["지역",r.target.region],["고객",r.target.customer_group],["공급자 범위",r.target.supply_pool],["예상 병목 시기",r.period],["고객 필요 시기",r.need_time],["공급 준비 시기",r.ready_time],["근거의 대상 기간",r.evidence_period]]));
      body.append(el("p",`${r.industry_basis} 제품·규격·지역·고객·공급자 이름은 저장된 원문 표기를 유지합니다.`,"caption"));
      const judgement=el("section",null,"detail-section");judgement.append(el("h3","수요·공급 판단"),el("p",`이 기록의 분류: ${r.role_label} · ${r.actuality}`,"muted"),el("p",r.counterpart_note,"section-note"));
      const fields=r.fields||{},quantity=fields.quantity,unit=fields.unit;if(quantity||unit)judgement.append(kv([["수량 원문",quantity?.surface],["단위 원문",unit?.surface]]));body.append(judgement);
      const missing=el("section",null,"detail-section");missing.append(el("h3","아직 부족한 근거"));const ul=el("ul",null,"missing-list");r.missing.forEach(t=>ul.append(el("li",t)));missing.append(ul);body.append(missing);
      const refs=el("section",null,"detail-section");refs.append(el("h3",`원문 근거 ${r.references.length}개`),el("p",r.semantic_note,"caption"));for(const ref of r.references)refs.append(reference(ref));body.append(refs);
    }catch(e){if(token!==detailRequest||!dialog.open)return;const title=el("h2","근거를 읽지 못했습니다");title.id="detail-title";body.replaceChildren(title,el("p",e.message,"muted"),btn("이 근거 다시 읽기",()=>openDetail(id)));}
  }
  function reference(r){
    const n=el("article",null,"reference-box");n.append(badge(r.verification,r.verified?"green":"red"));
    if(r.kind==="text"){
      n.append(add(el("div",null,"reference-meta"),el("span",`공개 ${date(r.published_at)}`),el("span",`확보 ${date(r.acquired_at)}`),el("span",`원문 ${number(r.start)}~${number(r.end)}자 위치`)));
      n.append(el("p","인용 원문 · 원문의 언어와 표현을 그대로 표시합니다.","section-note"),el("blockquote",r.quote,`quote ${r.verified?"":"invalid"}`));
      if(r.verified){const details=el("details");details.append(el("summary","인용 앞뒤 문맥 보기"),el("p",r.context_before||"원문 시작"),el("blockquote",r.quote,"quote"),el("p",r.context_after||"원문 끝"));n.append(details);}
      const metadata=el("details");metadata.append(el("summary","원문 식별 정보 보기"),el("p",`본문 해시: ${r.body_sha256||"미확인"}`,"mono"),el("p",`이 문서의 저장된 본문: ${number(r.document_characters)}자. 앞뒤 문맥 보기는 전체 문서 판독을 뜻하지 않습니다.`));n.append(metadata);
    }else{
      n.append(add(el("div",null,"reference-meta"),el("span",`보고 대상 월 ${r.period}`),el("span",`공식 표 ${r.sheet} · ${r.row}행`)));
      const names={"Plant Name":"설비 이름","Generator ID":"발전기 식별자","Plant State":"미국 주","Technology":"설비 기술","Status":"보고된 상태","Nameplate Capacity (MW)":"명목 발전용량 (MW)","Operating Year":"기록된 가동 연도","Operating Month":"기록된 가동 월"};const table=el("table",null,"research-table");const tr=el("tr");["항목","표에 적힌 값","셀 위치"].forEach(t=>tr.append(el("th",t)));table.append(add(el("thead"),tr));const tbody=el("tbody");for(const [key,title]of Object.entries(names))if(Object.hasOwn(r.fields,key))tbody.append(add(el("tr"),el("td",title),el("td",r.fields[key]),el("td",r.cells[key])));table.append(tbody);n.append(add(el("div",null,"table-wrap"),table),el("p","보고 대상 월은 공개일이 아닙니다. 보고된 가동 상태와 실제 적격 공급량은 다를 수 있습니다.","section-note"));const d=el("details");d.append(el("summary","공식 표 식별 정보 보기"),el("p",`원본 해시: ${r.raw_sha256}`,"mono"));n.append(d);
    }
    const a=external(r.kind==="table"?"공식 표 원출처 열기 ↗":"원문 사이트 열기 ↗",r.url);if(a)n.append(a);return n;
  }
  $("refresh").addEventListener("click",async()=>{await load();if(data&&!$("notice").textContent)notify(`저장된 기록을 다시 읽었습니다. 기준 시각 ${date(data.data_at)} · 새 수집은 실행하지 않았습니다.`,"success");});
  $("close-detail").addEventListener("click",()=>$("detail").close());
  $("detail").addEventListener("close",()=>{detailRequest++;});
  window.addEventListener("hashchange",()=>{if($("detail").open)$("detail").close();render();window.scrollTo(0,0);});
  load();
})();
