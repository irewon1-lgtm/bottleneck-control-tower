# CPO PIC–EIC 고객인증 hybrid bonding 처리능력 재조사

조사 기준일: 2026-10-06 UTC. TARGET: `cpo-pic-eic-qualified-hybrid-bonding`. 판정: **OBSERVE**. 기업·주가·시장수익성 분석은 하지 않았다.

기존 REVIEW_LEAD를 결론의 전제로 삼지 않고 원문을 다시 확인했다. CPO 생산 개시, COUPE의 SoIC CoW 접합 구조, 장비·공정의 기술적 제약은 확인된다. 그러나 **2027·2028·2029 미국 AI 데이터센터용 고객별 필요한 적격 PIC–EIC 접합 처리량이 같은 기간의 가동 가능한 적격 처리량을 초과한다는 증거는 확보하지 못했다.** 부족 가능성은 열려 있으나 입증된 shortage가 아니며 확률을 수치화할 근거도 없다. 공급 충분성을 입증한 것도 아니다. 기존 history는 유지하고 이 판단을 새 history로 추가한다.

## 1. 비교 기준과 판정 경계

비교 단위는 고객·제품·접합 recipe별 `accepted PIC–EIC bond assemblies/month`이다. 개별 Cu pad 수, optical port 수, optical engine 수, wafer 수, pick-and-place 횟수는 그대로 더할 수 없다. 엔진당 PIC/EIC 수, 여러 EIC를 한 PIC에 붙이는 구조, 층수와 die 면적에 따라 변환 계수가 달라진다. 미국 고객명과 미국 설치 목적지 비중도 구분한다. 해외 제조능력도 미국 수요에 실제 배정·인증되어 있으면 공급에 포함한다.

필요 양품 접합량 D는 제품 수량 × 엔진 수 × 해당 hybrid-bond 구조 채택률 × 엔진당 접합 조립 수로 계산해야 한다. 투입량을 비교하려면 D를 실제 수율로 나눈다. 공급 S는 고객별 적격 라인의 surface prep, alignment/contact, anneal, inspection 처리능력을 같은 단위로 환산한 뒤 최소 단계의 실효 처리량, 가동시간, OEE, 해당 recipe의 양품률 및 고객 배정을 반영해야 한다. 이미 다른 제품에 예약된 물량은 해당 고객의 잔여 capacity에서 제외한다. 이 식은 분석 방법이며 공개값으로 계산한 결과가 아니다. 수율을 수요와 공급 양쪽에 중복 적용하지 않는다.

| 연도 | 미국용 필요한 적격 양품 접합량 D | 미국용 가동·배정 가능한 적격 공급 S | D>S | shortage window |
|---|---|---|---|---|
| 2027 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| 2028 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| 2029 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

UNKNOWN은 0이 아니다. OEM 생산 발표, supplier production readiness, 고객 qualification 완료, 적격 line output, free capacity는 각각 별개의 증거다. 좁은 공정의 대기열·실효 처리량 부족이 확인되지 않아 신규 TARGET이나 하위 TARGET을 만들지 않았다.

## 2. 연도별 CPO ramp: 실제 생산과 미래 목표 분리

2027–2029는 조사 시점 이후다. 따라서 그 기간에 실제 수행된 양산 결과는 아직 존재하지 않으며, 이미 시작된 생산과 향후 일정·전망을 구분했다.

| 기간/제품 | 원문에서 확인한 사실 | 증거 수준 | 접합 수요로 사용할 수 없는 부분 |
|---|---|---|---|
| 2026 NVIDIA Spectrum-X Ethernet Photonics | 2026-05-31 공식 발표에서 CPO switches now in production, CoreWeave·Lambda·OCI 초기 adopters 명시 [S01] | OEM의 현재 생산 진술 | 2027–2029 미국 switch 수, 월 ramp, 엔진 BOM, 고객별 접합 주문량 없음. million-GPU는 시스템 확장 능력이며 설치 확정 수량 아님 |
| 2026 TSMC COUPE-on-substrate | 2026-04-23 발표에서 2026 production beginning 예정. 2025 연차보고서에는 여러 고객 200Gbps 성과 및 2026 volume 목표 [S02,S03] | 제조 서비스의 일정 및 고객 개발 실적 | 4월 발표만으로 모든 제품의 고객인증 완료를 선언하지 않음. NVIDIA 생산은 해당 시스템 경로 존재의 증거이며 TSMC 전 recipe qualification 명단이 아님 |
| 2027 Lightmatter | 현재 공식 Vision HTML은 2026 NPO → 2027 CPO → 2028+ photonic interposer. 2026-09-17 CPX 발표는 Q1 2027 NPO evaluation kit 출하 예정, preliminary specification [S05,S06] | 로드맵 + 별도 제품 평가 일정 | 제품 범위가 다른 두 문서의 일정은 조정 설명 없음. 동시 실현 가능하므로 지연 확정도 아니지만, 2027 CPO volume 확약으로 계산하지 않음. 문서 발행일 없는 Vision은 관찰일 기준 |
| 2027 Ayar | CEO Wade의 2026-09-10 직접 인터뷰: 고객의 2028–2029 ramp에 대응하려면 2027년 말까지 volume qualification 필요 [S07] | 경영자의 조건부 일정 | 2027년 말 완료 사실이 아니라 목표/필요 조건. qualification 소요시간·개시일·고객 물량 미공개 |
| 2027~2028 초 Celestial/Marvell | 2026-02-02 공식 문서의 initial contribution H2 FY2028와 이후 확대 목표. fiscal year는 1월31일에 가장 가까운 토요일 종료 [S32,S33] | 향후 상용화 시점의 보조 신호 | H2 FY2028는 대략 달력 2027 하반기~2028년1월. 매출 전망을 bond 수량·고객인증 생산으로 변환하지 않음 |
| 2028 | Ayar 고객 ramp의 첫 연도. Lightmatter photonic interposer 2028+ 로드맵 [S05,S07] | 향후 계획 | 현재 switch scale-out와 미래 XPU scale-up은 서로 다른 물량/qualification. 동일 시장량으로 중복 집계하지 않음 |
| 2029 | Ayar 2028–2029 ramp 구간; Lightmatter 2028+ 지속 및 Celestial FY2029 확대 목표는 보조 신호 [S05,S07,S32] | 향후 계획 | 달력 2029 전체 미국 양산 수량·월별 ramp 속도 미공개. FY2029는 달력 2029와 다름 |

Broadcom TH5-Bailly의 100G/lane volume-production과 Delta/Micas 생산은 2025 공식 발표에서 확인된다 [S26]. Meta의 100만 400G port device-hour 무중단 lab characterization은 2025 시스템 신뢰성 증거 [S27]다. 어느 것도 2027–2029 hybrid-bond 제조 수율·장비 output은 아니다. TH6 일반 제품의 volume shipment를 Davisson CPO 전량 volume로 바꾸지 않았다.

## 3. 어떤 구조에서 실제로 필요한가

| 구조 | PIC–EIC hybrid bonding 관계 | W2W / D2W / D2D 구분 | qualification 해석 |
|---|---|---|---|
| TSMC COUPE | EIC/PIC face-to-face SoIC 고밀도 접합이 선택된 구조의 핵심 [S03,S04,S30] | 연차보고서의 SoIC Chip-on-Wafer(CoW)는 D2W 계열. W2W로 단정하지 않음 | 해당 COUPE 구조 유지 시 필수. 모든 CPO의 필수 공정으로 일반화 불가 |
| COUPE 엔진을 substrate / CoWoS에 배치 | 엔진 내부 PIC–EIC 접합과 엔진→switch/XPU package 연결은 다른 interface | 내부 CoW와 외부 substrate/2.5D assembly 별도 | COUPE-on-substrate 2026 계획과 CoWoS CPO under-development를 합치지 않음 [S02,S03] |
| W2W hybrid | 두 full wafer를 정렬·접합; GEMINI FB는 PIC/EIC 통합 application 지원 [S15,S16] | wafer 접합 cycle. usable matching die sites 및 compound yield 필요 | 상용 장비/application은 확인. 특정 미국 CPO 고객의 완료 인증·wafer/day 없음 |
| D2W hybrid | singulated KGD를 target wafer에 placement. unequal die와 KGD 선택 가능 [S11,S17] | die/contact 처리량 + wafer prep·anneal·검사 배치. collective D2W도 별도 | 2,000 dry placements/hour를 2,000 accepted engines/hour로 계산 불가 |
| D2D hybrid | singulated PIC/EIC pair의 접합이라면 die handling·carrier·양면 준비 flow가 필요 | 전기적 D2D interface(UCIe 등)와 물리적인 die-to-die bonding은 다름 [S29] | 조사 원문에서 특정 CPO 고객 인증 D2D hybrid line output 미확인. D2W spare와 대체 가능하다고 합산하지 않음 |
| ASE photonic FOPoP / photonic 3D | copper pillars·fan-out 또는 PIC TSV를 쓰는 복수 구조 [S22,S31] | 3D stacking이라고 자동으로 Cu/dielectric hybrid 아님. PIC/EIC 정확한 접합 recipe 공개 범위 제한 | 엔진 integration 경로의 다변화 증거. COUPE 고객의 즉시 second source 증거 아님 |
| IMECAS micro-bump 구조 | 저자가 자기 연구 구조를 설명: EIC-on-PIC 40µm micro-bump [S28] | solder/micro-bump 연결, hybrid와 구분 | 구조적 우회 가능성의 연구 증거. 미국 200G/lane 고객인증 양산 대체로 간주하지 않음 |
| Intel OCI die stack | 실제 CPU-to-CPU 광 I/O 데모 [S29] | die stack 공개, PIC/EIC 접합 방식은 해당 자료에서 특정 못함 | monolithic EIC/PIC 또는 hybrid-free 상용 대체라고 추정하지 않음 |

결론: hybrid necessity는 **제품 architecture의 조건부 필요성**이다. CPO 전체 TAM, 모든 GPU, 모든 optical lane에 hybrid-bond 조립 수요를 일괄 부여할 근거는 없다.

## 4. 공개된 장비·라인·처리량 단서

| 공급경로/장비 | 확인한 수치 또는 단계 | 확인 가능한 적격 공급 | 미공개/주의 |
|---|---|---|---|
| TSMC COUPE/SoIC CoW | 고객 200Gbps 개발 실적, 2026 volume 계획; OEM CPO production 발표와 일관된 경로 [S01–S04] | 생산 경로 존재 수준; 고객별 signed qualification 및 accepted output 수치 없음 | installed HB fleet, 월 wafer starts, die map, bond yield, US 배정·잔여 CAPA UNKNOWN. logic/HBM SoIC와 CoWoS 총 CAPA를 CPO 공급으로 사용하지 않음 |
| NHanced Morrisville NC Besi8800 | 한 대의 신규 설치/production 진입 사건 공개. 최대 2,000 dies/hour, 200nm alignment, 1µm pitch, batch anneal [S12] | 일반 hybrid 생산 운영 진술 | 공개 설치 사건 1건 ≠ 전체 fleet 1대. 미국 AI CPO 고객·recipe qual·실제 양품 UPH·free capacity UNKNOWN |
| Besi Datacon8800 current product | up to 2,000 CPH **dry cycle**, 100nm @3σ worst corner GOG alignment, 12-inch target wafer, ISO3; inline IR [S11] | 고객 인증 output 수치 아님 | dry cycle 2,000/h의 산술상 1.8초/회는 실제 clean/align/anneal/inspection 포함 cycle time 아님. NHanced의 200nm와 현재100nm는 공개 모델/시점 사양이 다름 |
| Besi 산업 전체 | 2025말 HB 고객15→Q2 2026 고객21; CPO use case 확대와 신규 HB capacity 추가 진술 [S14] | CPO 관련 장비 보급의 방향성 | 21을 적격 CPO 고객/라인/장비 수로 환산 불가. 연차보고서 cumulative150+ orders는 여러 application 전체 [S13] |
| EVG GEMINI FB W2W | 2018 SmartView NT3 up to20 wafers/hour, sub50nm alignment; 2026 W2W 연구는200nm Cu pitch, sub40nm post-bond overlay across100% die sites [S15,S16] | W2W 장비/연구 가능성 | 20의 wafer/pair 조건 확인 없이 pair/h 변환 불가. 전체 die sites overlay pass ≠100% bond good yield. CPO recipe별 실제 wafer/day·fleet 없음 |
| Applied Kinex + Besi | wetclean/plasma/bond/metrology 통합, 2025-10-07 launch [S18–S20] | product availability/production-ready materials 진술 | Kinex에 포함된 Besi head를 stand-alone8800와 중복 공급 합산 불가. 설치·CPO 고객 qual·actualUPH UNKNOWN |
| EVG320/40 D2W, SUSS | prep/clean/collective transfer 및 overlay metrology 솔루션 [S16,S21] | 장비 메뉴/기술 역량 | CPO 설치 대수, accepted output 및 예약 물량 없음 |
| ASE | 2025 substrate-CPO demonstrated; wafer bumping, laser die bonding, 2.5D/3D 플랫폼 [S22,S23,S31] | assembly 경로/데모 | 고객별 PIC–EIC hybrid recipe 완료 인증, 적격 bonder 대수·월처리량 UNKNOWN |
| Amkor | 2024 Lightmatter와 develop/validate; 2026 slide35 CPO 3 active engagements, slide37 hybrid bonding toolbox [S24,S25] | 개발/engagement/technology offering | 3engagements ≠3 qualified lines. qualification 고객·PIC–EIC recipe·CAPA UNKNOWN |

어느 경로에서도 동일 조건의 고객인증 PIC–EIC 양품 처리량과 기간별 미국 배정량을 함께 확인하지 못했다. 따라서 정량 적격 CAPA의 합계는 UNKNOWN이다. 생산 능력이 없다는 판단이 아니다.

## 5. 실제 제한 단계와 품질

| 단계 | 원문에서 확인한 메커니즘·수치 | 실제 제한 여부 |
|---|---|---|
| CMP·surface prep·activation | Cu recess 제어, particle/dicing 청정도 유지, 활성 표면의 시간 경과에 따른 저하. imec 연구 recess<2.5nm 및 plasma dicing [S17,S19] | queue time 허용치·cleaner 대수·yield loss·고객 WIP 미공개. 좁은 하위 **가설**, 병목 확정 아님 |
| PIC–EIC alignment/contact | 정밀도와 빠른 placement 양립 필요. Besi100nm 사양, imecD2W<350nm overlay [S11,S17] | 생산 recipe의 alignment time·실제 overlay 분포·재정렬률 미공개. dry speed로 증명 불가 |
| anneal | NHanced room-temperature dielectric contact 뒤 batch anneal로 전기 접합 완료 [S12] | batch size, furnace 수, soak/ramp/cool time·thermal budget·대기열 UNKNOWN |
| bond/void/overlay inspection | Besi in-situ IR placement feedback; EVG40 overlay; Kinex metrology [S11,S16,S18] | inline placement 검사는 전기 접합·void·신뢰성 전 항목의 합격과 다름. 검사시간·샘플링/100%·재검률 UNKNOWN |
| warpage | NHanced improved control은 수치 없음. ASE substrate coplanarity/warpage는 FAU optical coupling 요구와 연결 [S12,S23] | PIC–EIC bond warpage 결함과 광섬유 coupling 불량을 혼합하지 않음 |
| fiber active alignment / KGOE test | ASE는 AA 시간과 double-side test의 구조 적합성 설명 [S31] | hybrid-bonder 정렬과 다른 downstream 단계. 기존 `cpo-optical-electrical-volume-test`와 연관 기록만 유지 |

imec 2024 D2W **연구 test vehicle**: 2µm pitch, <350nm overlay, Kelvin electrical yield>85%, daisy-chain>70%. 이것을 CPO 엔진 전체 yield로 사용하지 않았다. 같은 발표의 광 interconnect는 collective SiCN dielectric proof-of-concept(<0.5dB)이고 Cu-to-Cu는 후속 계획이다 [S17]. EVG 2026 W2W sub40nm overlay 수치도 연구 결과이며 고객인증 CPO 양산 수율이 아니다 [S16]. Meta lab port-hours는 시스템 안정성이고 bonding first-pass yield와 다른 분모다 [S27].

고객 recipe별 bond yield, electrical/optical acceptance, void density·reject threshold, die/wafer warpage 허용치, post-bond overlay, rework/scrap/retest 비율은 모두 UNKNOWN. 영구 접합의 rework 제약이라는 일반론만으로 폐기율을 임의 설정하지 않았다. 실제 제한 단계는 **UNKNOWN**이며, 내부에 `surface-prep/activation-to-bond queue`, `alignment/contact`, `anneal`, `inspection` 가설을 기록하되 신규 TARGET은 만들지 않는다.

## 6. 예약, lead time, 실제 대체 가능성

예약이 없다고 결론 내리지 않는다. Amkor Arizona slide59는 top customers multi-year contracts 및 고객 기반 시설을 명시한다 [S25]. Marvell 2026-05-28 10-Q도 장기 wafer/substrate capacity reservation을 확인한다 [S34]. 하지만 각각 packaging 공장 전체/wafer와 substrate 계약이며 **PIC–EIC hybrid-bond line·장비·recipe별 예약량을 공개하지 않는다**. Ayar–Alchip의 COUPE partnership 및 선별 고객 개발 역시 공급 계약/장비 예약량 증거가 아니다 [S09,S10]. 대상 공정의 예약량·free capacity는 UNKNOWN이다.

| 구간/relief | 확인된 일정 | 대상 CPO 적격 공급에 포함할 조건 |
|---|---|---|
| Besi 신규 장비 주문→인도 | 2025 연차보고서 hybrid bonding/TC Next 등 submicron 장비 **6–9개월**. 일반4–12주와 구분 [S13] | 보편적인 CPO 전용 quoted lead time 아님. 주문일·배정 모델·인도일 확인 필요 |
| 인도→설치·site acceptance | 기간 UNKNOWN | utilities, contamination control, calibration, actual recipe stability 확인 |
| 설치→고객 qualification→양산 | 기간·일정 UNKNOWN | reliability lots, yield, acceptance 범위, 고객 승인·배정 확인. 임의6–9개월 추가하지 않음 |
| NHanced 신규8800 | 2025 설치·생산 운영 공개 [S12] | 이미 들어온 일반 relief. 특정 CPO route qual/배정이 확인될 때만 해당 공급 산입 |
| 통합 Kinex / inline IR / collective D2W | 2025 launch와 현재 offering [S11,S16,S18–S20] | 실제 recipe UPH·오염/재검 감소·고객 승인일 필요. roadmap in-situ anneal은 구현 완료로 산입하지 않음 |
| Besi 산업 보급 확대 | 2026 Q2 material HB capacity additions [S14] | 날짜·장비·고객·CPO 비중·qualification 확인. 기존 고객21과 새장비를 별도 더하지 않음 |
| Amkor Arizona | 2027 tools/line verification/qualification, 2028 production; 2028–2029 ramp 계획 [S25] | factory-level 일정. 대상 PIC–EIC hybrid 공정·고객 승인·실제 output 확보 전은 **conditional relief** |
| 수율 개선 | supplier improved-yield 진술과 연구 수율 [S12,S17] | 양산 동일 recipe의 전후 yield·good output 및 시행일 필요. 현재 relief 규모/일정 UNKNOWN |

TSMC·ASE·Amkor·NHanced는 완전하게 교환 가능한 capacity pool이 아니다. 대체 공급자는 같은 interface metallurgy/pitch, die orientation, wafer map, CMP/surface specification, anneal thermal budget, optical/electrical performance 및 고객 reliability 승인에 맞아야 한다. PDK/설계·flow 변경과 재인증이 필요할 수 있다는 공정상의 추론이며, 고객별 전환 기간은 UNKNOWN이다. TSMC에서 접합한 엔진을 ASE/Amkor가 package/test한다면 직렬 서비스이므로 세 회사를 세 독립 hybrid 공급원으로 합산하면 중복이다.

micro-bump/TCB, fan-out copper pillar, 2.5D engine 배치 등의 구조는 존재하지만 COUPE의 고밀도 PIC–EIC 접합을 그대로 치환하는 drop-in 경로는 확인되지 않았다 [S22,S28,S31]. 필요한 pitch와 electrical parasitics/thermal budget에 맞도록 설계를 바꾸고 고객인증을 다시 받아야 할 수 있다. NPO나 pluggable은 CPO 채택 시기를 늦춰 수요를 줄일 수 있지만 내부 PIC–EIC hybrid 자체를 반드시 없애는 것은 아니다. monolithic PIC/EIC도 고객별 실제 양산 대체가 확인되지 않았다. 모두 무조건적인 relief로 계산하지 않는다.

## 7. 승격·반증 조건과 결정적 UNKNOWN

OBSERVE를 유지한다. FUTURE만으로 보류하지 않는 이유는 이미 CPO production 경로와 관련 접합 장비가 존재하기 때문이다. DROP하지 않는 이유는 선택된 COUPE 등에서 구조적 중요성이 남고 미래 고객인증 부족 가능성을 배제할 데이터가 없기 때문이다. REVIEW_LEAD/EMERGING으로 유지·승격할 만큼 구체적인 고객 대기열·부족 window가 발견되지 않았다.

결정적 UNKNOWN:

1. 월/분기별 미국용 switch·XPU CPO 수량, 실제 ramp slope, hybrid architecture share, 엔진당 접합 조립 수.
2. 고객·제품·recipe별 qualification 완료 범위 및 예정 완료일, 승인된 공급처 매핑.
3. 적격 installed fleet, 실제 prep/align/contact/anneal/inspection 처리량, OEE·가동시간, yield·scrap/rework/retest.
4. 예약·계약 배정량과 잔여 capacity, 다른 logic/HBM/CIS 작업과의 경쟁, 특정 고객으로 전환 가능 여부.
5. 실제 WIP/queue·납기 실패가 어느 단계에서 발생했는지, shortage 원인이 bonding인지 fiber/test인지.
6. 주문·설치·qualification·양산의 실제 milestone, 신규 line의 해당 고객 가용일, 수율 개선 적용일.

강화 조건은 같은 고객·recipe·월 기준으로 D와 적격 실효 S를 묶고, D>S 기간 및 prep/align/anneal/inspection의 실측 부족을 확인하는 것이다. 주문이 늘었다는 사실만으로 부족은 아니다. 고객 납기가 적격 공급 때문에 지연되었다는 직접 자료나 실제 가동률/대기열은 원인 분해와 함께 필요하다.

반증/relief 조건은 같은 기간의 승인된 spare·신규 공급이 수요를 커버하거나, 실제 CPO ramp 연기·하향, hybrid-free/다른 route 승인 및 양산 전환, 동일 recipe의 accepted output 개선 확인이다. 생산 개시·보급 확대·복수 architecture는 현재 가설을 약화하는 증거지만 2027–2029의 공급 충분성을 아직 증명하지 않는다.

## 8. 원문 재확인·저장 기록

34개 원문/직접 발언 문서의 URL, locator, 관찰일, 짧은 excerpt와 사용 한계를 `sources.json`에 보존한다. 웹 본문은 parsed-body 방식, 일부 원문은 local HTML/PDF로 교차 확인했다. 전체 원문을 저장하지 않은 문서에 원문 full hash가 있다고 주장하지 않는다. Besi annual PDF, ASE capability HTML, Lightmatter Vision HTML은 다운로드 원본 hash 및 짧은 추출 근거를 별도로 기록했다. Reuters 원사이트 접근 실패는 숨기지 않고 Reuters로 명시된 KFGO 신디케이션에서 Wade의 직접 발언만 사용한다. 2026-10-13~15 SEMICON 발표는 조사일 이후이므로 완료 발표로 취급하지 않았다. 오늘 예정된 새 발표는 공개 본문을 확보하지 못하면 향후 확인 대상으로 유지한다.

본 조사는 EARLY detection, strict provenance pass, 성과·수익성 주장이 아니다. 기존 TARGET 1개에 새 review를 append하고 기존 target metadata·전체 prior history·다른 TARGET을 보존한다. 저장 검증 결과와 branch/commit은 `verification-20261006.json`, `storage-receipt-20261006.json`에 기록한다.
