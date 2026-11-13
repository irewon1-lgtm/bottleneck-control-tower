"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = String(text); if (cls) n.className = cls; return n; };
  const add = (n, ...children) => { n.append(...children.filter(Boolean)); return n; };
  const number = n => n == null ? "미확인" : Number(n).toLocaleString("ko-KR");
  const known = v => v != null && v !== "" && v !== "UNKNOWN";
  const value = v => known(v) ? String(v) : "아직 확인되지 않음";
  // Presentation aliases only. Source names, IDs, quotes and ranking inputs
  // stay untouched; the original name remains available in the detail view.
  const productLabelsKo = Object.freeze({
    "a320 family": "A320 항공기 계열",
    "a350f": "A350F · 원문 모델명",
    "a350f freighter": "A350F 화물기",
    "agent studio platform": "에이전트 스튜디오 플랫폼",
    "agx": "AGX 항로 서비스",
    "ai agent builder": "인공지능 작업 도우미 제작 도구",
    "ai inference gpu": "인공지능 실행용 그래픽 처리 장치",
    "ai processor": "인공지능 처리 반도체",
    "ai processors": "인공지능 처리 반도체",
    "ai-agent": "인공지능 작업 도우미",
    "air": "에이아이알 · 원문 약어",
    "airbus": "에어버스",
    "airbus family": "에어버스 계열",
    "airbus h160": "에어버스 H160",
    "american nuclear energy": "아메리칸 뉴클리어 에너지",
    "batteries": "배터리",
    "battery electric": "배터리 전기 구동",
    "battery materials": "배터리 소재",
    "biosimilar": "바이오시밀러 · 기존 바이오의약품과 유사한 약",
    "blackwell ultra": "블랙웰 울트라",
    "burn-in modules": "불량 선별용 가속 노화 시험 장치",
    "bwrx-300": "BWRX-300 · 원문 모델명",
    "call": "전화 설명회 · 제품명 여부 확인 필요",
    "cassiopée": "카시오페",
    "ccl stage 3": "CCL 3단계",
    "chatgpt": "챗지피티",
    "claude": "클로드",
    "coal-fired power plants": "석탄 화력발전소",
    "commercial crude oil": "상업용 원유",
    "competitor aircraft": "경쟁사 항공기",
    "consteel ® electric arc furnace": "콘스틸 전기로 · 전기로 금속을 녹이는 설비",
    "consumables": "소모품",
    "conventional hydroelectric": "일반 수력발전",
    "converse gold": "컨버스 금광 개발 사업",
    "copilot": "코파일럿",
    "corpus christi lng expansion": "코퍼스 크리스티 액화천연가스 시설 확장",
    "crescent island": "크레센트 아일랜드",
    "crude oil": "원유",
    "cybersecurity gateways": "사이버 보안 연결 장치",
    "data center optical interconnects": "데이터센터의 빛을 이용한 통신 연결",
    "device-specific sockets": "기기별 전용 연결 소켓",
    "diesel": "경유",
    "direct feed system": "직접 공급 시스템",
    "distillate": "증류유 · 원유를 증류해 얻은 기름",
    "distillate fuel": "증류 연료 · 경유·난방유 등",
    "distillate fuel oil": "증류 연료유 · 경유·난방유 등",
    "distributed energy resources": "분산 에너지 자원 · 여러 곳의 발전·저장 설비",
    "drones": "드론",
    "earnings press release": "실적 발표 보도자료",
    "ecnoglutide": "에크노글루타이드",
    "electric generating capacity": "발전 능력",
    "electric motorcycle": "전기 오토바이",
    "electric trucks": "전기 트럭",
    "electric vehicle": "전기차",
    "electric vehicles": "전기차",
    "electricity": "전력",
    "elibrary": "전자자료실",
    "emergency exchange": "비상 교환",
    "employee share ownership plan": "직원 주식 소유 제도",
    "emulsions": "유화액 · 서로 섞이지 않는 액체를 분산시킨 혼합물",
    "engineering academy": "공학 교육 과정",
    "equity-based compensation plans": "주식 기반 보상 제도",
    "european launcher challenge": "유럽 발사체 공모 사업",
    "expanded mobility tactical truck": "기동성 확장 전술 트럭",
    "f126": "F126 · 원문 모델명",
    "falcon shores": "팰컨 쇼어스",
    "federal tax credits": "연방 세액공제",
    "ferc.ai": "퍼크 에이아이",
    "fm1": "FM1 항로 서비스",
    "foams": "거품 재료",
    "fox north energy center": "폭스 노스 에너지 센터",
    "fox wlbi test cell": "폭스 웨이퍼 불량 선별 시험 구획",
    "fox-xp": "폭스 엑스피",
    "fox-xp tm multi-wafer test and burn-in system": "폭스 엑스피 다중 웨이퍼 검사·가속 노화 시험 장비",
    "fox-xp ® wafer-level burn-in": "폭스 엑스피 웨이퍼 상태 가속 노화 시험",
    "fox-xp ® wafer-level burn-in (wlbi) system": "폭스 엑스피 웨이퍼 상태 가속 노화 시험 장비",
    "frigates": "호위함",
    "fuel supplies": "연료 공급",
    "g302": "G302 네트워크 연결 장치",
    "gas": "가스",
    "gas-fired facility": "가스 연소 시설",
    "gasoline": "휘발유",
    "ge vernova": "지이 버노바",
    "ge vernova 9f gas turbines": "지이 버노바 9F 가스터빈",
    "glp-1": "GLP-1 계열 의약품",
    "gpu d-series": "그래픽 처리 장치 D 계열",
    "grid": "전력망",
    "grid capacity": "전력망 수용 능력",
    "h145": "H145 · 원문 모델명",
    "h160": "H160 · 원문 모델명",
    "h215ms": "H215M 계열",
    "h225ms": "H225M 계열",
    "hugh brinson pipeline": "휴 브린슨 가스관",
    "hybrid electric": "하이브리드 전기 구동",
    "iar-330 puma": "IAR-330 푸마",
    "integrated fires protection capability": "통합 화력 방어 능력",
    "interceptor": "요격 장비",
    "isd": "아이에스디 · 원문 약어",
    "jebel ali": "제벨알리",
    "jet fuel": "항공유",
    "khor fakkan": "코르파칸",
    "landfill gas": "매립지에서 발생하는 가스",
    "launch service supply": "발사 서비스 공급",
    "launchers": "발사체·발사 장치",
    "leopold i": "레오폴트 1세",
    "light tactical drone system": "경량 전술 드론 체계",
    "light-duty vehicles": "경량 차량",
    "liquefied natural gas": "액화천연가스",
    "liquid fuels": "액체 연료",
    "lng": "액화천연가스",
    "louise-marie": "루이즈마리",
    "manganese sulphate": "황산망간",
    "megacharger": "메가차저",
    "meko a-200 deu": "메코 A-200 DEU",
    "mi455x": "MI455X · 원문 모델명",
    "munitions": "탄약·군수품",
    "natural gas": "천연가스",
    "natural gas fired combined cycle": "천연가스 복합발전",
    "natural gas fired combustion turbine": "천연가스 연소 터빈",
    "natural gas internal combustion engine": "천연가스 엔진",
    "natural gas steam turbine": "천연가스 증기터빈",
    "natural gas-fired power plant": "천연가스 발전소",
    "networking products": "통신망 연결 제품",
    "new clean vehicle credit": "신규 친환경차 세액공제",
    "next-generation advanced reactors": "차세대 첨단 원자로",
    "next-generation devices": "차세대 기기",
    "nhon trach 3&4 power plant": "년짝 3·4호 발전소",
    "nist internal report": "미국 표준기술연구소 내부 보고서",
    "nuclear fuel": "핵연료",
    "nuclear plants": "원자력발전소",
    "offshore wind turbine": "해상 풍력발전기",
    "oil": "석유",
    "onshore wind turbine": "육상 풍력발전기",
    "optical connectivity solutions": "빛을 이용한 통신 연결 기술",
    "optical i/o architectures": "빛을 이용한 데이터 입출력 구조",
    "order": "주문 · 문맥 검토 필요",
    "other gases": "기타 가스",
    "other oils": "기타 석유류",
    "paracom": "파라콤",
    "paracom gateways": "파라콤 연결 장치",
    "patriot missiles": "패트리엇 미사일",
    "payload": "탑재체 · 기체에 실리는 장비",
    "perjeta": "퍼제타",
    "petroleum liquids": "액체 석유 연료",
    "plant of the year": "올해의 발전소 · 수상 명칭",
    "ponte vecchio": "폰테베키오",
    "powders": "분말",
    "preliminary monthly electric generator inventory": "월별 발전설비 목록 잠정치",
    "press releases": "보도자료",
    "product slate": "생산 제품 구성",
    "production software enhancements": "생산 소프트웨어 개선",
    "propane": "프로판",
    "puma": "푸마",
    "qshield": "큐실드",
    "qualified commercial clean vehicle credit": "요건을 충족하는 상업용 친환경차 세액공제",
    "quantum science": "양자과학",
    "replay": "다시보기 · 제품명 여부 확인 필요",
    "residual fuel oil": "잔사 연료유 · 중유",
    "rialto bridge": "리알토 브리지",
    "roadster": "로드스터",
    "rotor life extension": "회전자 수명 연장",
    "s250 platform": "S250 플랫폼",
    "satellite solution": "위성 기술·서비스",
    "semiconductor devices": "반도체 소자 · 전자부품",
    "sensors": "센서",
    "sentinel-3 series": "센티넬 3 계열",
    "sentinel-3c": "센티넬 3C",
    "share buyback programme": "자사주 매입 계획",
    "silicon one a100l": "실리콘 원 A100L",
    "silicon one g300": "실리콘 원 G300",
    "silicon photonic integrated circuits": "실리콘 광통신 집적회로",
    "silicon photonics": "실리콘을 이용한 광통신 기술",
    "silicon photonics integrated circuits": "실리콘 광통신 집적회로",
    "simple-cycle natural gas": "단순 가스터빈 방식의 천연가스 발전",
    "smart solar farms": "지능형 태양광 발전단지",
    "software": "소프트웨어",
    "solar cells": "태양전지",
    "solar photovoltaic": "태양광 발전",
    "sonoma": "소노마",
    "sonoma systems": "소노마 시스템",
    "sonoma ultra-high-power systems": "소노마 초고출력 시스템",
    "state energy data system": "미국 주별 에너지 통계 시스템",
    "steam turbines": "증기터빈",
    "stem programme": "과학·기술·공학·수학 교육 과정",
    "strategic petroleum reserve exchange": "전략비축유 교환",
    "super intelligence": "초지능",
    "supplementary financial information": "추가 재무 정보",
    "supply chain traceability principles": "공급망 이력 추적 원칙",
    "systems": "시스템 · 세부 대상 확인 필요",
    "targeting systems": "표적 지정 시스템",
    "tissue bank specimens": "조직은행 검체",
    "top gas plant": "최우수 가스발전소 · 수상 명칭",
    "u050 capa-x": "U050 카파엑스",
    "u740-valkyrie": "U740 발키리",
    "ultra-dense small form factor": "고밀도 소형 규격",
    "uncrewed collaborative combat aircraft (cca)": "무인 협동 전투 항공기",
    "usfp": "USFP 광통신 모듈 규격",
    "usfp 400g optics": "USFP 400G 광통신 모듈",
    "waferpak": "웨이퍼팩",
    "waferpak™ contactors": "웨이퍼팩 접촉 검사 장치",
    "weapons": "무기",
    "wlbi": "웨이퍼 상태 가속 노화 시험",
    "wood/wood waste biomass": "목재·폐목재 바이오매스 연료"
});
  const productLabel = raw => {
    const key=String(raw??"").toLowerCase().trim().replace(/\s+/g," ");
    return Object.hasOwn(productLabelsKo,key)?productLabelsKo[key]:value(raw);
  };
  const date = v => {
    if (!known(v) || Number.isNaN(new Date(v).getTime())) return "시각 미확인";
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v.replaceAll("-", ".");
    return new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul", year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(v));
  };
  const badge = (text, tone="") => el("span", text, `badge ${tone}`);
  const btn = (text, action, cls="button") => { const n=el("button",text,cls); n.type="button"; if(action)n.addEventListener("click",action); return n; };
  const link = (text, href, cls="text-link") => { const n=el("a",text,cls); n.href=href; return n; };
  const external = (text, raw, cls="text-link") => { try { const u=new URL(raw); if(!["http:","https:"].includes(u.protocol)||u.username||u.password)return null; const n=link(text,u.href,cls);n.target="_blank";n.rel="noopener noreferrer";return n; } catch {return null;} };
  const displayStage = s => ({S1:"변화 신호 · S1",S2:"대상 구체화 · S2",S3:"공급 공백 근거 · S3"}[s]||"단계 판정 전");
  const detailButton = (r, text="근거 보기") => { const b=btn(text,()=>openDetail(r.id),"button small");b.setAttribute("aria-label",`${productLabel(r.product)} ${text}`);b.dataset.evidence=r.id;return b; };
  const panels = {
    overview:["한눈에 보기","자료가 얼마나 읽혔는지, 어떤 변화가 확인됐는지 살펴봅니다."],
    news:["최신 뉴스","RSS 수집 기사 제목을 발행일·수집일과 함께 보여줍니다. 병목 검증 근거와 구분합니다."],
    candidates:["미래 병목 후보","향후 12~36개월의 공급 부족 후보와 아직 검토 중인 변화를 구분합니다."],
    evidence:["판단 근거","저장된 원문과 공식 표를 열어, 판단이 어디에서 나왔는지 확인합니다."],
    automation:["자동화 현황","자동화 설정과 실제 실행 기록을 구분해 보여줍니다."]
  };
  let data=null, currentPage="overview", loadBusy=false, detailRequest=0;
  let rssNews=null, rssNewsError="", rssNewsLoading=false;
  const rssNewsState={query:"",source:"",sourceGroup:"",period:"all",sort:"collected",onlyNew:false,page:1};
  const state={candidates:{tab:"reviewed",query:"",industry:"",role:"",page:1},evidence:{source:"base",category:"",query:"",industry:"",role:"",page:1}};
  const content=$("content");
  function notify(text, tone=""){ $("notice").replaceChildren(text ? el("div",text,`notice ${tone}`) : document.createTextNode("")); }
  async function request(path){const r=await fetch(path,{cache:"no-store"});const body=await r.json();if(!r.ok)throw Error(body.error||"자료를 불러오지 못했습니다.");return body;}
  async function load(){
    if(loadBusy)return;loadBusy=true;$("refresh").disabled=true;
    try{data=await request("/api/dashboard");data.loaded_at=new Date().toISOString();
      if(rssNews&&rssNews.source_run_id!==data.rss_news_summary?.source_run_id){rssNews=null;rssNewsError="";}
      render();notify(data.publication?`저장된 연구 자료 · 화면 배포 ${date(data.publication.last_sync_at)} · ${data.publication.status_label}. 새로 읽기는 수집·분석을 실행하지 않습니다.`:data.source.snapshot?"검증된 연구 백업을 보고 있습니다. 현재 수집기의 실시간 상태를 뜻하지 않습니다.":"");}
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
    content.replaceChildren();
    if(currentPage!=="overview")content.append(head());
    if($("top-latest"))$("top-latest").textContent="최근 반영: "+date(data.snapshot_generated_at||data.data_at);
    ({overview:firstOverview,news:news,candidates:candidates,evidence:evidence,automation:automation}[currentPage])();
  }

  // Approved first-image layout. Everything is calculated from the saved
  // public snapshot; never turn a product mention into a proved bottleneck.
  let selectedBoardSector = "";
  let shownBoardEvidence = 7;
  let shownBoardSectors = 10;
  const boardKinds = {reviewed:"원문 검토",structured:"공식 표 기록",discovery:"제품 탐색"};
  const boardExcludedSectors = new Set(["산업 확인 필요","산업 추가 확인","아직 분류하지 않은 산업"]);

  function boardRankRows(){
    if(data.sector_rankings && Array.isArray(data.sector_rankings.rows))return data.sector_rankings.rows;
    // Local read-only dashboard fallback; public static exports use the
    // identical source-linked server ranking calculation.
    const groups=new Map();
    for(const r of data.records||[]){
      if(!Object.hasOwn(boardKinds,r.category)||boardExcludedSectors.has(r.industry)||!r.industry)continue;
      if(!groups.has(r.industry))groups.set(r.industry,new Map());
      groups.get(r.industry).set(r.id,r);
    }
    const rows=[...groups].map(([name,values])=>{
      const all=[...values.values()];
      const dates=all.map(r=>r.published_at).filter(Boolean).sort().reverse();
      return {name:name,evidence_count:all.length,recent_publication:dates[0]||null,
        reviewed_count:all.filter(r=>r.category==="reviewed").length,
        structured_count:all.filter(r=>r.category==="structured").length,
        discovery_count:all.filter(r=>r.category==="discovery").length};
    }).sort((a,b)=>b.evidence_count-a.evidence_count||a.name.localeCompare(b.name,"ko"));
    let previousCount=-1,rank=0;
    rows.forEach((r,i)=>{if(r.evidence_count!==previousCount){rank=i+1;previousCount=r.evidence_count;}r.rank=rank;});
    return rows;
  }

  function boardPrevious(row){
    const p=data.sector_rank_previous;
    if(!p||p.status!=="VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT")return {label:"—",change:"비교 전",tone:"muted"};
    const old=p.ranks&&p.ranks[row.name];
    if(!old||!Number.isInteger(old.rank))return {label:"신규",change:"새로 등장",tone:"up"};
    const delta=old.rank-row.rank;
    return {label:String(old.rank)+"위",change:delta>0?"▲ "+delta:delta<0?"▼ "+(-delta):"유지",tone:delta>0?"up":delta<0?"down":"muted"};
  }

  function boardEvidenceFor(sector){
    const priority={reviewed:0,structured:1,discovery:2};
    return (data.records||[]).filter(r=>r.industry===sector&&Object.hasOwn(boardKinds,r.category))
      .sort((a,b)=>priority[a.category]-priority[b.category]||
        String(b.published_at||"").localeCompare(String(a.published_at||""))||
        a.id.localeCompare(b.id));
  }


  // Separate source-linked RSS publication lane. RSS headlines are discovery
  // inputs only, never evidence for sector ranking, S1/S2/S3 or EARLY success.
  function rssNewsTeaser(){
    const info=data.rss_news_summary||{};
    const box=el("section",null,"bct-first-panel bct-news-teaser");
    box.append(add(el("div",null,"bct-panel-title"),el("span","▤","bct-panel-icon"),
      el("h2","최신 수집 뉴스"),link("기사 전체 보기","#news","bct-news-jump")));
    if(info.status!=="VERIFIED_PUBLIC_RSS_METADATA"){
      box.append(el("p","최신 뉴스 공개 기록은 확인 중입니다. 과거 연구 근거를 오늘의 뉴스로 표시하지 않습니다.","bct-news-limited"));
      return box;
    }
    box.append(add(el("div",null,"bct-news-counter"),
      add(el("div"),el("span","이번 수집에서 추가된 기사"),el("strong",number(info.new_article_count)+"건")),
      add(el("div"),el("span","저장된 전체 RSS 기사"),el("strong",number(info.visible_article_count)+"건")),
      add(el("div"),el("span","최근 RSS 수집 완료"),el("strong",date(info.collected_completed_at))),
      add(el("div"),el("span","수집 실패 출처"),el("strong",number(info.feed_failed)+"개"))));
    const list=el("div",null,"bct-news-teaser-list");
    for(const article of (info.newest_articles||[]).slice(0,6)){
      const line=el("div",null,"bct-news-teaser-item");
      line.append(el("span",article.source,"bct-news-source"));
      const a=external(article.title,article.url);
      line.append(a||el("span",article.title));
      line.append(el("small","수집 "+date(article.collected_at)+" · 발행 "+(article.published_at?date(article.published_at):article.publication_date_status==="FUTURE_DATE_HOLD"?"검증 보류(미래 날짜)":"미확인")));
      list.append(line);
    }
    box.append(list,el("p","뉴스의 제목과 요약은 수집 원문 표기이며 병목 검증이 아닙니다. 순위표는 별도의 근거 기록만 사용합니다.","bct-panel-explain"));
    return box;
  }

  function rssNewsFilterControl(labelText,control){
    return add(el("label",null,"bct-news-filter"),el("span",labelText),control);
  }
  function rssNewsSelect(options,value,onChange){
    const s=el("select");
    for(const [key,labelText] of options){const o=el("option",labelText);o.value=key;s.append(o);}
    s.value=value;s.addEventListener("change",()=>onChange(s.value));
    return s;
  }

  function news(){
    const info=data.rss_news_summary||{};
    if(info.status!=="VERIFIED_PUBLIC_RSS_METADATA"){
      content.append(empty("최신 뉴스 자료 연결 확인 중",
        "현재 공개된 뉴스 파일의 실제 수집 이력이 아직 검증되지 않았습니다. 역사적 근거 수를 최신 뉴스로 표시하지 않습니다."));
      return;
    }
    if(!rssNews){
      if(rssNewsError){
        content.append(empty("최신 기사 파일을 불러오지 못했습니다",rssNewsError,
          btn("뉴스 파일 다시 읽기",()=>{rssNewsError="";rssNewsLoading=false;render();},"button primary")));
        return;
      }
      content.append(empty("기사 원장을 읽는 중입니다","실제 RSS 수집 원본과 연결된 별도 공개 기사 목록입니다."));
      if(!rssNewsLoading){
        rssNewsLoading=true;
        request("./api/rss-news.json").then(body=>{
          if(body.format!=="bct-public-rss-news-1"||
             body.status!=="VERIFIED_PUBLIC_RSS_METADATA"||
             body.source_run_id!==info.source_run_id||
             !Array.isArray(body.articles)||
             body.articles.length!==info.visible_article_count){
            throw Error("기사 버전과 공개 화면의 수집 이력이 일치하지 않습니다.");
          }
          rssNews=body;rssNewsError="";
        }).catch(e=>{rssNewsError=e.message||"자료 요청이 실패했습니다.";})
          .finally(()=>{rssNewsLoading=false;if(currentPage==="news")render();});
      }
      return;
    }
    const n=rssNews;
    const summary=el("section",null,"bct-first-panel bct-news-main-summary");
    summary.append(add(el("div",null,"bct-panel-title"),el("span","▤","bct-panel-icon"),el("h2","실제로 수집한 뉴스 전체")));
    summary.append(add(el("div",null,"bct-news-counter"),
      add(el("div"),el("span","보유 기사"),el("strong",number(n.visible_article_count)+"건")),
      add(el("div"),el("span","최근 실행 새 기사"),el("strong",number(n.new_article_count)+"건")),
      add(el("div"),el("span","정상 작동 출처"),el("strong",number(n.feed_success)+"개")),
      add(el("div"),el("span","실패 출처"),el("strong",number(n.feed_failed)+"개"))));
    summary.append(el("p","RSS 수집 완료: "+date(n.collected_completed_at)+" · 기사의 발행일은 각 항목에 따로 표시됩니다. 출처 등록 분야는 뉴스 내용의 산업 검증 결과가 아니며, 분야 미확인·복수 출처는 확정 분류하지 않습니다.","bct-news-limited"));
    content.append(summary);

    const filters=el("section",null,"bct-first-panel bct-news-controls");
    const filterItems=el("div",null,"bct-news-controls-grid");
    const query=el("input");query.type="search";query.placeholder="기사 제목·요약·출처 검색";
    query.value=rssNewsState.query;query.setAttribute("aria-label","뉴스 검색어");
    query.addEventListener("input",()=>{rssNewsState.query=query.value;rssNewsState.page=1;renderNewsResults();});
    filterItems.append(rssNewsFilterControl("검색",query));
    const sources=[...new Set(n.articles.map(r=>r.source))].sort((a,b)=>a.localeCompare(b));
    filterItems.append(rssNewsFilterControl("기사 출처",rssNewsSelect([["","모든 출처"],...sources.map(s=>[s,s])],
      rssNewsState.source,v=>{rssNewsState.source=v;rssNewsState.page=1;renderNewsResults();})));
    const sourceGroups=[...new Set(n.articles.map(r=>r.source_group||"분야 확인 필요"))].sort((a,b)=>a.localeCompare(b,"ko"));
    filterItems.append(rssNewsFilterControl("출처 등록 분야(참고)",rssNewsSelect([["","모든 분야"],...sourceGroups.map(g=>[g,g])],
      rssNewsState.sourceGroup,v=>{rssNewsState.sourceGroup=v;rssNewsState.page=1;renderNewsResults();})));
    filterItems.append(rssNewsFilterControl("표시 순서",rssNewsSelect([["collected","최근 수집순"],["published","최근 발행순"]],
      rssNewsState.sort,v=>{rssNewsState.sort=v;rssNewsState.page=1;renderNewsResults();})));
    filterItems.append(rssNewsFilterControl("기사 발행일",rssNewsSelect([["all","전체 기간"],["7","최근 7일"],["30","최근 30일"]],
      rssNewsState.period,v=>{rssNewsState.period=v;rssNewsState.page=1;renderNewsResults();})));
    const newOnly=el("input");newOnly.type="checkbox";newOnly.checked=rssNewsState.onlyNew;
    newOnly.addEventListener("change",()=>{rssNewsState.onlyNew=newOnly.checked;rssNewsState.page=1;renderNewsResults();});
    filterItems.append(add(el("label",null,"bct-news-check"),newOnly,el("span","이번 수집에서 새로 추가된 기사만 보기")));
    filters.append(filterItems);
    content.append(filters);

    const result=el("section",null,"bct-first-panel bct-news-results");
    result.id="rss-news-results";content.append(result);
    renderNewsResults();
    const bad=el("section",null,"bct-first-panel bct-feed-failures");
    const details=el("details");
    details.append(el("summary","최근 수집 실패 출처 "+number(n.feed_failed)+"개 확인"));
    details.append(el("p","실패는 해당 출처의 최근 수집 시도에 한정됩니다. 접근 거부·주소 오류가 있더라도 다른 출처의 기사는 보존합니다.","bct-news-limited"));
    for(const failure of n.failed_feeds){
      const line=el("div",null,"bct-feed-error-line");
      line.append(el("strong",failure.feed),
        el("span",failure.type+(failure.http_status?" · HTTP "+failure.http_status:"")),
        el("span",failure.reason));
      details.append(line);
    }
    bad.append(details);content.append(bad);
  }

  function renderNewsResults(){
    const root=$("rss-news-results");if(!root||!rssNews)return;
    const s=rssNewsState;
    const keyword=s.query.trim().toLocaleLowerCase();
    const cutoff=s.period==="all"?null:Date.now()-Number(s.period)*24*3600*1000;
    const selected=rssNews.articles.filter(r=>
      (!s.onlyNew||r.is_new) &&
      (!s.source||r.source===s.source) &&
      (!s.sourceGroup||(r.source_group||"분야 확인 필요")===s.sourceGroup) &&
      (!keyword||(r.title+" "+(r.snippet||"")+" "+r.source).toLocaleLowerCase().includes(keyword)) &&
      (!cutoff||(r.published_at&&Date.parse(r.published_at)>=cutoff))
    );
    if(s.sort==="published")selected.sort((a,b)=>
      String(b.published_at||"").localeCompare(String(a.published_at||""))||
      b.collected_at.localeCompare(a.collected_at));
    else selected.sort((a,b)=>b.collected_at.localeCompare(a.collected_at)||
      String(b.published_at||"").localeCompare(String(a.published_at||"")));
    const pageSize=24,pages=Math.max(1,Math.ceil(selected.length/pageSize));
    s.page=Math.max(1,Math.min(s.page,pages));
    const shown=selected.slice((s.page-1)*pageSize,s.page*pageSize);
    root.replaceChildren();
    root.append(add(el("div",null,"bct-news-result-heading"),
      el("strong","조건에 맞는 기사 "+number(selected.length)+"건"),
      el("span","전체 저장 "+number(rssNews.visible_article_count)+"건 · "+number(s.page)+"/"+number(pages)+"쪽")));
    if(!shown.length){root.append(el("p","조건에 맞는 기사가 없습니다. 검색어나 날짜 조건을 변경하세요.","bct-news-limited"));return;}
    const list=el("div",null,"bct-news-article-list");
    for(const item of shown){
      const article=el("article",null,"bct-news-article");
      article.append(add(el("div",null,"bct-news-tags"),
        el("span",item.source,"bct-news-source"),
        el("span","출처 분야: "+(item.source_group||"분야 확인 필요"),"bct-news-source-group"),
        item.is_new?el("span","이번 수집 신규","bct-news-new"):null,
        el("span","제목·요약 수집 / 병목 미검증","bct-news-unverified")));
      const title=el("h3",item.title);
      article.append(title);
      if(item.snippet)article.append(el("p",item.snippet,"bct-news-snippet"));
      article.append(add(el("div",null,"bct-news-article-foot"),
        el("span","발행 "+(item.published_at?date(item.published_at):item.publication_date_status==="FUTURE_DATE_HOLD"?"검증 보류(미래 날짜)":"미확인")),
        el("span","수집 "+date(item.collected_at)),
        item.url?external("원문 기사 열기",item.url,"bct-news-source-link"):
          el("span","출처 링크 안전성 확인 대기")));
      list.append(article);
    }
    root.append(list);
    if(pages>1){
      const pg=el("div",null,"bct-news-pagination");
      const prev=btn("이전 페이지",()=>{s.page--;renderNewsResults();},"button");
      prev.disabled=s.page===1;
      const next=btn("다음 페이지",()=>{s.page++;renderNewsResults();},"button primary");
      next.disabled=s.page===pages;
      pg.append(prev,el("span",number(s.page)+" / "+number(pages)+"쪽"),next);
      root.append(pg);
    }
  }

  function boardStatus(icon,label,status,tone,note){
    const item=el("div",null,"bct-process-item");
    const symbol=el("span",icon,"bct-process-icon");symbol.setAttribute("aria-hidden","true");
    const line=add(el("div",null,"bct-process-line"),el("strong",label),el("span",status,"bct-process-badge "+tone));
    item.append(symbol,line,el("p",note,"bct-process-note"));
    return item;
  }

  function boardMetric(label,reading,note){
    return add(el("div",null,"bct-metric"),el("span",label,"bct-metric-label"),el("strong",reading,"bct-metric-value"),el("small",note||"","bct-metric-note"));
  }


  // Genuine latest new-only source-intake receipt; the legacy automatic
  // observation remains distinct, so a manual run is never a scheduled one.
  function sourceIntakePanel(){
    const item=data.latest_source_capture;
    const area=el("section",null,"bct-first-panel bct-source-intake");
    area.append(add(el("div",null,"bct-panel-title"),el("span","▤","bct-panel-icon"),
      el("h2","기사 수집 → 원문 확보 결과")));
    if(!item||item.status!=="VERIFIED_PUBLIC_SOURCE_INTAKE"){
      area.append(el("p","최근 원문 확보 실행의 공개 검증 기록을 확인할 수 없습니다. 과거 수집 실적을 최신 결과로 대신 표시하지 않습니다.","bct-source-note"));
      return area;
    }
    const mode=item.source_event==="workflow_dispatch"?"요청하여 실행":"자동 연동 실행";
    const cells=el("div",null,"bct-source-grid");
    for(const [label,note,amt] of [
      ["원문 확보 시도",mode,item.seed_attempts],
      ["원문·출처 검증 통과","새 원문 자료, 병목 확정 아님",item.captured],
      ["검증 보류·접근 실패","검증 미통과",item.held],
      ["독립 1차 근거 확보","별도 검증 완료 문서",item.valid_additional_primary_documents]
    ])cells.append(add(el("div",null,"bct-source-cell"),
      el("span",label),el("strong",number(amt)+"건"),el("small",note)));
    area.append(cells);
    const statusLabels={
      CAPTURED:"원문 확보",PROVENANCE_BLOCKED:"원출처 확인 보류",
      TIMEOUT:"접속 시간 초과",HTTP_403:"접근 거부(403)",
      NETWORK_FAILED:"연결 실패",CONNECT_BLOCKED:"연결 차단",
      DUPLICATE_BODY_EXCLUDED:"중복 본문 제외",
      EXISTING_CORPUS_EXCLUDED:"기존 자료 제외",
      BEFORE_NEW_COLLECTION_CUTOVER:"수집 기준일 이전"
    };
    const status=(Object.entries(item.statuses||{})
       .map(([key,n])=>(statusLabels[key]||key)+" "+number(n)+"건").join(" · "));
    const current=item.matches_current_rss?"이번 최신 RSS 수집과 일치":"최신 RSS보다 앞선 원문 확보 실행";
    area.append(el("p","원문 확보 "+date(item.completed_at)+" · "+current+" · "+status,"bct-source-note"));
    area.append(el("p","이 숫자는 원문 접근·출처 확인 결과입니다. 병목 섹터 근거 511건이나 독립 수요·공급 검증 건수에 자동 합산하지 않습니다.","bct-source-disclaimer"));
    return area;
  }


  // Do not display screening, body extraction or AI model progress as verified
  // future supply gaps. Archived 511 research records remain a separate lane.
  function sourceBacklogPanel(){
    const info=data.source_backlog||{};
    const audit=info.pinned_audit||{};
    const screen=info.live_sidecar||{};
    const panelRoot=el("section",null,"bct-first-panel bct-source-backlog");
    panelRoot.append(add(el("div",null,"bct-panel-title"),el("span","◫","bct-panel-icon"),el("h2","RSS 1만 건이 병목 근거 511건과 다른 이유")));
    if(info.format!=="bct-source-and-screening-funnel-1"){
      panelRoot.append(el("p","기사별 원문 처리 대조 기록을 아직 확인하지 못했습니다.","bct-backlog-note"));return panelRoot;
    }
    const recent=screen.status==="VERIFIED_INDEX_ONLY_NOT_ANALYSIS_COMPLETE";
    const sourceStats=el("div",null,"bct-backlog-stats");
    const numberStat=(label,value,desc)=>add(el("div",null,"bct-backlog-metric"),
      el("span",label),el("strong",value),el("small",desc));
    sourceStats.append(
      numberStat("전체 RSS 기사",number(data.rss_news_summary?.visible_article_count)+"건","최근 저장된 기사 제목·출처"),
      numberStat("본문 전체(FULL) 기록",number(audit.body_counts?.FULL)+"건","전수 대조 당시 본문 상태 · 완전 의미 판독은 아님"),
      numberStat("기사 분석 저장",recent?number(screen.registered_screening_record_slots)+"건":"최신 집계 확인 대기","별도 분석 저장소의 자료 수"),
      numberStat("순위표 연구 기록",number(info.historical_rank_input_count)+"건","과거 연구 근거 기준 · 병목 확정 아님")
    );
    panelRoot.append(sourceStats);
    const stats=el("p",null,"bct-backlog-note");
    stats.textContent="11월 13일 원문 전수 대조: 일부 확보 "+number(audit.body_counts?.PARTIAL)+
      "건 · 원문 확보 불가 "+number(audit.body_counts?.UNAVAILABLE)+"건 · 분석 저장소 미연결 "+
      number(audit.body_counts?.NOT_IN_SIDECAR)+"건 · 원문 재확인 대상 "+number(audit.due_source_recheck)+
      "건 · 접근/재시도 제한 등 보류 "+number(audit.blocked_or_deferred)+"건.";
    panelRoot.append(stats);
    const chronology=recent?(info.audit_matches_live_sidecar?
      "원문 전수 대조와 분석 저장소가 같은 코드 저장 세대입니다.":
      "분석 저장소가 전수 대조 이후 갱신되었습니다. FULL/보류 수는 전수 대조 당시 자료이며 최신 실적을 뜻하지 않습니다."):
      "최신 분석 저장소 실적은 검증 대기입니다. 전수 대조 수치는 당시 기준으로 유지합니다.";
    panelRoot.append(el("p",chronology,"bct-backlog-note"));
    const hypot=recent?number(screen.unverified_hypothesis_slots)+"건":"미확인";
    panelRoot.append(el("p","탐색 가설 "+hypot+"은 사실 확인 전 제안이며, 검증된 독립 수요·공급 근거 쌍이나 병목 부족 확정 건수가 아닙니다. 기존 연구 기록 "+
      number(info.historical_rank_input_count)+"건의 산업별 순위는 검증된 최신 근거가 등록될 때만 갱신됩니다.","bct-backlog-disclaimer"));
    const trial=audit.selected_future_work||{};
    panelRoot.append(el("p","다음 실행을 위해 전수 대조 당시 선정한 "+number(trial.total)+
      "건(최근 "+number(trial.recent)+"건·과거 "+number(trial.older)+
      "건)은 선정 작업일 뿐, 원문 수집 또는 판독 완료로 세지 않았습니다.","bct-backlog-note"));
    const go=link("10,604건 전수 대조 실행 내역 열기","https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/"+audit.source_run_id);
    panelRoot.append(add(el("div",null,"bct-backlog-link"),go));
    return panelRoot;
  }

  function firstOverview(){
    const current=boardRankRows();
    const snapshot=data.operating_research||null;
    const counts=snapshot&&snapshot.counts||{};
    const collection=data.collection_observation||null;
    const observed=data.workflow_observation&&data.workflow_observation.workflows||{};
    const lastPublished=data.snapshot_generated_at||data.data_at;
    const lastStored=snapshot?.clocks?.persisted_at;
    const future=Object.values(data.counts.future_candidates||{}).reduce((sum,n)=>sum+(Number(n)||0),0);
    const page=el("div",null,"bct-first-page");
    const title=el("header",null,"bct-page-title");
    title.append(el("h1","BCT V4 미래 병목 탐색판"),
      el("p","주가 추천이 아니라, 실제 저장된 산업별 근거를 찾아보는 화면입니다."),
      el("span","확정된 미래 병목 "+number(future)+"건 · 근거 기록이 많아도 공급 부족 확정은 아닙니다.","bct-promise"));
    page.append(title);
    page.append(rssNewsTeaser());
    page.append(sourceIntakePanel());

    const columns=el("div",null,"bct-rank-columns");
    const rankingPanel=el("section",null,"bct-first-panel");
    const rankingHead=add(el("div",null,"bct-panel-title"),el("span","☷","bct-panel-icon"),el("h2","병목 후보 섹터 순위표"));
    rankingPanel.append(rankingHead);
    const tableArea=el("div",null,"bct-table-scroll");
    const table=el("table",null,"bct-rank-table");
    const tHead=el("thead"),header=el("tr");
    ["현재","이전","변동","병목 후보 섹터","증거 수","최근 자료","상세"].forEach(text=>header.append(el("th",text)));
    tHead.append(header);table.append(tHead);
    const tbody=el("tbody");table.append(tbody);
    tableArea.append(table);rankingPanel.append(tableArea);
    const moreSector=el("div",null,"bct-rank-more");
    const previous=data.sector_rank_previous||{};
    rankingPanel.append(moreSector);
    rankingPanel.append(el("p","증거 수는 이 산업에 연결된 저장 기록 수입니다. 중복 기사·검토 전 탐색 기록이 포함될 수 있습니다. 검증된 미래 병목 수와 다릅니다.","bct-panel-explain"));
    rankingPanel.append(el("p",previous.status==="VERIFIED_PREVIOUS_PUBLIC_SNAPSHOT"?
      "이전 순위 비교: "+date(previous.generated_at)+" 공개 화면을 기준으로 계산했습니다.":
      "이전 공개 순위 기록을 확인하지 못한 항목은 ‘—’로 표시합니다. 순위를 지어내지 않습니다.","bct-history-note"));
    columns.append(rankingPanel);

    const details=el("section",null,"bct-first-panel bct-evidence-panel");
    details.append(add(el("div",null,"bct-panel-title"),el("span","▤","bct-panel-icon"),el("h2","선택한 섹터 근거")));
    const detailBody=el("div",null,"bct-evidence-body");
    detailBody.setAttribute("aria-live","polite");
    details.append(detailBody);
    columns.append(details);
    page.append(columns);
    page.append(sourceBacklogPanel());
    content.append(page);

    function choose(name){
      selectedBoardSector=name;shownBoardEvidence=7;
      renderRanks();renderSector();
    }
    function renderRanks(){
      tbody.replaceChildren();moreSector.replaceChildren();
      const visible=current.slice(0,shownBoardSectors);
      for(const r of visible){
        const prev=boardPrevious(r);
        const shared=current.some(other=>other!==r&&other.evidence_count===r.evidence_count);
        const tr=el("tr",null,r.name===selectedBoardSector?"bct-row-selected":"");
        const selector=btn(r.name,()=>choose(r.name),"bct-sector-name");
        selector.setAttribute("aria-pressed",String(r.name===selectedBoardSector));
        selector.setAttribute("aria-label",r.name+" 근거 "+number(r.evidence_count)+"건 보기");
        const view=btn("보기",()=>choose(r.name),"bct-view-button");
        view.setAttribute("aria-label",r.name+"의 근거 자세히 보기");
        const cRank=el("td",(shared?"공동 ":"")+r.rank+"위","bct-rank-number");cRank.dataset.label="현재";
        const cPrevious=el("td",prev.label);cPrevious.dataset.label="이전";
        const cChange=el("td",prev.change,"bct-rank-change "+prev.tone);cChange.dataset.label="변동";
        const cSector=add(el("td",null,"bct-sector-cell"),selector);cSector.dataset.label="섹터";
        const cCount=el("td",number(r.evidence_count),"bct-evidence-count");cCount.dataset.label="증거 수";
        const cDate=el("td",r.recent_publication?date(r.recent_publication):"날짜 미확인","bct-date-cell");cDate.dataset.label="최근 자료";
        const cView=add(el("td",null,"bct-button-cell"),view);cView.dataset.label="상세";
        tr.append(cRank,cPrevious,cChange,cSector,cCount,cDate,cView);
        tbody.append(tr);
      }
      if(current.length>shownBoardSectors){
        moreSector.append(btn("나머지 "+number(current.length-shownBoardSectors)+"개 산업 더 보기",()=>{
          shownBoardSectors=current.length;renderRanks();
        },"bct-more-button"));
      }else if(shownBoardSectors>10&&current.length>10){
        moreSector.append(btn("상위 10개만 보기",()=>{shownBoardSectors=10;renderRanks();},"bct-more-button"));
      }
      if(!current.length){
        tbody.append(add(el("tr"),add(el("td","아직 산업을 확인한 근거 기록이 없습니다.","bct-empty-rank"))));
        tbody.lastChild.firstChild.colSpan=7;
      }
    }
    function renderSector(){
      detailBody.replaceChildren();
      if(!current.length){
        detailBody.append(el("p","산업이 확인된 근거가 없어 순위를 표시할 수 없습니다.","bct-empty-message"));return;
      }
      const sector=current.find(r=>r.name===selectedBoardSector)||current[0];
      const evidence=boardEvidenceFor(sector.name);
      detailBody.append(add(el("div",null,"bct-selected-sector"),
        add(el("div"),el("span","선택한 섹터","bct-selected-label"),el("strong",sector.name)),
        el("b","근거 기록 "+number(sector.evidence_count)+"건","bct-selected-total")));
      detailBody.append(el("p","먼저 원문 검토 기록을 보여주고, 그다음 공식 표와 제품 탐색 기록을 표시합니다. 각 기록을 눌러 출처를 확인할 수 있습니다.","bct-evidence-intro"));
      const list=el("div",null,"bct-evidence-list");
      for(const r of evidence.slice(0,shownBoardEvidence)){
        const line=el("div",null,"bct-evidence-record");
        line.append(el("span",r.published_at?date(r.published_at):"날짜 미확인","bct-evidence-date"),
                    el("span",boardKinds[r.category],"bct-kind "+r.category));
        const summary=el("div",null,"bct-evidence-description");
        summary.append(el("strong",productLabel(r.product)),el("p",r.role_label+" · "+({reviewed:"원문 검토 · 사람 검증 전",structured:"공식 표 기록 · 실제 공급 확인 전",discovery:"제품 이름 탐색 · 수급 사실 확인 전"}[r.category]||"검토 대기")));
        line.append(summary);
        const show=btn("원문 보기",()=>openDetail(r.id),"bct-evidence-open");
        show.setAttribute("aria-label",productLabel(r.product)+" 원문 근거 상세 보기");
        line.append(show);list.append(line);
      }
      detailBody.append(list);
      if(evidence.length>shownBoardEvidence){
        detailBody.append(btn("근거 "+number(evidence.length-shownBoardEvidence)+"건 더 보기",()=>{
          shownBoardEvidence+=15;renderSector();
        },"bct-more-button bct-evidence-more"));
      }
      detailBody.append(el("p","원문 위치가 확인돼도 수요·공급 관계와 병목 여부는 별도 검증이 필요합니다.","bct-evidence-warning"));
    }
    if(!current.some(r=>r.name===selectedBoardSector))selectedBoardSector=current.length?current[0].name:"";
    renderRanks();renderSector();

    const automation=el("section",null,"bct-first-panel bct-process-panel");
    automation.append(add(el("div",null,"bct-panel-title"),el("span","⚙","bct-panel-icon"),el("h2","자동화와 자료 현황")));
    const stripe=el("div",null,"bct-process-grid");
    const rss=observed.rss;
    const rssOk=rss&&rss.status==="completed"&&rss.conclusion==="success";
    stripe.append(boardStatus("◉","뉴스 자동 수집",rssOk?"최근 수집 성공":rss?"최근 실행 "+(rss.conclusion==="failure"?"실패":"확인 필요"):"실행 기록 없음",
      rssOk?"good":rss&&rss.conclusion==="failure"?"bad":"unknown",
      rss?"실행 "+date(rss.created_at):"최근 예약 실행을 확인할 수 없습니다."));
    const latest=data.latest_source_capture;
    const hasCurrent=latest?.status==="VERIFIED_PUBLIC_SOURCE_INTAKE"&&latest.matches_current_rss;
    const acquired=collection&&collection.counts||{};
    const captureHold=acquired.new_seed_statuses&&Object.entries(acquired.new_seed_statuses).some(([key,n])=>key!=="CAPTURED"&&Number(n)>0);
    stripe.append(boardStatus("▤","기사 원문 확보",
      hasCurrent?(latest.held?"확보 "+number(latest.captured)+"건 · 일부 보류":"확보 "+number(latest.captured)+"건"):
      !collection?"자료 미확인":captureHold?"기존 실행 일부 보류":"기존 실행 확보 기록",
      hasCurrent?(latest.held?"warn":"good"):!collection?"unknown":captureHold?"warn":"good",
      hasCurrent?"최신 수집 "+number(latest.seed_attempts)+"건 처리 · "+number(latest.held)+"건 미확보 · "+date(latest.completed_at):
      collection?"이전 자동 실행 원문 "+number(acquired.new_verified_documents)+"건 · 최신 처리와 구분":"원문 확보 기록 확인 필요"));
    const cpu=observed.cpu;
    const cpuSuccess=cpu&&cpu.conclusion==="success";
    const cpuLabel=cpuSuccess?"최근 예약 성공":cpu&&cpu.conclusion==="failure"?"최근 예약 실패":cpu?"예약 상태 확인 필요":"예약 기록 없음";
    stripe.append(boardStatus("▣","문서 자동 읽기",cpuLabel,cpuSuccess?"good":cpu&&cpu.conclusion==="failure"?"bad":"unknown",
      known(lastStored)?"마지막 결과 저장 "+date(lastStored)+" · 예약 결과와 별도":"결과 저장 시각을 확인할 수 없습니다."));
    stripe.append(boardStatus("⌕","판단 근거 검토",counts.review_pending_windows>0?"검토 "+number(counts.review_pending_windows)+"개 대기":"검토 기록 확인 필요",
      counts.review_pending_windows>0?"warn":"unknown","인용 확인과 공급 부족 판단은 서로 다른 단계입니다."));
    stripe.append(boardStatus("▣","화면 최신화",data.publication&&data.publication.automatic_deployment==="GITHUB_PAGES_ACTIONS"?"공개 화면 반영":"공개 상태 미확인",
      data.publication&&data.publication.automatic_deployment==="GITHUB_PAGES_ACTIONS"?"good":"unknown","화면 생성 "+date(lastPublished)));
    automation.append(stripe);
    page.append(automation);

    const metrics=el("section",null,"bct-first-panel bct-metrics-panel");
    metrics.append(add(el("div",null,"bct-panel-title"),el("span","▥","bct-panel-icon"),el("h2","지금 상태")));
    const metricsGrid=el("div",null,"bct-metrics-grid");
    metricsGrid.append(
      boardMetric("아직 읽지 못한 구간",known(counts.pending_windows)?number(counts.pending_windows):"미확인","확보한 원문을 나눈 구간 기준"),
      boardMetric("원문 미확보",known(counts.held_inputs)?number(counts.held_inputs)+"건":"미확인","아직 읽을 본문이 없는 항목"),
      boardMetric("내용 검토 대기",known(counts.review_pending_windows)?number(counts.review_pending_windows)+"개":"미확인","병목으로 확정된 건수 아님"),
      boardMetric("마지막 화면 반영",date(lastPublished),"실제 게시된 자료 기준"),
      boardMetric("최근 판독 저장",date(lastStored),"결과 저장 완료 시각 · 한국 시간"));
    metrics.append(metricsGrid);page.append(metrics);

    const help=el("section",null,"bct-help-strip");
    help.append(el("span","ⓘ","bct-help-icon"),el("strong","쉽게 보기"),
      el("p","근거 기록이 많은 섹터부터 위에 보입니다. 산업을 누르면 실제 원문 기록을 볼 수 있습니다. 이전 순위는 검증된 지난 공개 화면과만 비교합니다."));
    page.append(help);
    page.append(el("p","※ 기록 건수는 고유한 병목 사건 수가 아닙니다. 아직 확인되지 않은 산업과 새 CPU 제품명 제안은 섹터 순위에서 제외했습니다.","bct-final-disclaimer"));
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
    const list=el("div",null,"mini-list");for(const r of choices){const a=btn("↗",()=>openDetail(r.id),"icon-button");a.setAttribute("aria-label",`${productLabel(r.product)} 근거 열기`);add(list,add(el("div",null,"mini-row"),el("div",r.role.startsWith("DEMAND")?"↗":r.role==="RELIEF"?"↘":"⌁","mini-icon"),add(el("div"),el("b",productLabel(r.product)),el("p",`${r.industry} · ${r.role_label} · ${r.actuality}`)),a));}
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
    const q=s.query.trim().toLocaleLowerCase();const all=recordsFor(page).filter(r=>(page!=="candidates"||r.category==="reviewed")&&(!s.category||r.category===s.category)&&(!s.industry||r.industry===s.industry)&&(!s.role||r.role===s.role)&&(!q||`${productLabel(r.product)} ${r.product} ${r.industry}`.toLocaleLowerCase().includes(q)));
    const pages=Math.max(1,Math.ceil(all.length/12));s.page=Math.min(s.page,pages);const rows=all.slice((s.page-1)*12,s.page*12);
    root.replaceChildren(add(el("div",null,"list-summary"),add(el("span"),el("b",`${number(all.length)}건`),document.createTextNode("의 기록")),el("span",page==="candidates"?"예상 시기는 원문으로 확인된 경우만 표시":"인용 위치 검증과 의미 검증은 별개입니다")));
    if(!rows.length){root.append(empty("조건에 맞는 기록이 없습니다","검색어나 산업·역할 조건을 바꿔 보세요."));return;}
    if(page==="candidates"){
      const wrap=el("div",null,"panel table-panel"),table=el("table",null,"research-table");const tr=el("tr");["산업 · 제품","수요·공급 변화","예상 시기","검증 상태","근거"].forEach(t=>tr.append(el("th",t)));table.append(add(el("thead"),tr));const body=el("tbody");
      for(const r of rows){const tr=el("tr");const product=add(el("td",null,"product-cell"),el("span",productLabel(r.product),"product-title"),el("span",r.industry,"product-meta"));const role=add(el("td"),el("span",r.role_label,"cell-main"),badge(r.actuality,r.actuality==="계획"?"amber":""));role.dataset.label="변화";const time=add(el("td"),el("span",r.period,"cell-main"),el("span",`공개 ${date(r.published_at)}`,"product-meta"));time.dataset.label="예상 시기";const status=add(el("td"),badge(displayStage(r.stage),r.stage==="S1"?"green":""),el("p","원문 AI 검토 · 사람 검증 전","product-meta"));status.dataset.label="검증 상태";tr.append(product,role,time,status,add(el("td"),detailButton(r)));body.append(tr);}table.append(body);wrap.append(table);root.append(wrap);
    }else{
      const grid=el("div",null,"evidence-grid");for(const r of rows){const card=el("article",null,"evidence-card");add(card,add(el("div",null,"card-meta"),badge({reviewed:"별도 원문 검토",structured:"공식 표의 변화",discovery:"제품 탐색 · 검토 대기",cpu_product:"CPU 제품 표기 · 의미 검증 전",reported:"보도 검토 · 공식 1차 확인 전"}[r.category],r.category==="reviewed"?"green":r.category==="structured"?"blue":"amber"),el("span",r.industry)),el("h3",productLabel(r.product)),el("p",`${r.role_label} · ${r.actuality}`),add(el("div",null,"card-bottom"),el("span",known(r.published_at)?`공개 ${date(r.published_at)}`:"공개일 확인 필요"),detailButton(r,"원문 대조")));grid.append(card);}root.append(grid);
    }
    if(pages>1){const p=el("div",null,"pagination");const prev=btn("← 이전",()=>{s.page--;renderList(page);});prev.disabled=s.page===1;const next=btn("다음 →",()=>{s.page++;renderList(page);});next.disabled=s.page===pages;p.append(prev,el("span",`${s.page} / ${pages} 페이지`),next);root.append(p);}
  }
  const stateLabel=s=>({UNREAD:"미판독",PARTIAL:"부분 판독",FAILED:"처리 실패",SOURCE_VERIFICATION_PENDING:"원문 검증 대기",GRAPH_CONTEXT_PENDING:"독립 근거 문맥 대기",READ_EVIDENCE_HOLD:"판독 후 근거 보류",NO_VALIDATED_EVENT:"검증된 사건 없음",RESEARCH_FORECAST_REVIEW:"연구 후보 검토",READ_COMPLETE:"판독 범위 완료"}[s]||s);
  const workflowStateLabel=s=>({success:"성공",failure:"실패",skipped:"실행 안 함",cancelled:"취소됨",timed_out:"시간 초과",queued:"대기 중",in_progress:"실행 중",completed:"종료됨",waiting:"대기 중",pending:"대기 중",action_required:"확인 필요",neutral:"판정 없음",stale:"오래된 실행"}[s]||"상태 미확인");
  function workflowLabel(row){if(!row)return "상태 미확인";return `${workflowStateLabel(row.conclusion||row.status)} · 실행 ${row.id}`;}
  function cpuWorkflowLabel(row){if(!row)return "작업 상태 미확인";return `판독 작업 ${workflowStateLabel(row.processing_jobs?.research)} · 저장 작업 ${workflowStateLabel(row.processing_jobs?.publish)}`;}
  function operatingSummary(){
    const r=data.operating_research,c=data.collection_observation,p=panel("현재 자동화 관측","수집 기록과 CPU 저장 세대는 각자의 실행 번호로 구분합니다.",link("처리·보류 상태 보기 →","#automation"));
    p.append(add(el("div",null,"stats-grid"),stat("최근 발견 URL",c?.counts.new_URLs,"마지막 수집 관측 · CPU 판독 수와 별도","▤"),stat("이번 저장 세대 신규 판독",r?.counts.new_CPU_windows,"실제 모델 판독 시도 창 · 검증 성공과 별도","◫","창"),stat("검증 성공 창",r?.counts.successful_new_CPU_windows,"실제 성공한 새 창만 집계","✓","창"),stat("미판독 대기 창",r?.counts.pending_windows,"저장된 CPU 대기열 기준","◷","창")),el("p",`최근 수집 ${date(c?.collection_started_at)} · 실제 판독 시도 ${date(r?.clocks.last_read_at)} · 영속 저장 ${date(r?.clocks.persisted_at)}. 과거 상세 연구 기준 ${date(data.historical_data_at)}는 별도 보존합니다.` ,"section-note"));content.append(p);
  }
  function operatingAutomation(){
    const r=data.operating_research,c=data.collection_observation,w=data.workflow_observation?.workflows||{},n=r?.counts,b=r?.last_read_batch;
    if(data.public_transport&&data.public_transport.pending_reason!=="NONE")content.append(el("p",`공개 요약 연결 확인 대기 · ${data.public_transport.pending_reason}. 확인된 저장 세대는 보존하며, 대기 중인 실행을 완료로 세지 않습니다.`,"notice"));
    const newest=data.latest_source_capture;
    if(newest?.status==="VERIFIED_PUBLIC_SOURCE_INTAKE"){
      const p=panel("최신 기사 원문 확보 실행 · 실제 저장 확인",
        "최신 RSS와 연결되는 수집 실행과 자동 실행으로 수집된 과거 자료를 구분합니다.");
      const statusNames={CAPTURED:"원문 확보",PROVENANCE_BLOCKED:"출처 보류",
        HTTP_403:"접근 거부 403",TIMEOUT:"시간 초과",NETWORK_FAILED:"네트워크 실패",
        CONNECT_BLOCKED:"연결 차단"};
      p.append(add(el("div",null,"stats-grid"),
        stat("이번 원문 확보 시도",newest.seed_attempts,"RSS 수집 기사 중 새로 처리한 건수","▤"),
        stat("원문·출처 확인",newest.captured,"원문 확보 · 병목 근거 확정 아님","✓"),
        stat("원문 미확보·보류",newest.held,"원출처 확인 또는 네트워크 장애","!"),
        stat("추가 독립 1차 자료",newest.valid_additional_primary_documents,"검증된 반대편 근거 문서 수","◷")));
      p.append(el("p","저장 "+date(newest.completed_at)+" · "+(newest.source_event==="workflow_dispatch"?"요청 실행":"자동 연동")+" · "+
        (newest.matches_current_rss?"현재 최신 RSS 수집과 일치":"이후 RSS 수집이 더 존재함"),"section-note"),
        el("p",Object.entries(newest.statuses||{}).map(([k,n])=>(statusNames[k]||k)+" "+number(n)+"건").join(" · "),"section-note"),
        el("p","기존 자동 원문 확보 기록 "+date(c?.completed_at)+"과 별개입니다. 최신 원문을 기존 산업 순위의 증거 수에 자동 추가하지 않습니다.","section-note"));
      const origin=external("실행 내역 보기","https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/"+newest.source_run_id);
      if(origin)p.append(origin);
      content.append(p);
    }
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
      const title=el("h2",productLabel(r.product));title.id="detail-title";body.append(title,add(el("div",null,"detail-status"),badge(r.status,r.category==="reviewed"?"green":"amber"),badge(displayStage(r.stage)),badge(r.actuality)));
      const originalName=el("details");originalName.append(el("summary","원문에 적힌 제품명 확인"),el("p",value(r.product)));body.append(originalName);
      if(r.category==="discovery"||r.category==="cpu_product")body.append(el("p","제품명과 역할은 CPU가 제안한 값입니다. 수요·공급 사실로 채택하지 않은 탐색 기록입니다.","notice"));
      body.append(kv([["산업",r.industry],["제품",productLabel(r.product)],["제품 규격",r.target.specification],["지역",r.target.region],["고객",r.target.customer_group],["공급자 범위",r.target.supply_pool],["예상 병목 시기",r.period],["고객 필요 시기",r.need_time],["공급 준비 시기",r.ready_time],["근거의 대상 기간",r.evidence_period]]));
      body.append(el("p",`${r.industry_basis} 제품명은 읽기 쉬운 한글 표시명을 함께 사용합니다. 원문 제품명·규격·지역·고객·공급자·인용 내용은 바꾸지 않고 보존합니다.`,"caption"));
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
