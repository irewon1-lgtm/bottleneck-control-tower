# 미국 AI DC용 고객인증 200G/lane EML die: 2027~2029 재조사

조사 기준일: 2026-10-06. TARGET: `datacom-200g-eml-qualified-die-capacity`.

**판정: OBSERVE.** 기존 OBSERVE를 전제로 삼지 않고 공급자·모듈업체·플랫폼업체·SEC 원문 27건을 다시 읽어 판단했다. 현재 전체 EML/InP 공급 압박과 200G 제품의 실제 상용 공급은 확인된다. 그러나 2027·2028·2029 각각 미국 AI 고객에게 필요한 고객인증 200G EML die 수량과 같은 고객·규격·기간에 공급 가능한 적격 die 수량을 맞춘 자료가 없다. 미래 부족은 입증되지 않았으며 상태를 승격하지 않는다. UNKNOWN은 공급이 0이라는 뜻도, 부족이 없다는 뜻도 아니다.

이 조사는 기업 가치·주가·ASP 분석이 아니다. 새 TARGET을 만들지 않으며 기존 TARGET의 메타데이터와 모든 기존 history를 보존하고 별도 재조사 history를 추가한다. 원문 URL·읽은 위치·주장과 한계는 [sources.json](sources.json), 기계 판독 기록은 [history-append.json](history-append.json)에 있다. 문서 전체의 보존·완전한 추출을 주장하지 않는다. InnoLight 한 건은 발행사 IR 기록의 PDF 미러이며 이를 표시했다.

## 1. 같은 기간에 무엇을 비교해야 하는가

| 연도 | 확인한 수요 시점 근거 | 필요한 US 고객인증 200G EML die | 실제 공급 가능한 동일 적격 die | 충돌 판정 |
|---|---|---|---|---|
| 2027 | InnoLight 주요 고객이 2027 guidance와 orders를 제시했고 800G/1.6T 주문이 2026 대비 빠르게 증가한다고 설명. H2 2027 신제품/NPO ramp도 예상 | UNKNOWN | UNKNOWN | D>S 및 need-date 지연 미입증 |
| 2028 | InnoLight는 신제품/NPO의 더 큰 출하를 예상. Mitsubishi·Sumitomo의 시장 전망은 1.6T·3.2T 확대를 표시 | UNKNOWN | UNKNOWN | 미입증 |
| 2029 | 공급자 시장·아키텍처 로드맵은 광연결 확대를 전망. 200G EML만의 미국 firm orders/필요일은 확인되지 않음 | UNKNOWN | UNKNOWN | 미입증 |

근거: E19의 outlook·Q14, E11 slide 10, E18 slides 9~10, E15 slide 14. 2027 주문 가시성은 단순 TAM 전망보다 강하지만, EML/SiPh·800G/1.6T·미국/기타 지역 물량의 분해가 없다. NPO/CPO의 매출 ramp와 chip-to-chip 2029/30 전망은 CW/VCSEL 경로를 포함하므로 전부 EML 수요로 넣지 않았다. NVIDIA의 Rubin 1.6T급 연결·200G SerDes 상용화 역시 EML die 구매 수량을 제공하지 않는다(E25~E26).

전세계 optical-lane CAGR, 전체 EML 시장 매출, DSP 매출 전망, 800G 이상 모듈 전망은 수요 방향의 보조 근거다. 100G/lane·CW·VCSEL·telecom·비AI 물량이 섞이거나 US/아키텍처 분해가 없어 firm US 200G die 숫자로 환산하지 않는다.

비교는 최소한 고객, 승인 SKU/라인, 파장, 온도, baud·driver/package 조건, 월 또는 분기, need-date를 맞춰야 한다. **기존 배정 수요는 배정 공급을 포함한 총 공급과 비교**하고, **새 미배정 수요만 잔여 미예약 슬롯과 비교**한다. 총수요를 잔여 공급에 비교하면 예약을 이중으로 부족 처리한다. 재고·이월·고객 조립 손실·교체품 수요도 UNKNOWN이다. 연간 합계가 맞더라도 특정 분기 납기 충돌은 따로 검증해야 한다.

## 2. 모듈당 die 구조와 3.2T 전환의 함정

| 실제 선택한 광송신 구조 | transceiver 하나의 200G EML die | 근거/제약 |
|---|---:|---|
| 800G = 4×200G EML | 4 | Source 200G-lambda 제품(E20~E21) |
| 1.6T = 8×200G EML, DR8/2×FR4/2×LR4 | 8 | Lumentum 구성·Source 제품(E03,E21) |
| 3.2T = 16×200G EML | 16, 조건부 | 선택한 BOM이 이 구조일 때만 성립. 기본값·주류 양산 BOM으로 확인한 것은 아님 |
| 3.2T = 8×400G EML | 0 | 대신 400G EML 8개. 공급자 로드맵/데모(E03,E17,E22), 적격 양산은 별도 확인 필요 |
| SiPh PIC + CW laser pluggable/CPO/NPO | 0 | CW die 개수는 광분배·출력·손실·중복 설계에 따라 달라 UNKNOWN |
| VCSEL 단거리 경로 | 0 | 광섬유·거리·링크 예산이 달라 모든 single-mode EML 링크를 대체하지 못함 |

8×200G 모듈에서 DFB laser와 EAM이 한 die에 통합된다. 두 부분을 각각 laser die로 세면 안 된다. 1.6T 양방향 링크 양끝에 이 모듈을 하나씩 쓰면 총 16개지만, 모듈/포트 전망이 이미 양끝을 포함하면 다시 2배 하지 않는다. 3.2T 광엔진이라는 이름만으로 EML die 16개를 가정하지 않는다. 특히 CPO는 별도 CW 광원 경로가 있다.

설치용 기본 수요 산식은 `8×1.6T(200G EML) 모듈 + 4×800G(200G EML) 모듈 + 16×3.2T(200G EML) 모듈`이다. 각 아키텍처의 US 모듈 수량, 조립 손실·재고 변경·교체품을 알아야 공급자가 납품해야 할 적격 die 수요가 된다. 이 변수들이 미공개여서 숫자를 대입하지 않았다. Fab yield는 공급의 good-die 계산에 반영하며 고객 조립 yield와 혼합하지 않는다.

## 3. 공급자는 존재한다. 적격 공급량은 공개되지 않는다

| 공급자 | 확인된 200G 상용성/qualification 수준 | 확인 가능한 적격 200G die/월 및 잔여능력 |
|---|---|---|
| Lumentum | Q4 FY26 100G·200G EML record shipments. 제품·at-scale 공급 주장. 200G 매출비중 >25%(E02,E04~E05) | UNKNOWN. 매출비중으로 unit mix를 구하지 않음 |
| Broadcom | 2025-03-13에 200G EML production 및 누적 millions 출하 명시. Die/CoC 제품(E08~E09) | UNKNOWN. 누적 출하는 연간 CAPA가 아님 |
| Mitsubishi Electric | 200G EML mass production Apr2024 시작(E10) | UNKNOWN. 전체 EML 누적 1억개와 분리 |
| Coherent | 112GBd 200G 제품, non-hermetic package용 qualification. 6-inch 전체 InP volume production(E12~E14) | UNKNOWN. 고객별 200G fab/lot 승인·accepted output 미공개 |
| Sumitomo Electric/SEDI | 200G 대응 및 4-inch EML/CW 대량제조 기술(E18) | UNKNOWN. 전체 optical-device 증설을 전용 200G 공급으로 환산하지 않음 |
| Source Photonics/Dongshan | 자체 200G EML을 쓴 800G/1.6T production shipments, 1.6T EML/SiPh production volume와 Delta interoperability(E20~E23) | UNKNOWN. captive die를 merchant 시장의 가용 die로 추가하지 않음 |
| Zetta 등 신규 후보 | Zetta 200G CWDM4 mass-production-ready 개발 발표(E27) | 실제 고객승인 출하·가용량 미확인. 적격 공급 합계에 추가하지 않음 |

제품 개발, 신뢰성 시험 통과, wafer-platform qualification, module interoperability, 특정 고객이 승인한 양산 라인·SKU·출하 lot acceptance는 서로 다른 증거다. Commercial shipments는 실제 공급과 적어도 일부 고객 채택의 강한 신호지만 모든 미국 CSP의 승인이나 spare capacity를 증명하지 않는다. Coherent의 packaging-qualified라는 문구를 특정 미국 고객의 die 승인으로 확대하지 않았다. Source의 모듈 출하 역시 외부 판매 가능한 laser die capacity를 뜻하지 않는다.

신규 중국 공급자에 대한 검색 결과와 MACOM의 PD/CW/driver 정보는 200G EML 고객적격 물량으로 확인되지 않아 합산하지 않았다. 이름이 확인되지 않은 HKEX draft business section의 200G 카탈로그와 일반 qualification 설명도 수급 계산에서 제외했다. 공급자가 없다고 판단한 것이 아니라 검증된 적격 물량을 얻지 못한 것이다.

## 4. 현재 압박과 실제 제한 단계

Lumentum은 EML capacity가 near-term constraint라고 직접 밝혔다(E01). Coherent는 industry-wide InP shortage에 대응한 Sherman 투자를 설명한다(E16). Dongshan은 EML 광칩 공급 압박에 자체 증설로 대응한다고 답했다(E23). InnoLight는 optical/electrical chip·PCB를 함께 tight한 물료로 설명하고 납품 확보 조치를 밝혔다(E19). 따라서 현재 공급 압박을 단순한 추측으로 보기는 어렵다. 다만 이 발언들은 범위와 기간이 달라 2027~2029 US 고객인증 200G die shortage의 동일 숫자가 아니다.

| 제조 단계 | 읽은 증거 | 이 TARGET의 실제 제한 단계로 확정 가능한가 |
|---|---|---|
| InP substrate | AXT 계약으로 Lumentum·Coherent 장기 예약/증설 확인(E24) | 아니오. 수량·200G 배정·미달량 미공개 |
| Epi/regrowth | EML 다단계 epitaxy의 공정 난도(E05) | 아니오. Epi reactor throughput/WIP/yield와 고객 필요량 비교 없음 |
| Laser wafer fab | Fab/InP 증설과 공유 공급압박(E03,E14,E16) | 가장 근거가 많은 front-end 후보이나 200G 전용 제약 및 fab/epi 중 어느 단계인지 미확정 |
| Dicing·screening·laser die test | Die/CoC 제품·사양(E04,E09) | UNKNOWN. Tester hours·test yield·queue 미공개 |
| Burn-in/reliability | GR-468와 package qualification(E05,E12) | UNKNOWN. 양산 burn-in 시간·병렬 처리량·불량률 없음 |
| CoC/laser package/module assembly | Non-hermetic option·hybrid 후공정·실제 volume module(E03,E12,E21) | UNKNOWN. Laser-package와 module capacity를 분리한 병목 증거 없음 |
| Customer product/line qualification | 신규 내부·외주 라인의 고객 승인과 이전 시 재승인(E06) | 실제 gate 확인. 해당 200G 고객의 대기기간·실패·출하 제한량은 UNKNOWN |

현재 확정할 수 있는 가장 좁은 진술은 **전체 EML/InP front-end 공급 압박과 고객 승인 gate의 존재**다. 특정 epi reactor, laser die test, burn-in, packaging이 실제 제한 단계라고 확정하지 않는다. Epi/regrowth throughput과 공유 InP fab의 200G 적격 배정은 별도 후보 메모로만 기록했다. 새 TARGET은 생성하지 않았으며 substrate 관련 증거는 기존 `inp-qualified-exportable-substrates`에 연결한다.

GR-468 qualification은 양산 burn-in의 동일 기간/동일 처리량을 뜻하지 않는다. 신규 제조라인이 생겼다는 사실도 accepted 200G die가 즉시 늘었다는 뜻은 아니다. E06의 고객 승인 요건은 실제 생산라인·외주이전의 재qualification 필요성을 확인하지만, 보편적인 6개월/12개월 기간을 제공하지 않는다. 그런 기간을 임의로 넣지 않는다.

## 5. 예약·배정·lead time

| 확인된 사실 | 의미 | 알 수 없는 부분 |
|---|---|---|
| Lumentum EML+CW laser-chip backlog >2년(E03) | 이미 확보된 장기간 주문/출하 가시성 | 200G 전용 예약량, 매월 CAPA 점유율. Backlog 기간을 제조 lead time으로 취급하지 않음 |
| NVIDIA 비독점 광제품 purchase/capacity rights(E01,E16) | 실제 capacity 확보 계약 존재 | EML200와 CW/UHP의 분리·US 고객별 최소 die 수량 |
| InnoLight LTA·선급·신규 supplier, 일년 이상 물료 선급 자산(E19) | Upstream 배정 확보와 납품 대응 | 200G EML die 예약량/잔여량. 일부 고객 LTA는 아직 협상 |
| AXT-Coherent 6-inch substrate 공급/증설 계약, AXT-Lumentum 6년 최소연간 예약(E24) | Upstream 공급 확보가 계약 수준에서 구체적 | Wafer 수량·200G 전용 배정·die 환산·잔여 substrate capacity |

AXT의 Coherent 계약은 2026~2028 증설과 capacity commitment를, Lumentum 계약은 최소연간 예약을 규정한다. 이는 좁은 upstream 후보의 실물 계약 근거이면서 확보된 소재 공급이라는 relief다. 금액을 wafer 수나 die 수로 환산하지 않는다. 예약금은 장래 shipment credit이며 현재 공급 부족 개수가 아니다.

특정 고객인증 200G EML의 제조 cycle time, quoted lead time의 변화, 지연 주문 수량, allocation 비율·취소, 2027~2029 납기 미달을 입증하는 원문은 이번에 확인하지 못했다. 전사 allocation 진술과 mixed-product backlog를 그 증거로 대신하지 않는다. 200G mix가 mid2027 과반, end2026 undershipping, LTA through2027라는 2차 transcript 단서는 공식 transcript/audio로 대조하지 못해 결정적 증거에서 제외했다. 검색 실패나 미공개는 해당 사실이 없다는 입증이 아니다.

## 6. 언제 relief가 적격 공급이 되는가

| 증설/개선 | 공개 일정·범위 | 200G 고객적격 공급 시작일 |
|---|---|---|
| Lumentum 기존 fab all-EML +50% | EndCY26 vs endCY25 계획(E03) | UNKNOWN. 100G/200G와 승인된 라인 배분 미공개 |
| Coherent 6-inch 확대·상대 yield 개선 | Total InP production doubling 2026·2027. Sep2026 원문에서 계획 재확인(E14~E15) | UNKNOWN. EML/CW/PD/PIC split·각 200G 고객의 승인 미공개 |
| Mitsubishi EML 투자 | FY30 >3× FY26 목표, FY26 400억엔 투자(E11) | UNKNOWN. Calendar2027/28/29 qualified output과 분리 |
| Sumitomo intra-DC optical devices | 2028/2023 12× 계획, EML/CW 포함(E18) | UNKNOWN. 200G-only accepted output 없음 |
| Source/Dongshan 자체 칩·모듈 증설 | 현재 물료 압박 대응과 투자(E23) | UNKNOWN. Die와 module·captive/merchant split 없음 |
| InnoLight 상위 공급자 물료 개선 | H2 2026~H1 2027 capacity release 기대(E19) | UNKNOWN. 광칩/PCB 등 범위가 넓음. 실현 시 부족의 중요한 반증 |
| Lumentum UK/Greensboro | UHP UK late-summer2027, Greensboro CW mid2028(E03,E07) | 직접 200G EML 증설에서 제외. SiPh 대안의 간접 relief 가능성 |

2024 Coherent의 6-inch capability/qualification 진행(E13)을 오래된 계획으로만 취급해서도 안 된다. 2026에는 aggregate volume production과 상대 yield 개선 설명이 있어 진전은 확인된다. 반대로 6-inch 면적이나 all-InP 증설률만으로 customer-qualified 200G output을 계산해서도 안 된다. Qualification 완료일과 월별 accepted output이 확인될 때 해당 물량을 supply balance에 넣어야 한다.

## 7. 대체와 다중소싱이 부족 주장에 주는 반증

SiPh/CW는 단순한 연구 가능성에 머물지 않는다. Lumentum Q4 FY26에는 실제 1.6T 초기 출하 일부가 내부 CW를 썼고, Source는 1.6T EML·SiPh variant 모두 production volume 공급 가능 및 switch interoperability를 발표했다(E02,E21). 따라서 모든 1.6T 모듈을 EML 8개로 계산하는 전제는 틀린다. Sumitomo의 2028 CW 비중 증가 전망(E18)은 방향성 보조 근거이며 실제 고객 mix 수치로 쓰지 않는다.

다만 CW laser 하나를 기존 EML 자리로 바꾸는 것은 아니다. PIC·modulator·driver·optical coupling·power budget·package·approved SKU를 변경하고 고객 승인을 받아야 한다. 실제 대체율·승인기간·가용 CW/PIC capacity는 UNKNOWN이다. SiPh로 EML 필요량이 줄어도 InP CW 수요가 늘 수 있어 공유 fab 압박 전체가 해소된다고 단정하지 않는다.

Broadcom·Mitsubishi·Lumentum·Coherent·Sumitomo·Source라는 복수 공급 경로는 중요한 반증이다. 한 공급자의 constrained 발언만으로 전세계 고객인증 공급을 대신할 수 없다. 동시에 서로의 die가 모든 고객에서 교환 가능한지는 검증되지 않았으므로 nominal multi-vendor supply를 곧바로 free qualified supply로 합산하지 않는다. VCSEL의 거리/광섬유 차이와 400G EML의 데모 단계도 반영했다.

## 8. 결론을 바꾸는 관측과 결정적 UNKNOWN

상향 판단에는 적어도 특정 미국 고객/모듈 BOM의 200G die 최소수요와 필요일, 같은 승인라인의 배정 포함 accepted output, 이미 예약된 물량과 잔여 슬롯, 재고, 신규 적격 release 일정을 함께 알아야 한다. 그 비교에서 수량 초과 또는 필요일 이후 실제 공급 지연을 확인하고 증설·다중소싱·아키텍처 전환을 넣어도 지속되어야 한다.

결정적 UNKNOWN은 고객별 US 주문량/need-date와 EML mix, 200G wafer 투입·good die·공정/최종 시험 수율, 제조/시험/burn-in 처리량, 고객별 qualification 기간·승인라인, 예약·잔여 CAPA, 재고·ASP, 새 CAPA의 accepted release 날짜다. 비공개 숫자를 시장 매출·예약금·wafer 면적·누적 출하로 복원하지 않았다.

실제 2027 공급 완화, 200G 고객승인 증설, 정상 납기, 승인된 다중소싱과 SiPh SKU 확대로 동일 기간 수요가 충족되면 shortage 주장은 약해진다. 현재는 그 relief가 있다는 근거와 현재 pressure가 있다는 근거가 공존한다. **2027·2028·2029 모두 D>S는 UNKNOWN이고, 좁은 공정 병목도 미확정이므로 OBSERVE를 새로 판단한다.**

## 저장·검증

Live 원장: `future-bottleneck-data:future-tracking.json`의 기존 TARGET history에 추가. Main 근거 번들: `docs/registrations/datacom-200g-eml-20261006/`. Registration patch: `docs/registrations/20261006-datacom-200g-eml-deep.json`. 저장 전 모든 기존 history·TARGET 메타데이터 보존, TARGET 수 불변, 새 history 한 건, operation 재실행 idempotence를 확인한다. 원격 commit/blob readback와 main 반영 결과는 `storage-receipt.json`에 별도 기록한다. 미래 부족 입증·선행예측성과·strict provenance PASS는 주장하지 않는다.
