# SiPh WLBI / CPO 광전기 적격 검사능력 — 2026-10-06

조사 질문은 하나다: **2027–2029년 미국 AI 데이터센터향 SiPh/CPO 양산 증가가 실제 가동 가능한 적격 검사 처리능력을 초과하는가?** 기업 수익·주식·가치평가는 조사하지 않았다. 미국향 제품을 해외 foundry/OSAT에서 검사하는 경우도 공급범위에 포함해야 한다. 미국 내 설치 장비만 공급으로 제한하지 않는다.

기존 두 TARGET을 각각 재검토한 판정은 **OBSERVE 유지 / D>S UNKNOWN**이다. 부족이 없다는 확정 판정도 아니다. 두 대상에 실공정과 성장 촉매는 있지만, 같은 제품·recipe·기간에 필요한 적격 처리량과 가동 가능한 적격 처리량을 대조할 공개 숫자가 없다. 고객 필요일보다 모든 승인 대체 공급의 qualification 완료일이 늦다는 증거도 없다. EMERGING/FUTURE/REVIEW_LEAD로 승격하지 않는다.

## 1. TARGET와 공정 관계

| 기존 TARGET ID | 이번 범위 | 최종 상태 |
|---|---|---|
| silicon-photonics-wafer-level-burn-in | 고객별로 채택한 wafer-level reliability burn-in·laser stabilization | OBSERVE |
| cpo-optical-electrical-volume-test | 기존 PIC wafer 광전기 검사 범위를 유지; single/double-sided, die/OE/module의 후속·대체 공정 함께 검토 | OBSERVE |

WLBI는 stress·잠재결함 screening·laser stabilization이다. OE 통합 검사는 광·전기 성능을 측정해 KGD를 선별하고 조립 이후 광 경로와 전기 기능을 검증한다. 한 제품이 두 공정을 모두 거칠 수 있으나 공정 시간, 대상 단위, 장비, qualification이 다르다. 동일 고객의 중복 병목인지는 **UNKNOWN**. TARGET를 합치지 않았고 CAPA를 교차 합산하지 않았다.

## 2. 2027 / 2028 / 2029 수요와 실제 ramp 근거

| 달력연도 | 확인한 원문과 증거 수준 | 필요한 WLBI / OE 검사량 | 가동 가능한 적격 CAPA | 충돌 판정 |
|---|---|---|---|---|
| 2027 | NVIDIA는 2026-05-31 Spectrum-X Ethernet Photonics 생산을 이미 발표(S01). 2027을 CPO 산업 최초 양산으로 간주할 수 없음. Ayar CEO는 고객 2028–29 ramp를 위해 2027말 qualification 필요하다고 조건부 언급(S03). Celestial H2 FY2028 초기 기여 계획은 대략 2027하반기~2028년1월(S04,S26) | UNKNOWN | UNKNOWN | UNKNOWN |
| 2028 | Ayar 고객 제품의 2028–29 목표(S03); Celestial FY2029 확대 계획은 대략 2028년~2029년1월(S04,S26). 둘 다 출하·검사량 확정계약이 아님 | UNKNOWN | UNKNOWN | UNKNOWN |
| 2029 | Ayar CEO가 제시한 조건부 고객 ramp 범위에 포함(S03). 미국향 고객별 calendar2029 확정 물량 원문 확보 못함. FY2029를 calendar2029 전체로 대체하지 않음 | UNKNOWN | UNKNOWN | UNKNOWN |

스위치 scale-out CPO, compute scale-up optical I/O, SiPh pluggable transceiver를 하나의 ramp로 묶지 않는다. NVIDIA 생산 발표는 현존 상용화 근거이지만 실제 미국 현장 인수량·2027–29 주문량을 공개하지 않는다. Vera Rubin의 수백 공장 수나 GPU 규모는 CPO 전용 검사량이 아니다. Ayar CEO 발언은 직접 인터뷰의 계획을 확인하는 1차 진술이지만, Reuters 원문 접근 실패로 동일 Reuters 전재 기사에서 읽었다(S03). 독립 확인 두 건으로 세지 않는다. Ayar 공식 panel도 switch-first/compute-later 흐름과 향후2–3년 전망을 제시하지만 확정 물량은 없다(S22).

Celestial의 매출 시점은 제품 상용화 시점을 가늠하는 보조 근거일 뿐 wafer/die/OE 수의 입력값이 아니다. 매출·시장 CAGR·포트 TAM을 검사량으로 환산하지 않는다. 이번 조사 시점에 공개 확인되지 않은 10월6일 이후 발표 내용은 반영하지 않는다.

## 3. 필수 공정 여부와 qualification / 공급능력

### WLBI

특정 고객의 필수 채택은 확인된다. Aehr의 2021-03-01 원문은 integrated-laser SiPh 고객이 모든 die를 stabilization하는 100% production 단계라고 명시한다(S09). 2026-07-09에는 익명 lead SiPh 고객의 첫 fully automated 시스템 설치와 **production qualification 성공**을 명시한다(S05). 이것은 데모만 있는 공정은 아니라는 반증이다.

다만 모든 SiPh/CPO에 WLBI가 필수인지는 UNKNOWN이다. NVIDIA의 CPO는 외부 ELS를 별도 열제어·field-replaceable 형태로 둔다(S02). 따라서 integrated-laser die stabilization 물량을 모든 external-laser PIC의 WLBI 물량으로 확장할 수 없다. ELS 자체의 레이저 burn-in 요구는 별도이며 고객별 제조 flow는 미공개다. 익명 SiPh 공급자의 최종 미국 DC 고객·CPO 적용 비중도 UNKNOWN이다.

| 사례 | 실제 확인 상태 | 정량 CAPA로 인정 가능한 범위 |
|---|---|---|
| lead 고객 첫 fully automated FOX-XP | 설치·production qualification 성공 명시(S05) | 해당 사례에서 적격 cell 최소1 존재. 전체 fleet, SiPh recipe UPH/wafer/day UNKNOWN |
| 신규 networking/transceiver 고객 | 2026년5월까지 production system1, engineering systems2 인도(S06) | production용 인도1 확인. engineering2는 적격 HVM CAPA로 제외. 별도 생산 qualification 완료일 UNKNOWN |
| 6월17일 follow-on | 9-wafer XP1, AutoAligner/contactors, 6개월 내 인도 예정(S06) | 고객에 배정된 주문; 현재 설치·가동 여부 UNKNOWN |
| 7월9일 follow-on | 최대9×300mm 병렬 및 자동 handling(S05) | 추가 주문의 구성 사양. 기존 설치 cell과 후속 주문을 가동능력으로 중복 산입하지 않음 |
| 8월4일 follow-on | XP1,9 blades, 최대3500W/blade; H1 calendar2027 출하 예정(S07) | 신규 relief 후보이나 설치/qualification/양산 시작일 UNKNOWN |

9-wafer 병렬 사양은 wafers/day가 아니다. FY2026 10-K의 일반 FOX-XP 최대18-wafer와 hours–days 설명(S10)을 고출력 SiPh 구성이나 실제 고객 burn-in recipe에 적용하지 않는다. 2021년 전체 설치2500+ systems, 2026년 전체application 고객 수, backlog 금액을 SiPh 적격 장비 대수로 대체하지 않는다.

### 광·전기 통합 검사

광전기 성능 검사를 수행하는 상용 제조 flow와 KGD 검사 장비는 존재한다(S11,S14,S15). 다만 **모든 제품에 동일한 100% wafer-level 동시검사가 필수라는 고객 규정은 확보하지 못했다**. wafer KGD, singulated die/OE full-rate test, package/module BER의 recipe와 검출 결함이 다르므로 각 insertion의 필요량을 따로 비교해야 한다.

| 경로 | 현재 공개 증거 | qualification / 실제 처리량 |
|---|---|---|
| TRITON / V93000 / TEL | 상용 production-ready single-sided wafer cell, 자동 coupling/calibration(S11,S12). 공식 indexed PDF는 첫 production CPO system의 2025 출하를 표시(S13) | 고객별 production qualification 완료일·적격 installed fleet·UPH UNKNOWN. PDF 전체 retrieval 실패를 기록 |
| Teradyne / ficonTEC double-sided wafer | 2025-03-31 production system 발표(S14), custom300mm slotted chuck의 WLT-D2 사양(S16) | 고객별 적격 설치·wafer/day UNKNOWN |
| Photon100 | 2026-03-17 wafer/OE/module 광전기 platform 출시(S15) | 출시와 고객 HVM qual를 구분; UNKNOWN |
| ficonTEC DLTD1 | double-sided die/OE 최대3 parallel heads(S17) | effective multisite efficiency, UPH·qual UNKNOWN |
| SENKO / Advantest / VIAVI module workflow | 2026-09-14 simulated HVM demonstration, 200Gbps/lane BER 탈착 접속(S18) | 40UPH는 예시 산식. 실제 고객 CAPA·qual UNKNOWN |
| OpenLight / Advantest | 2026-06-23 end-to-end OE HVM 공동 개발 계획(S19) | 개발단계; 적격 CAPA로 제외 |

고객 qualification 정보가 공개되지 않은 제품을 일괄 “미완료”로 판정하지 않는다. 확인된 상태는 상용 제품/production-ready/출하/데모/개발로 구분하며 고객별 qual는 UNKNOWN이다. 반대로 production-ready 문구만으로 모든 고객에 적격인 장비라고 인정하지 않는다.

공식 FormFactor deck의 160+ globally installed systems는 광범위 photonics/R&D 계보를 포함할 수 있고 구성별 분해와 전체 PDF 확인이 부족하다(S13). 따라서 **적격 TRITON 160대**로 집계하지 않는다. 수천 optical probes도 test cells 수가 아니다. Chroma의 공개58635 ≤6-inch photonics wafer/LIV/NF/FF 장비는 300mm double-sided CPO full-rate OE 검사와 동등한 공급으로 합산할 수 없다(S25).

## 4. 제한 단계와 실제 병목 증거의 구분

| TARGET | 근거가 있는 기술적 제약 후보 | 실제 수요초과를 확인하는 데 필요한 미공개 자료 |
|---|---|---|
| WLBI | stress/stabilization dwell, 열 ramp/settle 및 고출력 wafer의 온도 제어; full-wafer contact/aligner handling(S05–S10) | 실제 recipe hours, 동시에 안정화 가능한 wafer 수, contact yield, OEE, retest, 월 queue 및 생산차질 원인 |
| OE wafer/die | 광 probe alignment/coupling, loss/polarization calibration, wafer warp 대응, end-face 검사·청소, RF/BER 자원과 serial communication overhead, 유효 multisite 병렬률(S11,S16,S17,S23,S24) | recipe별 cycle-time 분해, 실제 effective sites, 검사 범위, thermal settle, 실패·재검사율 |
| OE module | 반복 탈착 접속의 정확도·마모·교체/청소 downtime, all-lane 200Gbps BER(S18) | 고객 qualified flow의 실측 UPH/OEE·connector 수명과 예약 대비 월 처리량 |

S18의 40UPH×24시간×30일>28000/month는 제조 조건을 설명하는 **예시**다. measured sustained40UPH, OEE100%, 고객 volume shipment로 읽지 않는다. 내구성 주장도 simulated HVM demo로 분류한다. S20의 IHP 200mm photodiode edge-coupling die당5초 미만은 특정 측정 사례다. 기존 원장에 있던 일반 PIC100초 초과 설명과 측정 범위가 달라 서로 비교하거나 전체 CPO 필요 장비 수를 계산할 수 없다.

S24는 2026-10-15 예정 SEMICON West 발표의 공개 초록이다. 조사 기준일10월6일에 이미 발표한 양산 실측으로 취급하지 않는다. 초록의 “bottleneck”과 2026–27/2027 roadmap은 공정 난도·향후 계획이지 적격 공급 부족 수치가 아니다.

따라서 **실제 부족을 일으킨 병목 단계는 두 TARGET 모두 UNKNOWN**이다. 관찰 우선순위는 WLBI의 stress/thermal/contact dwell과 OE의 optical interface/calibration/full-rate multisite·module connector 유지보수다. 일반 ATE chassis 생산 부족으로 단순화할 근거는 없다.

## 5. 수요–공급 충돌 계산 규칙

비교 단위는 customer/product/architecture/recipe/insertion별 월 처리량이어야 한다. first-pass 투입량을 기준으로 잡으면 공급은 qualification이 완료된 가동 장비의 실측 처리량에서 재검사·정비·교정 시간을 반영해야 한다. 최종 양품 요구량을 first-pass 투입량으로 바꾸려면 die/wafer 수와 관련 수율도 필요하다. 수율과 재검사율을 수요와 공급에 동시에 반영해 이중 계산하지 않는다.

WLBI 예비 산정에는 qualified independent wafer slots, 유효 가동시간, stress/thermal/handling 시간과 retest 부담이 필요하다. OE에는 실제 effective multisite 수, recipe cycle time, optical alignment/calibration/thermal/cleaning downtime, BER 측정시간, OEE가 필요하다. 병렬·중첩 가능한 단계를 모두 직렬 합산하는 가정도 피해야 한다. 이 변수들은 공개 자료에서 같은 고객/제품 조합으로 확보되지 않았다.

기존 고객에 배정된 장비는 그 고객의 수요와 함께 비교한다. 이미 예약된 공급을 신규 수요에 남은 free capacity로 취급하지 않는다. 전체 수요와 전체 적격 공급을 비교할 경우 동일 지역/기간/규격의 양쪽 모두를 집계해야 한다. 신규 미배정 수요를 비교할 경우 미예약 적격 잔여능력만 공급으로 쓴다.

이번 연도별 Dmin/Dmax와 Smin/Smax는 모두 null/UNKNOWN이다. null을0으로 바꾸지 않는다. D>S 부족 구간과 시작/종료일도 null이다. 실제 고객이 필요한 날짜에 승인된 대체 경로를 포함한 모든 적격 공급이 불가능하다는 timing 증거도 미확인이다. **2027,2028,2029의 충돌은 모두 UNKNOWN**.

## 6. 주문→설치→qualification→양산 lead time / 예약

Aehr 6월17일 원문은 고객 engagement 후 약6개월 안에 2026년5월 production1+engineering2 인도 목표를 달성했다고 설명한다(S06). 이는 특정 사례의 engagement→인도이며 실제 주문 날짜와 인도→installation→qualification 각 구간의 길이가 아니다. 후속 주문의 6개월 내 인도 계획은 대략2026년말 후보지만 완료는 UNKNOWN.

8월4일 주문 발표에서 H12027 예정 출하까지는 약5–11개월이다(S07). 계산된 단일 사례의 발표→출하 범위로 기록하며 범용 lead time, 생산지연 또는 신규 고객 backlog로 해석하지 않는다. 고객의 requested required-by date가 없으므로 “필요일보다 늦다”는 판정은 불가하다. lead 고객은 첫 cell qual 성공을 이미 확인했으나 모든 후속장비가 인도 즉시 같은 제품으로 승인된다는 보장도 없다(S05).

광전기 장비들의 상용 출시일은 개별 고객 주문→인도→설치→qual→양산 lead time이 아니다. 공개 고객별 날짜는 UNKNOWN이다. 기존 고객 장비 주문은 확인되지만 산업 전체 tester time 예약, OSAT 슬롯 계약, 잔여 free capacity는 양 TARGET 모두 UNKNOWN이다.

## 7. relief / 반증 / 우회

- WLBI에는 이미 설치·qual 성공한 자동화 cell, 추가9-wafer XP 주문과 AutoAligner/handling 개선이 있다(S05–S07). 2026년말 인도 및 H12027 출하가 relief 후보이나 실제 qual 완료/순증 처리량 날짜는 UNKNOWN이다. 자동화로 handling 시간이 줄어도 stress dwell이 지배적이면 증가폭은 다르다.
- 동일 안정화/스크리닝을 package/PCB 이후 실시하는 기술적 대안이 원문에 있다(S09). DiePak을 통한 singulated die/module 경로도 있다(S10). 고객별 승인과 available CAPA는 UNKNOWN이며 assembly 이후 잠재불량 검출은 scrap/재작업 비용을 늘릴 수 있다. 다른 제품용 Sonoma/메모리/SiC 장비를 SiPh 적격 relief로 자동 산입하지 않는다.
- OE에는 자동 calibration/coupling TRITON, double-sided wafer, Photon100, 최대3-head die 경로가 있다(S11,S14–S17). single-sided 장비는 custom double-sided 3D 구조의 자동 대체 공급이 아니다.
- SAM-T 내구성 master와 ganged multi-engine 접속은 module connector downtime을 줄이는 완화책이다(S18). demo→HVM 고객 승인 및 실제 relief UPH는 UNKNOWN이다.
- Ayar는 2026년3월 자금조달의 용도에 high-volume production **및 test capacity** 확충을 명시했다(S21). 수요 증가에 앞서 공급 투자가 진행될 가능성을 뒷받침하지만, funding이 installed/qualified 장비 예약 수를 뜻하지 않는다.
- wafer KGD를 die/package final test로 옮기는 부분 우회는 가능하나 검출 결함이 완전히 같지 않다(S15,S17). wafer 불량이 고가 assembly로 넘어가거나 final test 부담이 증가하므로 “검사 자체 제거”가 아니다. 고객 approval과 해당 경로의 여유능력 없이 relief 확정은 불가하다.
- compute CPO ramp의 qualification 지연이나 아키텍처 변경, 기존 pluggable/NPO 채택 지속은 수요시점도 바꿀 수 있다. 제품별 확정 지연·우회 물량은 UNKNOWN이며 신규 확정 사실로 사용하지 않았다.

## 8. 저장 / 이력 / 다음 승격 조건

이 조사와 source26개(원문 bounded excerpt/hash 또는 paraphrase, 접근 한계 명시), 연도별 null 수급 비교, qualification register, relief/반증을 기존 두 TARGET의 **신규 history 각1개**로 append한다. 기존 TARGET 이름/ID/stage 및 과거 history는 변경하지 않는다. 새 TARGET도 만들지 않는다. 원장은 `future-bottleneck-data:future-tracking.json`; main에는 본 REPORT, source register, 개별 history, preserving registration, 검증 및 storage receipt를 저장한다. main의 연구 bundle과 live sidecar는 구분한다.

수동 on-demand 원문 재조사다. 최초 탐지일·EARLY 성공·first S3·투자성과를 새로 만들지 않는다. source 파일은 전체 원문 snapshot이 아니며 PARTIAL/metadata/paraphrase를 명시한다. 원문 출판일을 확인하지 못한 경우 null로 유지한다. 기존 수집 DB, 투자/기업 ticker 필드, history를 덮어쓰지 않는다.

다음 승격 검토에 필요한 결정적 입력은 월별 고객·제품별 실제 required test load, approved recipe와 적용률, installed qualified fleet, sustained UPH/wafer/day/OEE, yield/retest, 예약/미예약 능력, 필요한 날짜 및 신규 장비/대체 flow qual 완료일이다. 이를 승인된 모든 대체 경로와 함께 비교해 같은 기간 **실제 필요한 적격 처리량 > 실제 가동 가능한 적격 처리량**이 입증되거나 필요일을 넘기는 전체 적격 공급 지연이 확인되어야 한다. 그 전에는 OBSERVE다.

## 원문 register

각 S번호의 URL·출판일 확인 여부·locator·bounded excerpt·hash·근거 구분·한계는 `sources.json`에 있다. Reuters 원문 실패, FormFactor PDF 전체 retrieval 실패, 미래 발표 초록은 명시적으로 제한했다. 공급 coverage는 PARTIAL이며 업계 전체 미공개 고객 CAPA를 채웠다고 주장하지 않는다.
