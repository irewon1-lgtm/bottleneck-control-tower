# CPO FAU attach / active alignment 적격 처리능력 재조사

기준일 2026-10-06. TARGET `cpo-fau-qualified-attach-alignment`. 최종 **REVIEW_LEAD**. 기업·주가 분석은 수행하지 않았다. 조사 창은 CY2027·2028·2029이며, 공급 지역은 미국 AI 데이터센터에 투입 가능한 전세계 고객인증 공급망이다.

**CPO 제품의 생산 진입과 정렬 공정 부담은 확인된다. 그러나 같은 고객·설계·기간의 필요한 합격 attach 처리량이 가동 가능한 적격 양품 처리량보다 크다는 수량·납기 증거는 없다.** 기존 판정을 전제로 하지 않고 원문을 재확인했으며 승격하지 않았다. 없다는 증거도 아니므로 DROP하지 않는다.

## 연도별 수요와 ramp

| 연도 | 원문에서 확인한 내용 | 수요 확정성 / 제한 |
|---|---|---|
| 2027 | NVIDIA는 2026-05-31 Spectrum-X Ethernet Photonics 생산 진입과 초기 채택자를 발표[S01]. TSMC도 COUPE on substrate 2026 생산 계획[S06]. Ayar CEO는 2027년 말까지 양산 인증 목표[S07]. | 기존 switch 제품의 2027 확대는 합리적 가능성이나 확정 주문량은 UNKNOWN. Ayar 인증 목표는 생산 완료·확정 수요가 아님. |
| 2028 | Ayar CEO가 고객제품의 2028~2029 ramp를 설명[S07]. NVIDIA는 Rubin Ultra/Kyber의 직접 광연결 로드맵을 공개[S03]. | 고객 계획. 미국향 CPO 수량·필요일·BOM은 UNKNOWN. 직접 광연결을 모든 링크의 CPO로 간주하지 않음. |
| 2029 | 같은 Ayar 고객 ramp 창에 포함[S07]. | 별도의 2029 수량 계약·attach 물량표 없음. 2028 전망을 기계적으로 늘리지 않음. |

NVIDIA 초기 채택 발표는 구매 계약표가 아니다. Broadcom TH5-Bailly는 회사가 양산과 부품 출하를 발표[S04]했지만 Davisson의 2025-10-08 발표는 sampling 상태[S05]다. 특정 문서 날짜의 상태를 최신 전체 출하량으로 바꾸지 않는다. Lightmatter의 Q1 2027 CPX 평가 키트는 **NPO**[S20]로, 이 TARGET의 확정 CPO 수량에 합산하지 않았다.

## 구조·작업횟수

| 공개 설계 | 확인된 광학 구조 | attach 작업량으로 바꿀 때 빠진 정보 |
|---|---|---|
| Quantum-X | ASIC당 6 subassemblies × 3 OE = 18 OE. OE당 Tx8/Rx8/laser input2 fibers. Q3450은 ASIC4개[S02]. | 산술상 ASIC당 324, chassis당 1,296 fiber 연결 경로. 이는 개별 active 정렬 횟수나 FAU attach 횟수가 아님. 어레이·렌즈 그룹·고정 공정 분할·검사 재접속 정보 필요. |
| Spectrum-X | 패키지당 32 OE, OE당 Tx16/Rx16 lanes, wafer microlens 및 detachable optical connector[S02]. | 엔진당 FAU/MLA/receptacle 수·공정 순서·초기 정렬/후속 passive mating 구분 UNKNOWN. |
| TH6-Davisson | 16 × 6.4T OE, 200G/lane[S05]. | OE 수는 확인되지만 attach cycle 수 UNKNOWN. |
| PICAlign 일반 사례 | SENKO 등은 CPO module이 100회 이상 active 정렬을 요구할 수 있다고 설명[S09]. | 특정 NVIDIA/Broadcom BOM의 확정 작업수·출하량이 아니다. 복수 채널 동시 정렬과 detachable 우회 반영 필요. |

Passive는 기하 기준/비전/맞물림으로 위치를 맞추며, active는 실제 광학 피드백을 사용한다. Passive 사전 정렬 뒤 active 미세 정렬을 할 수도 있다[S12]. FAU 한 개의 많은 fiber 채널이 여러 자유도와 함께 최적화될 수 있다[S13]. 따라서 fiber 수 × 순차 정렬 초 단위 계산을 기본 수요식으로 쓰지 않았다.

## 적격 처리능력의 증거 수준

| 공급자·공정 | 실제 공개 단서 | 인증/처리능력 판독 |
|---|---|---|
| 제품 양산 공급망 | NVIDIA 생산 진입, Bailly 양산·부품 출하[S01,S04] | 생산 공급망의 존재는 확인. 특정 attach recipe·사이트별 release·양품 UPH·잔여 CAPA UNKNOWN. |
| ADST | 회사 IR에서 CPO 제품 이력, 연구/파일럿 주문 및 납품. UPH 13→40[S14] | UPH 대상 유닛·recipe·수율·cure/test 포함 여부와 고객 HVM 승인 미공개. 40 × 장비 수를 적격 CAPA로 계산하지 않음. |
| ficonTEC ASSEMBLYLINE | 산업 검증 플랫폼·누적 설치 1,000대 이상. TESTLINE 정렬 max4초[S11] | 누적 대수는 여러 산업/장비 합계. 4초는 검사 포트 정렬로 attach cycle과 다름. 특정 CPO 고객별 인증 표 없음. |
| Aerotech/Santec/SENKO | PICAlign debut, <1초 최적 정렬 성능[S09] | 부분 정렬 benchmark. 양산 acceptance·장비 수·accepted output 미확인. |
| PI | 병렬 다채널 정렬 <0.6초[S13] | 부분 subsystem 성능. 실제 고객 전체 cycle·양품 CAPA 아님. |
| Suruga / FitTech | OFC 전시·EW stages, 기존 범용 SiPh 양산 장비 공급 주장, FAS passive/active FAU-PIC 제품[S16,S17] | 제품/데모. 고객별 가동 CAPA 미확인. |
| ASMPT | bulk orders는 1.6T transceiver. CPO는 FAU/MLA/EIC/PIC 고객 engagement[S15] | 발주 범위를 분리. CPO attach 예약 CAPA 증거 아님. |
| AIXEMTEC | cleaning/AOI/align/bond/cure/test 및 recipe 복제 라인 설명[S18] | 고객 수용 기준과 공정은 설명. named-customer 양산 인증·대수·UPH·수율 미공개. |

**확인 가능한 고객인증 처리량 수치: UNKNOWN.** 일부 실제 제품 생산이 확인된다는 의미와, 2027~2029 추가 고객에게 배정 가능한 합격 interface/월이 확인된다는 의미는 다르다.

## 실제 제한 단계와 수율·재작업

1. load·cleaning·비전 pre-alignment → first-light·dry/wet active alignment → dispense/bond → UV lock·thermal post-cure → 위치/광성능 검사 → electrical/optical test가 확인할 흐름이다[S12,S18]. 모든 설계가 동일 순서를 사용하는 것은 아니다.
2. 가장 구체적인 하위 검토 항목은 **정렬을 유지하며 접합하고 post-cure 이후 모든 채널의 광학 기준을 통과시키는 단계**다. 접착 수축·열적 변형·응력 이완이 초기 최적 위치를 바꿀 수 있다[S18]. 이는 품질 과제의 증거이며 현재/미래 queue 부족 증거는 아니다.
3. 양품 UPH는 재탐색 횟수, 각도/채널 최적화, fixture 점유시간, cure 이후 재작업·탈락, 검수 결과에 좌우된다. 공개된 반복 횟수·수율·재작업률은 UNKNOWN. 전체 설계에 임의 수율을 대입하지 않았다.
4. cure가 길어도 오븐이 병렬 batch 처리하면 alignment station보다 느린 공급 단계라는 결론은 나오지 않는다. batch size/dwell/ovens와 버퍼 데이터가 필요하다. laser weld는 본 CPO FAU BOM의 필수 여부부터 UNKNOWN이며 OCS 용접 사례를 혼용하지 않았다.
5. SENKO/Advantest/VIAVI의 40 UPH × 24 × 30 예시는 **simulated module testing**[S23]. 실제 attach 공장 28,800개/월 공급량으로 기록하지 않았다. 검사는 이미 있는 `cpo-optical-electrical-volume-test`와 관련만 연결했다.

Active alignment, cure, weld, inspection 각각을 이 history의 `subprocess_observations`에 기록했다. **지배적인 제한 단계는 미확정이며 신규 하위 TARGET을 만들지 않았다.**

## 예약·납기·증설

공개 고객별 주문/예약 장비 수, 생산라인 배정, 잔여 qualified slots는 UNKNOWN이다. 2026-08-05 서울경제 원보도는 성호전자가 ADST의 C사 CPO active alignment 장비 $16.45M PO를 발표했다고 전한다. 기사 본문은 확인했으나 발주서/회사 원문은 확보하지 못해 `unverified_order_leads`로 분리했다. 주문액에서 장비 수·납품일·production acceptance·잔여 CAPA를 산출하지 않고 C사 이름도 추정하지 않았다. [주문 단서](https://en.sedaily.ai/finance/2026/08/05/sungho-electronics-unit-ads-tech-wins-235-billion-won-order). ADST의 연구·pilot 매출/장비 공급과 ASMPT의 transceiver bulk orders는 CPO 고객의 공급 부족 또는 미예약 슬롯 0을 뜻하지 않는다.

발주 → 제조/조달 → FAT → 운송/설치 → SAT → 공정 수율 안정화·신뢰성 시험 → 고객 production release의 각 날짜와 기간이 필요하다. 본 TARGET에서 사용할 원문 기반 정량 lead time은 확보되지 않았다. 다른 die-bonder나 transceiver 장비의 일반 납기를 CPO FAU 양산인증 lead time으로 가져오지 않았다. 과거 RoboTechnik draft의 주문 기준 SiPh 장비 생산 개수·인수 전 제외 주석[S24]도 현 CPO 가동 대수로 사용하지 않았다.

## Relief와 반증

| 경로 | 확인된 진전 | 실제 relief 시점/규모 |
|---|---|---|
| GF–SENKO SEAT/MPC | 최초 microlens active 정렬 후 후속 조립은 passive mating 가능[S10] | 2025 발표·전시. 특정 미국 고객 CPO 인증·처리량은 UNKNOWN. 초기 active 작업은 남음. |
| Lightmatter vClick | wafer 단계로 인터페이스 이동, ASE packaging 호환성 시연, production fiber active 정렬 우회 주장[S19] | 2026 공개. 보편적으로 모든 초기 정렬이 사라지는 것은 아님. 고객별 양산 CAPA UNKNOWN. |
| NVIDIA microlens/detachable | 공개 제품 설계에서 시간/정렬 민감도 축소와 자동조립 지원[S02] | 이미 설계에 반영. 2027~2029 추가 양품량은 UNKNOWN. |
| 병렬 정렬·복제 라인 | PI parallel optimization, PICAlign, recipe와 slots 복제 설명[S09,S13,S18] | 도입·인증 날짜 및 개선 양품 UPH UNKNOWN. |
| 장비 제조 투자 | ficonTEC 2026-09 IPO 후 제조/서비스 확대 계획[S22] | 투자 계획이며 납품/설치/고객 인증 투입일 UNKNOWN. |
| NPO/BiDi/수요 순연 | CPX NPO 평가 일정 및 fiber intensity 완화 모델[S20] | 특정 고객 attach 수요와 채택으로 검증해야 함. 양산증명/완전한 대체로 처리하지 않음. |

동일 SKU·월의 확정 주문량이 배정된 post-cure 양품 output을 초과하고 가장 빠른 대체/인증 증설 납기가 필요일 이후라면 강화할 수 있다. 반대로 passive/detachable 채택, 수요 순연, 재고, recipe 개선이나 복제 라인의 실제 고객 승인·양품 output으로 필요일을 충족하면 해당 shortage 가설은 반증된다.

## 비교 결과·다음 확인 자료

| 연도 | 필요한 적격 attach 처리량 | 가동 가능한 적격 양품 처리량 | 신규 미배정 주문 / 잔여 슬롯 | 충돌 |
|---|---|---|---|---|
| 2027 | UNKNOWN | UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN |
| 2028 | UNKNOWN | UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN |
| 2029 | UNKNOWN | UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN |

수요식은 같은 고객·BOM·월의 확정 CPO 수량 × 필요한 interface 작업수다. 공급은 고객/site/SKU별 인증 station × 가동시간 × 실제 accepted UPH로, 공정별 공유 배정과 재작업·downstream blocking을 반영한다. Cure·검사를 같은 output 단위로 맞춰 flow capacity를 비교한다. 이미 yield를 반영한 accepted UPH에 다시 yield를 곱하지 않는다. 총 예약 수요는 그에 배정된 공급과, 신규 미배정 수요는 잔여 미예약 공급과 각각 비교한다.

결정적 누락은 연도·월별 firm need, BOM 작업수, customer recipe release, 전체 cycle, 실제 장비/라인 수, 양품수율/OEE/재작업, 예약·잔여 배정 및 증설 qualification 날짜다. 제품 로드맵과 공급자 benchmark만으로 이를 채우지 않았다.

## 원문 목록 및 검증 한계

상세 문서 ID·발행일·위치·짧은 인용·SHA256·판독은 `sources.json`, 추가 판정은 `history-append.json`, 적용 patch는 `../20261006-cpo-fau-attach-alignment-deep.json`에 있다. 원문 자료는 제한된 발췌로 저장하여 PARTIAL로 표시한다. 전체 웹문서의 불변 snapshot 또는 선행탐지 성과를 주장하지 않는다. 고객 비공개 계약/라인 로그는 확보되지 않았으며 공개자료 범위를 넘어 추정하지 않았다. ADST 자료는 회사가 작성한 IR의 미러이며 회사 주장으로 분류했다. Ayar 시기는 CEO의 Reuters 원인터뷰 재전재를 사용했다.

| 번호 | 출처 |
|---|---|
| S01 | [NVIDIA 생산 발표](https://nvidianews.nvidia.com/news/vera-rubin-full-production-agentic-ai-factory) |
| S02 | [NVIDIA CPO 구조](https://developer.nvidia.com/blog/how-industry-collaboration-fosters-nvidia-co-packaged-optics/) |
| S03 | [NVIDIA Rubin POD](https://developer.nvidia.com/blog/nvidia-vera-rubin-pod-seven-chips-five-rack-scale-systems-one-ai-supercomputer/) |
| S04 | [Broadcom Bailly/200G](https://investors.broadcom.com/news-releases/news-release-details/broadcom-announces-third-generation-co-packaged-optics-cpo) |
| S05 | [Davisson 발표 PDF](https://investors.broadcom.com/node/63626/pdf) |
| S06 | [TSMC 2026 기술발표](https://pr.tsmc.com/chinese/news/3302) |
| S07 | [Reuters Ayar CEO 인터뷰](https://kfgo.com/2026/09/10/ayar-labs-backed-by-chip-giants-extends-funding-round-by-150-million/) |
| S08 | [Ayar 제조준비 투자](https://ayarlabs.com/news/ayar-labs-expands-2026-funding-to-650-million/) |
| S09 | [PICAlign 발표](https://www.senko.com/aerotech-santec-and-senko-unveil-advanced-active-alignment-architecture-for-high-volume-co-packaged-optics/) |
| S10 | [SENKO–GF active/passive 구조](https://www.senko.com/senko-and-globalfoundries-achieve-breakthrough-in-wafer-level-detachable-fiber-interface-and-optical-testing-for-co-packaged-optics/) |
| S11 | [ficonTEC 플랫폼](https://www.ficontec.com/machine-platforms/) |
| S12 | [ficonTEC 공정](https://www.ficontec.com/capabilities/) |
| S13 | [PI parallel alignment](https://www.pi-usa.us/en/expertise/parallel-active-fiber-optics-alignment) |
| S14 | [ADST 회사 IR PDF](https://file.alphasquare.co.kr/media/pdfs/company-ir/20260518%EC%84%B1%ED%98%B8%EC%A0%84%EC%9E%90_2026%EB%85%84_1%EB%B6%84%EA%B8%B0_%EA%B2%BD%EC%98%81%EC%8B%A4%EC%A0%81_%EB%A6%AC%EB%B7%B0.pdf) |
| S15 | [ASMPT Q1 원문](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0422/2026042200021.pdf) |
| S16 | [Suruga 공지](https://eng.surugaseiki.com/news/) |
| S17 | [FitTech FAS](https://zh-tw.fittech.com.tw/photonic-device-assembly-system) |
| S18 | [AIXEMTEC 공정라인](https://aixemtec.com/applications/cpo-optical-interface-assembly-test-aixemtec) |
| S19 | [Lightmatter vClick](https://lightmatter.co/press-release/lightmatter-unveils-vclick-optics-industry-first-detachable-fiber-array-unit-for-cpo-advanced-packaging-and-high-volume-production/) |
| S20 | [Lightmatter NPO/CPX](https://lightmatter.co/press-release/lightmatter-joins-open-cpx-msa-introduces-the-industrys-first-bidirectional-cpx-optical-engine/) |
| S21 | [Corning OMS](https://www.corning.com/optical-communications/worldwide/en/home/the-signal-network-blog/why-scalable-cpo-must-be-built-as-a-system.html) |
| S22 | [ficonTEC 투자계획](https://www.ficontec.com/robotechnik-hong-kong-listing-enables-ficontecs-next-phase-of-growth/) |
| S23 | [SENKO simulated test](https://www.senko.com/senko-advantest-and-viavi-collaborate-to-address-a-hidden-bottleneck-in-cpo-module-level-testing/) |
| S24 | [RoboTechnik 과거 draft](https://www1.hkexnews.hk/app/sehk/2025/107815/a126801/sehk25102801668.pdf) |
