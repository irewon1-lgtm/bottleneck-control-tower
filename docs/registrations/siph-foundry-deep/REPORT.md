# SiPh PIC 고객인증 파운드리 생산 슬롯 — 2026-10-06 심층 재검토

**OBSERVE 유지. 2027·2028·2029년 각각 `수요 > 고객인증 양품 공급`은 UNKNOWN.** 계약·예약·양산 ramp는 실재하지만 공개된 물리 수량과 적격 공급/잔여 슬롯을 같은 고객·공정·기간으로 맞출 수 없다. 기존 TARGET `siph-pic-qualified-foundry-slots`에 새 심층 history 하나만 append한다. 기존 history, 메타데이터 및 다른21 TARGET은 그대로 보존한다. 좁은 공정 세 가지는 하위 연구단서로만 기록하며 정식 TARGET을 만들지 않았다.

## 비교 방법과 범위

미국 AI DC에 사용되는 pluggable/NPO/CPO용 SiPh PIC가 대상이다. 전 세계 SiPh 계약을 미국 AI DC 전용으로 합산하지 않는다. Coherent DCI와 direct-detect/CPO 공정·제품을 구분한다. 검사·burn-in·fiber attach·SOI substrate는 경계만 확인하며 이번 조사에서 별도의 반복 심층검토를 하지 않았다.

예약된 고객 의무량은 그 고객에 배정된 적격 공급량과 비교한다. 신규 미배정 firm demand만 미예약 qualified-good-output slots와 비교한다. `전체 예약량 > 미예약 슬롯`은 유효한 부족 비교가 아니다. 금액·매출·대역폭·wafer 면적/직경·기업 전체 CAPA에서 wafer/PIC 수를 추정하지 않는다. 이미 설치된 명목 능력, wafer starts, shipped wafers, accepted known-good PICs, 고객 인증은 서로 다른 상태다.

## 연도별 실제 수요와 공급의 충돌

| 기간 | 확인한 demand/ramp | 적격 공급/relief 단서 | 확정 wafer 필요량 | 잔여 적격 양품 슬롯 | D>S |
|---|---|---|---|---|---|
| CY2027 | Tower $13억 SiPho 계약과 $2.9억 received prepayment; NewPhotonics NPO1H27 volume shipment 계획; ST 장기 reservation | Tower Q426 starts 증설의 full financial effect Q227 목표, AraiQ427 readiness 목표; ST >4배 production 목표; UMC2026 actual qualified300mm 공급 | UNKNOWN | UNKNOWN | UNKNOWN |
| CY2028 | Tower 더 큰 contractual wafer commitment, 관련 추가 prepayment Jan2027 due; 계약 수량/미국용 배정 미공개 | ST 추가 확대2028; Tower Track1, Track2 장비 functioning Q428 목표이며 tool/qual 일정 미확정 | UNKNOWN | UNKNOWN | UNKNOWN |
| CY2029 | 검토 원문에서 미국 AI DC2029에 대응하는 확정 최소 wafer/PIC량·납기 없음; Tower2028 이후는 discussions | Track2 성장2029 및 경쟁 플랫폼 발전은 계획/공급 옵션; 실제 고객별 인정 물량 미공개 | UNKNOWN | UNKNOWN | UNKNOWN |

2027 금액은 계약 존재의 강한 증거지만 ASP/제품 믹스가 없어 wafer 최소량이 아니다. 2028에는 최소 wafer commitment의 존재가 확인되지만 숫자가 없다. 2029 자료 부재는 수요가 0이라는 뜻이 아니다. 각 연도에 확정 미배정 수요나 실제 공급 지연·부족을 공개한 customer-specific 사례도 이번 원문 표본에서는 확인하지 못했다. [T01,T03,T07,S01,U01]

## 고객·계약·수량 단서

| 사례 | 확인 수준 | 물리 수량과 한계 |
|---|---|---|
| Tower 주요 고객 | SEC embedded issuer announcement: signed2027 SiPho contracts, 실제 reservation prepayment, 더 큰2028 계약 | 고객명·최소 wafer/PIC 수·US/CPO 배정·ASP UNKNOWN. 50+active customers의 full forecasts는 firm minimum 아님 |
| ST–AWS | named multi-year multi-billion commercial engagement, 여러 제품군 | PIC-only 최소금액/wafer량 UNKNOWN; 전체 계약가를 SiPh로 할당 금지 |
| ST PIC100 |300mm HVM, long-term customer capacity commitments | 확정 예약의 존재 확인; 비율·연도별 wafer/양품량 UNKNOWN |
| NewPhotonics–Tower | PH18DA NPG102800G/1.6T HVM 발표; NPC5056.4T NPO1H27 shipment 계획 | 첫 고객/실제 양산 플랫폼 확인, 연도별 의무량·미국 end-customer UNKNOWN |
| Marvell–Tower | 실제 coherent PIC cumulative >500만 출하 | 양산 증거지만 연간 CAPA·동기간 신규 슬롯·CPO용 배정 아님 |
| SILITH–UMC |2026-07-14 첫300mm 양산 wafer delivery; unnamed cloud qualification | 실제 경쟁 supply. SILITH cumulative >800만100/200G PIC 모두를 새 UMC라인으로 계산하지 않음 |
| NVIDIA Spectrum-X Photonics |2026-05-31 CPO system now in production | 고객 측 product ramp, supplier/year/US deployment별 PIC 예약량 UNKNOWN |

이 사례들은 수요·공급 실재성을 보여주며 wafer 수요를 합산할 수 있는 동질 자료는 아니다. 발표문은 원계약 부속 공급량표를 대체하지 않는다. [T01,T07,T08,S01,S02,U01,N01]

## 고객인증 공급과 신규 슬롯

| 파운드리/flow | 실제 확인 상태 | 앞으로 들어올 공급 | 공개하지 않은 것 |
|---|---|---|---|
| Tower multi-fab / F7 | F7 Uozu300mm photonics qualified volume shipping, coherentPIC 누적 출하, PH18DA HVM | Q426 installation/full qualification·starts 목표; Q227 financial effect. AraiQ427 readiness·Track2Q428 tools/functioning 목표 | PDK·고객·wafer size별 starts/shipped/accepted CAPA, 예약·가동률·양품률·free slots |
| ST PIC100 |300mm800G/1.6T HVM for leading hyperscalers |2027 >4배 production·2028 additional expansion 목표; PIC100TSV NPO/CPO는 roadmap | 절대 baseline/증설 후 accepted wafers, 고객별 slot/TSV qual 날짜 |
| UMC–SILITH | Singapore300mm 실제 첫 양산 wafer 납품과 cloud customer qualification | 자체300mm 플랫폼 product development2027; imec flow riskproduction2026/27;400G/TFLN 개발 | accepted wafers/month, yield%, cloud identity·US 배정, 일반 신규 고객 잔여 슬롯 |
| GF | 현재 undated 페이지는 Malta/Singapore300mm 및 추가 Singapore200mm 제조 제공을 설명, in-house packaging/test capability | March10 자료의 Singapore300mm 계획과 현재 웹 상태를 구분; site별300mm 실제 qual 날짜 UNKNOWN. 기존 cleanroom scale 옵션·정부 R&D LOI | PIC SKU/customer별 actual capacity/reservations/free slots; GF 전체 wafer를 SiPh로 환산 불가 |
| TSMC COUPE | COUPE-on-substrate CPO production2026 announced |200G microring/packaging 생태계 공급 옵션 | 고객별 qualifiedPIC output·미예약 슬롯; 일반CoWoS/N2 CAPA 산입 불가 |

Tower의2월 `>70% reserved OR in-process`에는 협의 중 예약이 섞였다.8월 공식 콜은 증설을 고객들이 원하지만 전부 booked는 아니라고 구분했다. 따라서30% free,70% firm booked,100% sold-out 어느 것도 확정할 수 없다. >5배 Q425 shipment baseline과 >3배 Q226 baseline은 서로 다른 기준의 계획이다. Track2 4배 수치는 Track1/Fab6분을 포함하고 SiGe도 섞여 있어 합산하거나 곱하지 않는다. F7 fab utilization 및85% model assumptions는 PIC yield 또는 free capacity가 아니다. [T02–T05,G01–G03]

## Leadtime·수율·qualification·대체

Tower20-F의 신규 고객9–24개월 이상/기존6–12개월은 design→mask→prototype→assembly/test→validation/qualification→production을 포괄하는 일반 sales cycle이다. PO가 보통 출하2–6개월 전에 들어온다는 설명도 일반 주문창이다. 어느 것도 PIC wafer process cycle이나 타파운드리 이전 재인증 기간을 뜻하지 않는다. UMC–SILITH18개월은 그 플랫폼 개발부터 production-readiness까지의 사례이다. EUROPRACTICE의6주 design 제출창도 fab cycle이 아니다. 실제 wafer-start→accepted known-good PIC 납품, customer port requalification, yield% 및 양품률로 인한 CAPA 할인폭은 모두 UNKNOWN. [T06,U01,E01]

각 공급자의 PDK, 소자 특성, active modulator/photodiode, SOI/wafer size, III-V integration, TSV/packaging route가 다르다. GF45CLO/SPCLO, STPIC100, TowerPH18DA, UMC/iSiPP300, TSMCCOUPE의 명목 제조면적을 하나의 전환가능 공급풀로 더할 수 없다. 다른 파운드리의 실제 양산·qualification은 sector-wide 부족 주장을 약화시키지만 기존 설계의 즉시 대체를 증명하지 않는다. Tower co-development에 양측 exclusivity가 통상 있다는 경영진 설명은 특정 고객 이전을 제한할 수 있으나 고객명·범위·기간 미공개이며 모든 고객에 일반화하지 않는다. [T03,T06,S01,U01,U02,G02,P01]

## 더 좁은 공정이 실제 병목인가

| 공정 단서 | 확인 | 판정 |
|---|---|---|
| InP epi / PH18DA chip-to-wafer bonding | 실제 heterointegration; outsourced bonding을 in-house로 옮겨 start-to-ship control 강화 계획. IQE executed reciprocal 공급계약 | queue/양품률/qualified bonding output/고객 의무량 충돌 미확인. 기존 hybrid-bonding 및 InP TARGET 경계로 연결; 신규 TARGET 없음 |
| wafer probe / optical acceptance | 일반 third-party probe·customer test, GFknown-good integration | 특정 SiPh foundry test shortage 또는 wafer-start가 test에서 막힌 수량 미확인; 기존 burn-in/test TARGET 경계만 연결 |
| lithography / Ge epi / SOI / TSV | process dependence와 차세대 TSV/400G 개발 확인 | 특정 장비 수·예약·throughput·yield/leadtime으로 인한 shortage 미확인. 공정 기술 발표를 병목으로 승격하지 않음 |

가장 강한 반증은 실제 신규 UMC qualified 공급과 기존 Tower/ST/GF 생산이다. 또 Tower는8월 콜에서 전반적인 shortage를 부인하고 과거 InP starting-material crunch를 IQE 계약 등으로 해결했다고 밝혔다. 이는 해당 경영진의 현재 상태 설명이며2027–29 모든 고객의 미래 공급 보장은 아니다. [T03,I01,U01]

## 승격/기각 조건과 다음 확인

- 강화: 같은 고객·PDK·wafer size·수량단위의 확정 최소 needdate가 배정 또는 미예약 accepted capacity/최초 공급일보다 앞선다는 원계약/제조 자료; 고객 인증·수율·tool installation/test queue 지연과 qualified 경쟁 대체의 실패를 확인.
- 깨는 조건: 예약물량의 실제 적격 양품 공급·납기를 충족; 신규 미배정 물량도 잔여 슬롯이나 실제 승인된 경쟁 flow로 충족. 계획 CAPA가 아닌 accepted shipments 확인.
- 다음 확인: TowerQ426 tool/qualification actual, Q227 shipments와 January2027 prepayment 실제 수령; NewPhotonics1H27 납품; AraiQ427 및 Track2Q428 고객별 qualification; ST2027/28 및 GF/UMC product-specific good-output/free slots.

## 원문·저장 검증

원문20건의 bounded exact excerpts, publication date/UNKNOWN, locator, SHA256는 sources.json에 보존한다. 전체 문서 archival snapshot은 아니며 strict provenance PASS·EARLY/performance 주장은 하지 않는다. 정부 METI PDF 재접근403으로16000/2000wpm와 특정2027 production dates를 verified quantitative inputs에서 제외했다. Secondary GF10배 capacity, SiGe oversubscription, TSMC25kwpm estimates, Samsung research-only platform을 SiPh qualified capacity로 사용하지 않았다. 미공개 원계약·물량은 zero로 취급하지 않는다.

Active ledger: `future-bottleneck-data:future-tracking.json`의 기존 TARGET history에 단일 append. Main artifacts: `docs/registrations/20261006-siph-foundry-deep.json`와 `docs/registrations/siph-foundry-deep/`. 기존22 TARGET·old histories 보존, operation idempotency와 remote byte readback을 검증한다. 최종 실제 원격 commit/merge는 별도 immutable storage receipt에 기록한다.

## Primary sources

- [T01] Tower SEC 6-K (2026-05-13): https://www.sec.gov/Archives/edgar/data/928876/000117891326002609/zk2635309.htm — L57–65
- [T02] Tower SEC earnings exhibit (2026-02-11): https://www.sec.gov/Archives/edgar/data/928876/000117891326000404/exhibit_99-1.htm — L44–57
- [T03] Tower official Q2 2026 conference-call transcript (2026-08-04): https://ir.towersemi.com/static-files/da25365d-20d1-4c75-83d9-93b39badcb42 — P2–3, P7–8, P12–14; exact excerpt P7 L295–296 and P14 L545
- [T04] Tower SEC 6-K (2026-07-14): https://www.sec.gov/Archives/edgar/data/928876/000117891326003477/zk2635682.htm — L70–77
- [T05] Tower official announcement (2026-03-25): https://ir.towersemi.com/news-releases/news-release-details/tower-semiconductor-announces-plans-expand-300mm-capacity-japan/ — L34–42
- [T06] Tower SEC 2025 Form20-F (2026-04-30): https://www.sec.gov/Archives/edgar/data/928876/000117891326002318/zk2635149.htm — L920–926, L999–1046
- [T07] NewPhotonics / Tower joint primary announcement (2026-09-17): https://ir.towerjazz.com/news-releases/news-release-details/newphotonicsr-and-tower-semiconductor-begin-high-volume — L34–40
- [T08] Tower / Marvell joint primary announcement (2026-06-18): https://ir.towerjazz.com/news-releases/news-release-details/tower-semiconductor-and-marvell-ship-over-five-million-coherent — shipment paragraph
- [I01] IQE / Tower joint primary announcement (2026-06-15): https://www.iqep.com/media/press-releases/2026/iqe-and-tower-semiconductor-announce-multi-year-inp-epiwafer-supply-agreement/ — minimum commitment paragraph
- [S01] STMicroelectronics official announcement (2026-03-09): https://newsroom.st.com/media-center/press-item.html/t4761.html — L2593,2612–2622
- [S02] STMicroelectronics / AWS official announcement (2026-02-09): https://newsroom.st.com/media-center/press-item.html/c3385.html — L2605–2617
- [U01] UMC / SILITH joint primary announcement (2026-07-14): https://www.umc.com/en/News/press_release/Content/technology_related/20260714 — L149–168
- [U02] UMC / imec joint primary announcement (2025-12-08): https://www.umc.com/en/News/press_release/Content/technology_related/20251208 — risk-production paragraph
- [G01] GlobalFoundries official platform page (publication day UNKNOWN): https://gf.com/technologies/silicon-photonics/ — L279,285,438
- [G02] GlobalFoundries official March10 photonics event deck (2026-03-10): https://investors.gf.com/static-files/1e94f710-7024-436d-8ed6-7b37a00770ae — P9–12,16,20,22
- [G03] GlobalFoundries SEC Q2 earnings exhibit (2026-08-05): https://www.sec.gov/Archives/edgar/data/1709048/000170904826000218/globalfoundries2q2026earni.htm — L22–25 and shipment table
- [G04] GlobalFoundries official government LOI announcement (2026-07-29): https://gf.gcs-web.com/news-releases/news-release-details/globalfoundries-signs-letter-intent-us-department-commerce-300 — R&D award / photonics sections
- [N01] NVIDIA official platform announcement (2026-05-31): https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Vera-Rubin-Ramps-Into-Full-Production-to-Power-Agentic-AI-Factories-Worldwide/default.aspx — Spectrum-X Ethernet Photonics / CPO paragraphs
- [P01] TSMC official North America symposium release (2026-04-23): https://pr.tsmc.com/english/news/3302 — L297,300,315–316
- [E01] EUROPRACTICE official 2026 fabrication schedule (publication day UNKNOWN): https://europractice-ic.com/schedules-prices-2026/ — GF SPCLO registration deadline note
