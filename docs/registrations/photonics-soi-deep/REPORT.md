# 300mm Photonics-SOI 고객별 적격 공급·미예약 배정 — 2026-10-06 원문 심층 재검토

**최종 OBSERVE 유지. CY2027·2028·2029의 실제 고객인증 양품 부족은 각각 UNKNOWN.** 다년 구매·예약 구조와 고객별 전환 제약은 실재한다. 그러나 공개 수량으로 같은 시기의 공급 부족을 입증하지 못했다. 최초 결론에 의존하지 않고 SEC 실제 계약, AMF 등록문서, 공급자 실적 발표, 공정·고객 자료와 경쟁 양산을 다시 확인했다. 새 정식 TARGET은 만들지 않으며 기존 `photonics-soi-qualified-300mm-allocation`에 history 하나를 append한다.

## 유효한 비교

예약 고객의 의무량은 그 고객에 배정된 적격 양품 공급과 비교한다. 신규 미배정 firm need만 미예약 적격 양품 잔여 배정과 비교한다. 예약된 전체 수요를 잔여 CAPA와 비교해 인위적 부족을 만들지 않는다. 전체 SOI·RF/FD·Power/POI·reclaim·SiC 및 bare silicon CAPA는 Photonics300mm 공급이 아니다. 금액/고객 수/시장 port 전망/PIC 출하수/wafer직경을 기판 wafer량으로 추정하지 않는다. 공급 범위는 고객·SKU·300mm·제조site·acceptance·납기까지 일치해야 한다. Photonics 사업 전체를 미국 AI DC 전용으로 가정하지 않는다.

## 연도별 demand/ramp와 충돌

| CY | 확인된 원문 | 실제 확정300mm Photon wafer 필요량 | 배정/미예약 적격 양품 공급 | D>S |
|---|---|---|---|---|
| 2027 | GF–Soitec SEC ExhibitB는 Silicon Photonics를 명시하고 CY2027 일정 포함. 발효조건·물량 redacted. Soitec FY27 2.5–3배 매출 전망은 2027-03-31까지이며 CY2027 전체가 아님. Tower2027 signed SiPho 계약·ST reserve-backed >4배 생산 목표는 하류 신호 | UNKNOWN | UNKNOWN | UNKNOWN |
| 2028 | 같은 조건부 부속서 CY2028 purchase/supply 일정. Tower2028 더 큰 contractual wafer commitment는 foundry 수요이며 원기판 공급자·규격·물량 미배정 | UNKNOWN | UNKNOWN | UNKNOWN |
| 2029 | 같은 부속서 CY2029 일정 확인. 실제 발효·Photon 품목별 최소량·미국AI 배정 미공개. 새 fab ~2029 경영진 전망은 발주량/부족일이 아님 | UNKNOWN | UNKNOWN | UNKNOWN |

GF 계약의 2029 구조 자체가 없다고 판단하지 않는다. 반대로 조건부 계약 제목과 가려진 schedule만으로 이미 발효된 최소 발주량도 만들지 않는다. wafer 수량뿐 아니라 적격 첫 공급일이 확정 납기보다 늦다는 customer-specific timing conflict도 확인되지 않았다. [G02,S03,T01,T02,R01]

## 계약·예약·선급금의 원문 판독

| 원문 | 실제 확인 | 계량 금지/UNKNOWN |
|---|---|---|
| GF 2024-10-09 signed amendment / SEC2025-03-20공개 | ExhibitB 제목에300mm RFSOI, Silicon Photonics, FD; CY2026–29 주문·공급 구조, product-specific specifications | ExhibitB는 redactedGF행동/조건으로 발효. 발효 완료·annual 최소량·품목·spec·가격·납기·source-site UNKNOWN. 2024–25본문 RF/FD만 보고 futurePhoton부속서를 놓치면 안 됨 |
| GF–Soitec 2017 MSA / SEC2021공개 | Forecast/replenishment advice는 비구속, rolling frozen quantities는 양측 의무, accepted release는 합의 없이 취소 불가; 품질규격과 certificate/warranty 요구 | 실제freeze길이·release수량·고객납기·재고 미공개. 후속 addendum 우선 범위 확인 필요 |
| Soitec2026-07-22 | Photonics 다년 약정+associated deposits, 추가 물량 협의 | 실제 선급금 수령액/일자 미확인. 협의량을 확정 수요로 계산 금지 |
| Soitec2026-09-02 | 약10주요고객 중8개와 CRA 향후 수주 내 체결 예상 | 고객 count이며80% CAPA 예약 아님. Oct6현재 전체 서명/실제 예약 wafer 비율 UNKNOWN |
| Soitec2019–GF | named300mm SOI LTA에SiPh 포함 | historical공급관계, 현재2027–29필요량 아님 |
| Tower2026-05-13 | SiPho2027 $13억 signed contracts, $2.9억 실제 받은 prepay, 더 큰2028wafer commitment | Tower받은foundry예약금≠Soitec받은기판선급금. 고객별200/300mm·US·기판 최소량 환산 금지 |

CEO 원인터뷰의 날짜 기준으로 선급금 미수령이었다는 점을 별도로 보존한다. 이후 receipt를 이번 자료에서 확인하지 못한 것과 그 후에도 전혀 받지 않았다는 주장을 구분한다. 약정조건·deposit forfeiture만으로 전체 미래 구매가격의 무조건 take-or-pay를 가정하지 않는다. [G02,G03,S02,S03,S09,T01,R01]

## 실제 생산·고객인증·잔여 공급

| 공급자/site | 확인 수준 | Photonics300mm accepted CAPA·free allocation |
|---|---|---|
| Soitec Bernin2 | 실제Photon 공급site. AMF FY26보고 mixed300mm연800k명목 | UNKNOWN; 전체SOI를Photon전용·모든gradequalified로 계산 금지 |
| Soitec Singapore PasirRis | FY26말 mixed300mm연~800k. 7월22일 첫Photon고객HVMqualification완료, 추가고객인증 진행 | UNKNOWN; RF/FD인증·설치량과 Photon customer acceptance별 output 구분 |
| Soitec PR1A/확장 | mixedSOI장기1m/확장2m계획, demand에맞춰조정; undatedfabpageFY25표현과datedURD구분 | 투자/장비/인증 후 공급일·Photon배정 UNKNOWN |
| GlobalWafers StPeters Missouri | Q126 selectedPhoton massproduction, Q226300mmSOIPhotonvolume진입 | UNKNOWN; 제품·customer이름/현재양품량/잔여배정없음. 실제경쟁공급 존재가 가장 강한 공급측 반증 |
| Shin-Etsu/SEH | thinSOI photonics제품군·up-to300mmportfolio와 highqualitySOI공급 | 동일300mmPhotonSKU·GF/ST/Tower고객승인·acceptedfree물량 UNKNOWN |

따라서 공개된 Photonics 전용 고객인증 양품 CAPA의 확정 숫자는 없다. 소수의 초기고객 HVM 인증은 확인했지만 해당customer 명단·완료일·acceptance규격·미예약양품량을 확인할 수 없다. 과거800k/site는 참고 명목baseline으로만 저장하며 공급 비교의 min/max에는 넣지 않는다. GWC existing12inch fullutilization은 신규라인을 제외한 모든제품이고 Photon예약률이 아니다. [S01,S02,S06,W01,W02,E01,E02]

## 실제 제한 공정인지 단계별 반증

| 단계 | 직접 확인 | 병목 판정 |
|---|---|---|
| donor/handle silicon wafer | GF는Soitec의third-party raw silicon의존 위험 언급 | Photon-grade rawwafer shortage·qualifiedsupplierallocation·buffer UNKNOWN |
| light-ion implant | SmartCut 필수공정·에너지에따른깊이제어 | dose/beamthroughput/tool수/queue/leadtimeUNKNOWN. 일반implanter제품발표를 Photon shortage로 연결 안 함 |
| molecular adhesion bonding / split | 제조 공정 필수, film transfer와donor재사용 | bondvoid/reject·qualifiedtool배정·wafers/hourUNKNOWN |
| thinning/polish / thickness uniformity | topSi두께·roughness·handle안정성이opticalperformance에필요 | 실제SKU의numeric spec·yielddiscount·polishthroughputUNKNOWN. RF/FD atomicuniformityspec을Photon에이식 안 함 |
| defect control / inspection | lowdefects/bulk microdefects요구, customer certificate/spec/warranty | 실제surface-defectacceptance와검사queue/rejectrateUNKNOWN. 하류PIC wafer-test와substrateinspection구분 |
| customer/site qualification | Singapore일부완료·일부진행. GF는 대체supplier확보에extendedperiod, 단기대체SOI물량 제한 | 가장 강한 제약신호. 그러나 Photon300mm실제delay/shortage와정확한qualification기간은UNKNOWN |

현재 특정implant/bond/polish/inspection 공정이 물리적으로 제한한다는 증거는 없다. 세 단계 묶음을 하위 연구단서로만 기록하고 새 정식 TARGET은 만들지 않는다. GF2025 SOI spend71% 집중과 대체곤란은 customer-side 위험 확인이며 Photon300mm웨이퍼 수량·독점공급률·미국시장share가 아니다. [G01,G03,S04,S05,P01]

wafer제조→acceptance 실제cycle, 고객 첫qualification 및 supplier/site전환 재인증 기간, leadtime 모두 UNKNOWN. 공개된6–12개월은 Singapore추가building을 장비로 채울지 결정하는 기간으로 정정되어 있으며 공급start/재인증기간으로 쓰지 않는다. 품질조건의 존재만으로 yield를 임의 할인하지 않는다.

## 가장 강한 relief와 대체 한계

1. SoitecSingapore첫고객인증과 Bernin 공급, GWC미국300mmPhoton실제양산 진입은 설치/시장전망보다 강한 반증이다. 동일 고객grade를 즉시 바꿀 수 있다는 증거는 아니다.
2. Soitec공식release는 demand에맞춘 output증가와 capacityadjustability를 명시한다. CEO는 기존 underused시설 재배정·추가tools로2026/27충족을 주장했다. 내부acceptedoutput감사는 아니며2028/29보증으로 확대하지 않는다.
3. NIST finalCHIPSawardup$406m은 Missouri300mmSOI·Texasbare300mm·SiCepi를 함께 지원한다. 총지원금/전체 신규wafer수를PhotonCAPA로변환하지 않는다. 실제2026출하발표를보다강하게평가한다.
4. Shin-EtsuthinSOI, alternativewaferstructures/SiN/LNOI/chiplet/기존200mmroute는설계대안이나 기존activePIC의동일300mmSOI를그대로대체하지못한다. 고객변경승인·소자성능·패키징/PDK재검증 필요; 실제이전기간미공개.
5. GFrawwafer앞당긴구매·excessinventory위험은 전용Photon재고숫자가아니다. Customerinventorysharing계약방식도 부족buffer를보증하지않는다. 미국AI프로젝트납기순연으로Photon확정수요가감소했다는 customer-specific 증거는 이번 표본에서 확인하지못했다. UNKNOWN을0으로취급하지않는다.

## 승격을 강화하거나 깨는 조건

- 강화: 발효된SKU별최소수량·필요일, 해당고객배정양품및freeoutput/최초slot을동기간으로비교해양수gap또는명시적deliverydelay확인. 다중source미승인·qualification지연·actualreject/inspectionqueue가부족을유발함을직접확인.
- 반증: CRA예약분실제acceptedwafer납기충족, 신규미배정수요도freecustomerqualifiedslots로충족. Singapore/GWC동일customergrade인증및실제additionaloutput, 고객일정순연/전용재고가부족분메움.
- 다음확인: SoitecCRA서명완료/실제선급금수령·annualminimum, GFExhibitB발효/300mmPhoton제품표, Singapore추가고객승인, GWC동일grade별acceptedoutput·재인증진척, 투자결정과양산합격공급일분리.

## 기존TARGET 관계와 저장

기존substrateTARGET그대로사용. `siph-pic-qualified-foundry-slots`는원기판을소비하는하류의qualifiedPIC제조슬롯이므로별도물리대상으로연결한다. CWlaser/ELSisolator/burn-in/양산검사를중복심층검토하거나등록하지않았다. Source22건의boundedexactexcerpt·원문URL·날짜/UNKNOWN·locator·hash보존. 전체archive가아니므로 strictprovenancePASS/EARLY/예측성과주장을하지않는다.

원격활성원장:`future-bottleneck-data:future-tracking.json`. main자료:`docs/registrations/20261006-photonics-soi-deep.json`, `docs/registrations/photonics-soi-deep/`. 기존history/메타와다른TARGET을보존하고새history1개만append. 실제main반영commit·PR·검증결과는별도immutable storage receipt.

## 원문목록

- [S01] Soitec AMF 2025–2026 Universal Registration Document (2026-06-10): https://www.soitec.com/docs/default-source/agm-documents/2026/en/soitec---2025-2026-urd---va.pdf?amp%3Bsf_site=90bc9310-a429-4e2c-aee0-723d342d500e&amp%3Bsf_site_temp=true&sfvrsn=6bd9e43b_1%3Fsfvrsn%3D6bd9e43b_1 — PDF P31 L1899–1937; P33 L2009–2043; P45 L2673–2696; P238 capex; P266/P292 prepayments
- [S02] Soitec issuer Q1 FY27 release (2026-07-22): https://www.globenewswire.com/news-release/2026/07/22/3331579/0/en/soitec-reports-first-quarter-revenue-of-fiscal-year-2027.html — L70–80,104–128
- [S03] Soitec official Trading Update (2026-09-02): https://www.soitec.com/docs/default-source/financial-reports/2026-2027/2026-09-02-soitec-trading-update-en.pdf?sfvrsn=1b3dba3c_7 — PDF P0 L3–20
- [S04] Soitec technical investor deck (2026-01-06): https://www.soitec.com/docs/default-source/financial-reports/2025-2026/en/soitec---enabling-ai-with-engineered-substrates-2026-01-06.pdf?Status=Master&sfvrsn=bfd1f78a_1 — PDF P16–18; P17 L463–508
- [S05] Soitec Smart Cut process (publication day UNKNOWN): https://www.soitec.com/home/technology/innovation/smart-cut — L232–246
- [S06] Soitec fab inventory page (publication day UNKNOWN): https://www.soitec.com/home/technology/manufacturing/semiconductor-fabs — L236–293
- [S07] Soitec Photonics-SOI product page (publication day UNKNOWN): https://www.soitec.com/home/products/product-platforms/photonics-soi — Photonics-SOI applications section
- [S08] Soitec ecosystem announcement (2025-03-19): https://www.soitec.com/home/group/corporate/newsroom/press-releases/2025/03/19/soitec-contributes-to-accelerated-development-of-integrated-optical-connectivity-solutions-for-ai-datacentres-with-its-silicon-photonics-soi-technology — L277–289
- [S09] Soitec / GF joint original LTA announcement (2019-06-06): https://www.soitec.com/home/group/corporate/newsroom/press-releases/2019/06/06/globalfoundries-and-soitec-announce-multiple-long-term-soi-wafer-supply-agreements-to-meet-accelerating-demand-in-5g--iot-and-data-center — L275–280
- [G01] GlobalFoundries SEC 2025 Form20-F (2026-02-27): https://www.sec.gov/Archives/edgar/data/1709048/000170904826000022/gfs-20251231.htm — L412–415,2275,4713–4719; signatureL4761
- [G02] GF–Soitec actual signed SEC Exhibit4.13 (2025-03-20): https://www.sec.gov/Archives/edgar/data/1709048/000170904825000024/exhibit413-gfsoitecaddendu.htm — L232–235 execution2024-10-09; ExhibitB L297–369,378–474
- [G03] GF–Soitec original 2017 Materials Supply Agreement filed SEC (2021-10-04): https://www.sec.gov/Archives/edgar/data/1709048/000119312521290644/d192411dex103.htm — EffectiveApr25,2017 from linked20-F; §4L111–135; §6–8L200–288
- [W01] GlobalWafers Q1 earnings release (2026-05-05): https://www.sas-globalwafers.com/en/gwc_news_en_20260505/ — Missouri12inchSOI paragraphL261
- [W02] GlobalWafers Q2 earnings release (2026-08-04): https://www.sas-globalwafers.com/en/gwc_news_en_20260804/ — L256–268
- [W03] GlobalWafers SOI product page (publication day UNKNOWN): https://www.sas-globalwafers.com/en/products/soi-wafer-en/ — L254–256
- [E01] Shin-Etsu Chemical original AI materials page (publication day UNKNOWN): https://www.shinetsu.co.jp/en/sustainability/sc_ai/ — L275
- [E02] Shin-Etsu Handotai America product portfolio (publication day UNKNOWN): https://sehamerica.com/products/ — L49,113
- [N01] US NIST final CHIPS award (2024-12-17): https://www.nist.gov/news-events/news/2024/12/biden-harris-administration-announces-chips-incentives-awards-globalwafers — L125,130–135; updated2025-10-06
- [T01] Tower SEC6-K downstream boundary (2026-05-13): https://www.sec.gov/Archives/edgar/data/928876/000117891326002609/zk2635309.htm — L57–68
- [T02] ST official PIC100 downstream boundary (2026-03-09): https://newsroom.st.com/media-center/press-item.html/t4761.html — L2612–2620
- [P01] Photonics21 ecosystem technical white paper (publication day UNKNOWN): https://www.photonics21.org/download/ppp-services/photonics-downloads/300_mm_Photonics_White_Paper.pdf — PDF P26 L826–848; P27–28
- [R01] Reuters original CEO interview — management claim (2026-08-31): https://www.reuters.com/world/asia-pacific/soitec-locks-customers-into-multi-year-deals-ai-wafer-demand-surges-2026-08-31/ — L179–205; corrected6–12month decision timing
