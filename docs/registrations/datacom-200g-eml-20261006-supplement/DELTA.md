# 계약·고객인증 추가 확인: 기존 조사 이후의 새 증거

기준일 2026-10-06. 기존 TARGET `datacom-200g-eml-qualified-die-capacity`의 후속 기록이다. 앞선 전체 조사와 근거 파일은 변경하지 않았다. 이번에는 계약 부속서, 신규 공급자 발행사 문서, LightCounting 자체 연구 원문에서 얻은 추가 사실만 기록한다. 출처와 읽은 위치는 `sources.json`에 있다.

## 1. 예약 계약은 신규 적격 공급 완료를 뜻하지 않는다

AXT–Coherent의 SEC Exhibit 10.3을 확인했다(S01). 2026년 6월 25일 계약 효력 발생 당시, 계약 대상 6-inch InP 프로그램은 개발·파일럿 단계였다. 증설 대상은 2026~2028년 결정성장 furnace와 substrate 제조라인이다. 계약은 낮은 수율, 결정성장 확대, 수출허가 위험도 명시한다.

2027년 1월부터 월별 capacity commitment 미달에는 정해진 기한 내 보충 공급 또는 해당 미사용 선급금 반환 의무가 있다. 이는 구체적인 월별 공급 의무를 확인하는 근거지만, 실제 미달 발생의 증거는 아니다. 60일은 미달을 구제하는 계약상 기간이며 wafer 제조 lead time이 아니다.

결정적인 월별 capacity/MOQ 표와 wafer 사양은 삭제돼 있다. Prime·mechanical·dummy wafer가 구분되므로 전체 예약 금액을 활성 laser wafer로 환산할 수도 없다. 200G EML 배정은 미공개다. 계약 시점의 pilot 상태를 10월 현황으로 단정하지 않으며, Coherent의 기존 6-inch fab 양산이 전부 이 신규 소재 계약에 의존한다고 가정하지 않는다.

Lumentum 계약의 July 29 8-K(S02)는 완전한 계약서를 September 30 종료 분기의 10-Q에 부속한다고 예고한다. 분기 종료일은 제출일이 아니다. 이번에 읽은 공개 자료에는 최소연간 wafer 수량이 없고, 해당 전체 부속서를 얻지 못했다.

공정 후보는 `6-inch InP 결정성장 → prime substrate 가공·적격 release`로 더 좁혀 메모했다. 관련 기존 TARGET은 `inp-qualified-exportable-substrates`이며 새 TARGET은 만들지 않았다. 이 단계가 미국 고객인증 200G EML 공급의 실제 제한 단계라는 증거는 아직 없다.

## 2. Yuanjie의 200G 고객 검증은 완료 공급과 구분된다

2026년 8월 30일 IR 기록 원본 DOCX를 내려받아 OOXML 본문을 읽었다(S03, 발행사 문서의 Sina 미러). 100G EML 및 CW 70/100mW의 batch 공급과 200G EML의 고객 검증 진행을 명확히 구분한다. 2027~2028년 고급 제품 CAPA 배분 질문에는 높은 광출력 제품 비중 확대만 답했으며 200G EML 수량은 제시하지 않았다. 미국 자회사는 건설 중이고 향후 생산 중심은 중국이라고 답했다.

반기보고서의 200G single/differential EML 카탈로그·2025 OFC 개발 전시·설계 정형화(S04)는 기술 진전을 보여준다. 그러나 그 문구를 미국 고객 승인 완료로 해석하지 않는다. 비기밀 포장 환경에서의 일반 제품 batch 공급 설명도 200G만의 공급을 증명하지 않는다. 이 신규 공급자의 미국 고객인증 200G die/월, 최초 승인 출하일, 예약·잔여 CAPA는 UNKNOWN이다.

## 3. 2027년 중반 위험 신호가 추가됐지만 주문 과대계상도 경계해야 한다

LightCounting 원문을 날짜순으로 대조했다(S05~S09). 이는 연구기관의 자체 추정·전망이고 공급자의 실제 accepted die 실적표는 아니다.

| 원문 시점 | 새로 확인한 진술 | 200G EML 수급 판정에 적용하는 범위 |
|---|---|---|
| January 2026 | 전년도 신규 InP CAPA의 대부분이 생산에 적격화됐을 것으로 추정 | 고객·라인별 승인 확인치가 아니므로 전체 숫자로 반영하지 않음 |
| April 2026 | 전체 InP EML/laser 공급보다 수요가 30% 많다는 추정, 연말 완화 예상. GPU 공급 증가 시 2027까지 지속 가능 | 30%를 US 고객인증 200G 전용 gap로 사용하지 않음 |
| July 2026 | InP laser 부족이 2027년 중반까지 이어질 가능성. 광범위 component shortage와 double ordering 경고 | 2027 위험 시점 단서 강화. 다만 범위가 전체 InP이고 고객별 firm die/qualified output 없음 |
| August 13, 2026 | 광공급망의 공급자 수가 과거 2~3에서 5~7로 늘고 qualification·관리가 과제로 부상 | 5~7을 200G EML 적격 공급자 수로 세지 않음 |
| September 2026 | 1.6T Ethernet volume shipments와 기존 100/400/800G 성장 동시 확인 | 실제 1.6T ramp를 지지하나 US/EML/CW별 die 수량은 제공하지 않음 |

July 원문은 backlog와 bookings에 double ordering이 섞인다고 명시한다. 따라서 장기간 backlog를 고객의 최소 실사용 수요와 같다고 놓을 수 없다. 그 규모를 알 수 없으므로 임의로 일정 비율을 차감하지도 않는다. April의 2028~2029 1.6T ZR/ZR+ 성장 전망은 coherent DCI 경로이므로 이 TARGET의 datacom EML200 수요에서 제외했다.

## 4. UNKNOWN의 이유를 분리했다

| 종류 | 이번에 해당하는 항목 |
|---|---|
| 공개 문서에서 삭제된 정보 | AXT 월별 capacity·MOQ·사양·가격·추가 CAPA 우선권 비율 |
| 읽은 현행 공시에서 얻지 못한 정보 | Lumentum July 전체 예약 계약서와 die 용도별 배정 |
| 아직 완료로 확인되지 않은 고객 검증 | Yuanjie 200G EML 고객 검증·US 승인 SKU·최초 적격 출하 |
| firm 수요로 쓸 수 없는 추정 | LightCounting 전체 InP gap·미래 shortage 시점·광범위 공급자 증가 |

추가 자료는 2027 위험 단서와 신규 CAPA의 적격 전환 조건을 더 구체화한다. 그러나 2027·2028·2029의 미국 고객인증 200G EML 필요 die와 accepted 공급 die를 수량 또는 필요일로 충돌시킨 증거는 추가되지 않았다. 판정 승격은 없다. 기존 원장에 새 history만 추가하며, 이전 history·메타데이터·TARGET 수를 그대로 보존한다.
