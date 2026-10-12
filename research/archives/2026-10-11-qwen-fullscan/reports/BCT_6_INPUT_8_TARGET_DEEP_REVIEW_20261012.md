# BCT 4차 공식 근거 심층검증 — 6개 입력 항목, 8개 독립 TARGET

- **검증 기준일:** 2026-10-12 (Asia/Seoul)
- **BCT horizon:** 2027-10-12 ~ 2029-10-12 (향후 12–36개월)
- **저장 목적:** 연구 원장 및 후보 재검토 조건 보존. 운영 후보/알림/코드 자동 변경 금지.
- **결과:** 공식 계약·생산계획 확인, **독립 DEMAND + 적격 CAPACITY + NEED/READY 비교로 증명된 S3=0, EARLY=0**.
- **대상 식별 정정:** RTX SM-6 / SM-3 Block IB 별도, 스페인 El Moto / 영국 Hemerdon→미국 Elmet 별도. 6개 입력 행에서 실제 8개 TARGET이 됨.
- **증빙 해석:** 계획·계약·임대 전력은 실제 가동/출하·최종검수와 구분. 신규 생산계약은 shortage뿐 아니라 RELIEF를 의미할 수 있음. 모델 판독만으로 PASS 불가.
- **불확실성:** 본 조사에서 기존 BCT 캐시 원문 해시와 새 공식 자료의 바디 SHA 일치 여부를 검증하지 않았음. 인용 URL의 발표일이 최초 전세계 선행 이벤트 발생일임을 보증하지 않음.

## 판정 요약

| 식별 TARGET | 공식 수요 신호 | 공급·준비 신호 | 일치하는 적격 공급부족(S3) | horizon / 판단 |
|---|---|---|---|---|
| BRUN→Cohere GB300 NVL72 rack | $525.6M 2026-09-30 서비스계약 | 2027 Q2 초기 인수 예상·2027-07-15 인수 외부기한, GPU/랙 수량 미공개 | **미입증** | 기한 12개월 미만, 공급 납기 리스크; S2 불완전 |
| AIB CLT1→Nebius 50MW critical IT | 12년 임대 계약(2026-09-30) | 65MW utility ESA, 25MW hall~2027-08 +25MW~2027-12 회사 목표, 프로젝트 대출 미조달 | **미입증** | 2027-12는 horizon 내; 완공·전력 인가·자금조달 리스크 |
| Elevra NAL→LGES 스포듀민 정광 | 240,000 dmt 기본 공급: CY26 30k/CY27 60k/CY28 60k/CY29 90k; 최대 90k 추가 옵션 미확정 | NAL FY26 실제 197,967 dmt, FY27 198–210k dmt 전망, 증설 Stage1 mid-CY27 / Stage2 mid-CY28 / Stage3 mid-CY29, 장기 373ktpa 예상 | **미입증** | 기존생산+증설 공급확보/RELIEF; FY와 CY 혼합 산술 금지 |
| GFS→TSMC CoWoS 인터포저 | 5년 $2B 제조계약(2026-10-08) | NY Malta H1 2028 ramp 목표; 월 웨이퍼 수량·양품률·qualification 미공개 | **미입증** | 새로운 미국 공급원/RELIEF; CoWoS shortage 이미 2024년 공개 |
| RTX SM-6 interceptor | 최대 $24.4B / 5년+2년 옵션 | 2026-02-04에 연 500발 초과 향후 생산목표 발표; 현재 실출하/연도별 조달량 미공개 | **미입증** | 현재 shortage의 후속 계약, 새로운 EARLY 아님 |
| RTX SM-3 Block IB | 최대 $6.3B / 5년+2년 옵션 | 생산·군수지원 계약, 제품별 실제 연간 확정 주문·산출 미공개 | **미입증** | SM-6 수량과 통합 금지, 새로운 EARLY 아님 |
| 스페인 Abenójar El Moto tungsten WO3 | 2026-10-03 Traxys가 정광 100% 장기 구매(take-or-pay), 10년 이상 | Q1 2029 초기 생산 목표, steady >4,200 t WO3/y (422,656 mtu = 약 4,227 t), 2031 단계 확대; 주요 허가 확보, 자금 일부 조건부 | **미입증** | 2029 신규 공급원/RELIEF; 아직 상업가동 전 |
| UK Tungsten West Hemerdon→US ELMT | Elmet과 8년 1,000 t/y contained WO3 인수; 추가 500t/y는 조건부 가공 추진 | Hemerdon 2026-09 최초 광석처리, Q1 2027 풀시운전·H2 2027 정상 생산 목표. ELMT의 APT 실제 정제 적격 capa 미공개 | **미입증** | 비중국 공급원/RELIEF; El Moto와 직접 구매계약 관계 증명 없음 |

## 원문 기준 상세 근거 및 재개 조건

### T1 BRUN/Cohere — GB300 NVL72
- **공식 원문:** SEC 8-K (2026-10-06) https://www.sec.gov/Archives/edgar/data/2090646/000149315226045861/form8-k.htm
- **실제 계약 첨부:** https://www.sec.gov/Archives/edgar/data/2090646/000149315226045861/ex10-1.htm
- NDA로 일부 물량·임계기준 삭제. 고객 인수검사에는 NVIDIA 레퍼런스 아키텍처, NCCL, LLM 벤치마크 관련 보고가 명시됨.
- **다음에만 재개:** 확정 GB300 rack/GPU 수량과 납품 장소; 확보·실제 가동 클러스터 수량; RFT/acceptance 기록; 2027-07-15 일정 변경 공식 근거.
- **부정조건:** 실제 인수 수량 정상 달성 시 공급부족 후보화 금지.

### T2 AIB CLT1/Nebius — critical IT 50MW
- **공식 계약 발표:** https://www.sec.gov/Archives/edgar/data/2070542/000121390026105865/ea030737801ex99-1.htm
- **SEC 투자자 프레젠테이션:** https://www.sec.gov/Archives/edgar/data/2070542/000121390026105249/ea030723301ex99-1.htm
- 전력회사 65MW(utility load)는 GPU IT 50MW와 다른 측정 위치/단위 정의이며 차이 15MW를 공급부족으로 계산하면 안 됨.
- 2026-10-01부터 약 10개월/14개월 이후 25MW씩 인도 예정. 자금조달 예시의 $800M cost·부채/우선주 배분은 ILLUSTRATIVE, 대출 실제 조달확정 증거 아님.
- **다음에만 재개:** 확정 대출/자금납입, 건축 허가·현장 진행, 통전·검수 완료, hall별 실제 고객 인수·임대료 개시와 약정 기한 비교.

### T3 ELVR NAL/LGES — spodumene concentrate
- **공식 수요 원문:** https://www.sec.gov/Archives/edgar/data/1739016/000114036126039136/ef20083536_6k.htm
- **실제 공급 생산량 및 FY27 전망:** https://www.sec.gov/Archives/edgar/data/1739016/000114036126035094/ef20081294_ex99-4.htm
- **NAL 증설 PFS:** https://rss.globenewswire.com/news-release/2026/09/08/3358137/0/en/elevra-lithium-announces-nal-expansion-pre-feasibility-study.html
- 240,000은 dmt 정광 총량, 탄산리튬환산량·원소리튬량 아님. 공급계약은 3-year term이라 표기하지만 2026~2029 네 달력연도에 물량 배정됨.
- FY26/FY27 생산·판매 연도와 LGES CY 계약 연도를 무비판적으로 빼서 공급 잔량 계산 금지.
- **다음에만 재개:** 월별 실제 출하량, 잔여 다른 고객 확정계약, 같은 SC grade의 운송/정제 경로와 stage 1/2/3 지연 근거.

### T4 GFS→TSMC — CoWoS interposer
- **공식 계약:** https://gf.com/news-and-events/news/globalfoundries-reaches-agreement-to-establish-us-based-supply-of-silicon-interposers-for-advanced-ai-packaging/
- **선행 shortage 이미 보도:** https://www.trendforce.com/news/2024/02/19/insights-cowos-capacity-shortage-challenges-ai-chip-demand-while-taiwanese-manufacturers-expand-to-seize-opportunities/
- 원문상 CoWoS ecosystem의 silicon interposer, embedded deep trench capacitor 관련 언급; 최종 CoWoS 패키징 조립이나 CoWoS 전 규격을 GF가 공급하는 것으로 확대해석 금지.
- **다음에만 재개:** 동일 인터포저 세대/규격별 TSMC 요청 웨이퍼 수, GF 실제 양품률 및 qualified 월간 output, 2028~29 need-ready 비교, 여타 적격 공급원.

### T5/T6 RTX SM-6 / SM-3 Block IB
- **2026-02 사전 공개 증산계획:** https://www.rtx.com/news/2026/02/04/munitions-agreements
- **SM-6 2026-10 발표:** https://www.rtx.com/news/news-center/2026/10/01/rtxs-raytheon-awarded-24-4-billion-multi-year-contract-for-sm-6-interceptors
- **SM-3 IB 2026-10 발표:** https://www.rtx.com/news/news-center/2026/10/08/rtxs-raytheon-awarded-6-3-billion-multi-year-contract-for-sm-3-ib-interceptors
- `up to` 계약액은 현금 수령액·실제 발주 확정량 아님. SM-6 planned >500/y는 현재 달성 수량이 아님. SM-3 IIA 별도 체계와 혼합 금지.
- **다음에만 재개:** 미 해군/미사일방어청 각 탄종별 FY27–FY29 funded procurement quantities, 실제 생산/납품, 구성부품 certified capacity와 production slots, 최초 shortage 보도시각 검증.

### T7 스페인 El Moto→Traxys
- **2026-08 DFS:** https://abtungsten.es/en/2026/08/05/abenojar-tungsten-announces-results-of-el-moto-2026/
- **2026-10 전량 장기 오프테이크:** https://abtungsten.es/en/category/press/
- **2026-10 IPO 의향·허가·조건부 자금조달 공시:** https://www.lse.co.uk/rns/intention-to-float-ox0df9ho30wliej.html
- 422,656 **mtu**는 약 4,227 **tonnes WO3**이며 42만톤이 아님. Q1 2029 최초 생산과 steady-state 이후 연 4.2kt를 혼동 금지. Traxys가 전체 정광 구매자, Elmet의 직접 구매로 매핑 금지.
- **다음에만 재개:** 확정 자금조달·갱도/플랜트 진척·Q1 2029 최초 실제 출하, 타 지역 적격 APT 환산 능력과 시차.

### T8 영국 Hemerdon→ELMT
- **영국 광산측 8년 계약 상세:** https://www.lse.co.uk/rns/strategic-tungsten-supply-and-offtake-agreement-oqvcvuui6u6kzx7.html
- **미국 ELMT 발표:** https://investors.theelmetgroup.com/news-events/press-releases/detail/170/the-elmet-group-secures-long-term-tungsten-offtake-agreement-with-tungsten-wests-hemerdon-mine
- **광산 실제 초기 재가동(2026-09):** https://www.investegate.co.uk/announcement/rns/tungsten-west--tun/processing-operations-commence-during-visit-by-nwf/9771557
- **광산 증산 계획:** https://www.tungstenwest.com/project/hemerdon-mine
- 계약 기준 WO3 함유량 연 1,000t, 추가 500t는 별도 조건부 가공 추진이지 확정 수요·판매량 아님. APT/refining 전환 capacity·양품률 별도 대상.
- **다음에만 재개:** 연도별 실광석·정광 생산, Elmet 인수·APT 정제 수율/월간 톤, 고객별 QUALIFIED 중간재 수요 및 기한 비교.

## BCT 강제 게이트 — 결론

- 새로 확인된 건은 **계약/미래 생산능력/계획**이지 같은 TARGET에 대한 **적격 공급 부족의 계산·실증이 아니다**.
- **S3 VERIFIED: 0 / EARLY VERIFIED: 0**. 운영 FUTURE/EMERGING/OBSERVE 자동 판정 변경 금지.
- 2026-10-12 시점에 12개월 내 마감(예: Cohere 2027-07)은 BCT 고정 예측창 밖으로 별도 표기.
- 2028 CoWoS는 이미 2024 shortage 기사 존재; 2026 계약은 'shortage-first EARLY' 근거로 쓰지 않음.
- 다음 연구는 동일 사양·공급자·지역·고객·need/ready·수량의 **독립 수요·공급 공식자료 두 세트**가 신규로 충족될 때만 검토 재개.
- 원본 자동화 코드·후보 원장·예측 등급·알림은 변경하지 않는다.
