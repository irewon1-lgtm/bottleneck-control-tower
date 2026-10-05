# 1차 조사 검토 목록

수동 원문 판독 주석 기반 개발 예시. BACKFILL이며 EARLY/선행탐지 성과가 아닙니다.

## PrSM Increment 2 계약 / 시험·생산 전환 — HOLD

검토 ID: `review-2ff64e94fa6602472f6ed54b` · 정식 TARGET ID: 없음 · `BACKFILL`

원문이 뒷받침하는 범위: model=PrSM Increment 2

판독: MANUAL_SOURCE_READING_BY_ASSISTANT_USER_NOT_YET_VERIFIED / Codex: preserved full-source reading; not automatic extraction or independent gold (자동 추출 아님)

출처: Defense News · https://www.defensenews.com/industry/2026/09/22/us-army-awards-lockheed-martin-12b-prsm-contract/
문서 ID: `74b13ec8-e0f3-4cc4-9a69-b3ee58d2b6ed` · SHA-256: `f72dcb5f9b163c2377bc43cf553fdfec3bf0c879b0f53700c173485da8f735dc`
공개: 2026-09-22T15:04:23.290000+00:00 · 확보: 2026-10-04T20:30:41.131099+00:00 · 보존 가용: 2026-10-04T20:30:41.131099+00:00

최초 검토: 2026-10-05T15:35:13.020752+00:00 · 엄격 후보 최초 충족: UNKNOWN

- 원문 사실/표현 [FACT, REPORTED]: PrSM Increment 2 초기 생산·향후 주문에 관한 IDIQ 계약 보도. Lockheed 발표 재인용으로 표시.
  > The indefinite-delivery, indefinite-quantity contract covers initial production and future orders of Increment 2 of the Precision Strike Missile, or PrSM , according to a Lockheed Martin announcement .
  위치: 102–303 · 문서 `74b13ec8-e0f3-4cc4-9a69-b3ee58d2b6ed`

- 원문 사실/표현 [EXPLICIT_PLAN, PLAN]: 2027 추가 비행시험 계획. 납품일·qualification 완료일로 바꾸지 않음.
  > More PrSM Increment 2 flight tests are scheduled for 2027.
  위치: 1417–1475 · 문서 `74b13ec8-e0f3-4cc4-9a69-b3ee58d2b6ed`

가설(확인 사실과 구분): IDIQ 개별 주문의 필요일이 해당 Increment 2 시험·적격 생산 전환보다 빠른지 조사할 수 있으나 원문이 이미 같은 계열의 부족을 공개하므로 선행 조사대상으로 바로 분류하지 않는다.

가정: 실제 개별 주문·납기가 있다는 가정은 미확인; 공개 부족이 Increment 2에 적용되는지는 미확인

핵심 UNKNOWN: confirmation_scope: 기존 부족이 정확히 Increment 2인지?; orders_delivery_and_readiness: IDIQ 개별 확정 주문·납기와 적격 생산 전환일은?

확인된 반대 근거: 미확인

반박 조건: 같은 Increment 2의 부족이 이미 공개 확인됨: confirmation으로만 처리; 실제 주문 요구가 적격 생산 후이거나 배정이 충분함

다음 조사 질문:

- 이미 공개된 PrSM 부족이 Increment 2를 포함하는지 먼저 구분할 수 있는가?
- 포함하지 않는 경우에만 Increment 2 개별 주문·납기와 시험/생산 전환을 비교할 수 있는가?

단일 출처: True · 재인용: YES: according to a Lockheed Martin announcement; not two independent originals
confirmation 문서/같은 TARGET: YES/UNKNOWN · T/T_scope: UNKNOWN/UNKNOWN
기존 V2 판정 참조: {"source": "Unchanged original V2 decisions, not rerun", "archive": "diagnostics/v2-origin-count-20261005/original/immutable-run.json.gz", "pair_ids": ["6323cbdea9e4d08d6cadc17ce56886e3ad8bfe8831265de071b94bb62e5ce167"], "states": ["DATA_WAIT"], "original_evaluated_at": "2026-10-05T10:46:04.796837+00:00", "formal_TARGET_ids": [], "first_strict_condition_met_at": "UNKNOWN"}
상태 근거: POSSIBLE_PRIOR_CONFIRMATION
append-only 후속 기록: 0개

## Katy 수소 플랜트 → Hyroad offtake 공급 착수 — REVIEW_LEAD

검토 ID: `review-b62bffce3078cd440988d99d` · 정식 TARGET ID: 없음 · `BACKFILL`

원문이 뒷받침하는 범위: facility=Total Hydrogen Solutions’ new hydrogen plant in Katy, Texas, product=hydrogen

판독: MANUAL_SOURCE_READING_BY_ASSISTANT_USER_NOT_YET_VERIFIED / Codex: preserved full-source reading; not automatic extraction or independent gold (자동 추출 아님)

출처: POWER Magazine · https://www.powermag.com/hydrogen-award-finalist-total-hydrogen-solutions-texas-production-facility/
문서 ID: `69732205-86c3-463f-9e1e-cc68bd7e23e0` · SHA-256: `aa7801159857a50ccbf8a46ef351daf1f22fd1dfac2f7bb80f50647d9a4a8a9d`
공개: 2026-09-29T21:30:53+00:00 · 확보: 2026-10-04T14:46:43.723688+00:00 · 보존 가용: 2026-10-04T14:46:43.723688+00:00

최초 검토: 2026-10-05T15:35:13.019091+00:00 · 엄격 후보 최초 충족: UNKNOWN

- 원문 사실/표현 [FACT, REPORTED]: Hyroad 관련 offtake와 지역 사용자 공급 관계가 보고됨. 시작일·구속 물량은 미확인.
  > Demand for the hydrogen is meant to come partly from Hyroad. The nomination says an offtake agreement with the company supports distribution to regional users, and Hunt called the relationship an important part of connecting supply with real demand.
  위치: 2985–3234 · 문서 `69732205-86c3-463f-9e1e-cc68bd7e23e0`

- 원문 사실/표현 [FACT, REPORTED]: Hunt가 초기 통전·commissioning에 접근 중이라고 설명. 완료일·운영 실적은 미확인.
  > It is approaching initial energization and commissioning, Hunt said, so it is too early to share operating results or verified energy savings.
  위치: 635–777 · 문서 `69732205-86c3-463f-9e1e-cc68bd7e23e0`

- 원문 사실/표현 [FACT, REPORTED]: nomination 기재 공칭 능력 500 kg/day. 실제 적격 공급량으로 보지 않음.
  > The nomination puts capacity at 500 kilograms of hydrogen per day
  위치: 1206–1271 · 문서 `69732205-86c3-463f-9e1e-cc68bd7e23e0`

- 원문 사실/표현 [EXPLICIT_PLAN, PLAN]: 2026년 말 2 MW 증설 목표 및 5 MW까지 가능한 설계. 수소량이나 확정 준비일로 환산하지 않음.
  > The nomination targets expansion to 2 MW by the end of 2026, with a modular design that could reach 5 MW.
  위치: 3235–3340 · 문서 `69732205-86c3-463f-9e1e-cc68bd7e23e0`

가설(확인 사실과 구분): Hyroad offtake의 실제 공급 필요일이 commissioning·안정 생산보다 빠르면 Katy 설비에 연결된 초기 공급공백이 생길 수 있다. 공급공백이 확인됐다는 뜻은 아니다.

가정: offtake에 실제로 요구되는 시작일/최소 물량이 있다는 가정은 아직 미확인; 저장분·외부 조달·수요 순연으로 공백이 흡수되지 않는다는 가정은 미확인

핵심 UNKNOWN: offtake_need_date_quantity: Hyroad가 언제부터 얼마를 받아야 하는가?; commissioning_stable_output: 통전·commissioning·안정 생산의 실제 이정표와 적격 물량은?; storage_or_alternate_supply: 저장량·외부 대체 공급이 초기 납품을 충족하는가?

기간 원문: “by the end of 2026” · 정규화=UNKNOWN · 증설 목표 원문. 준비 완료일·정확한 날짜로 정규화하지 않음

반대 근거: 공급자가 시기를 고객 수요와 commissioning 경험에 맞출 계획이라고 설명. 실제 수요 순연이 공급공백을 없앨 수 있음.

반박 조건: 납품 요구가 안정 생산 이후에만 시작되거나 수요와 함께 순연됨; 저장/외부 적격 공급이 초기 물량을 충분히 충족함

다음 조사 질문:

- Hyroad 계약의 최초 납품일·최소 물량·순연/취소 조항은 무엇인가?
- 해당 Katy 플랜트의 통전·commissioning·검수 완료 계획/실적은 무엇인가?
- 초기 off-take를 저장분 또는 외부 수소로 이행할 수 있는가?

단일 출처: True · 재인용: Company nomination and interview reported by POWER; independent second origin not established
confirmation 문서/같은 TARGET: NO/NO · T/T_scope: UNKNOWN/UNKNOWN
기존 V2 판정 참조: {"source": "Unchanged original V2 decisions, not rerun", "archive": "diagnostics/v2-origin-count-20261005/original/immutable-run.json.gz", "pair_ids": ["c42e2a95ec42c5ec5a64fbd5e566a4f78fab24a740d29a55727c34310a94a7e2", "c380c7a7f9486299dcc10bfff69d0c88dc5594640552b2a6e5988c0e3842bc55", "084b12431754341651a8b63cec1272596f67c5a413248abf45e92842d7525df2"], "states": ["DATA_WAIT"], "original_evaluated_at": "2026-10-05T10:46:04.796837+00:00", "formal_TARGET_ids": [], "first_strict_condition_met_at": "UNKNOWN"}
상태 근거: SOURCE_BOUND_CHANGE_AND_FALSIFIABLE_RESEARCH_QUESTION
append-only 후속 기록: 0개

## eActros 600 — 기존 수요 이벤트 판독 제외 — EXCLUDED

검토 ID: `review-be698ff9fbfce3e6b1a2a918` · 정식 TARGET ID: 없음 · `BACKFILL`

원문이 뒷받침하는 범위: model=eActros 600

판독: MANUAL_SOURCE_READING_BY_ASSISTANT_USER_NOT_YET_VERIFIED / Codex: preserved full-source reading; not automatic extraction or independent gold (자동 추출 아님)

출처: FreightWaves · https://www.freightwaves.com/news/daimler-truck-scale-electric-trucks-europe
문서 ID: `3b19f7a6dad4a8964f0af31f91f4a929143f234018997386924f44b051a8ffb9` · SHA-256: `ebbcfa567e34cee818407f23c4829488248e550201f6dd169ca6d6234660399f`
공개: 2026-10-02T12:00:00+00:00 · 확보: 2026-10-05T03:02:22.753185+00:00 · 보존 가용: 2026-10-05T03:02:22.753185+00:00

최초 검토: 2026-10-05T15:35:13.021300+00:00 · 엄격 후보 최초 충족: UNKNOWN

- 원문 사실/표현 [NON_FACTUAL, RHETORICAL]: in order to는 목적을 말하는 수사적 표현이며 구매 주문 사실이 아님.
  > in order to build the ecosystem around those electric trucks
  위치: 5836–5896 · 문서 `3b19f7a6dad4a8964f0af31f91f4a929143f234018997386924f44b051a8ffb9`

가설(확인 사실과 구분): 기존 pair의 수요 근거는 실제 주문이 아니므로 같은 eActros 600의 미래 공급공백 가설을 이 근거로 만들지 않는다.

가정: 실제 주문 증가·납품 필요일은 현재 근거로 확인되지 않음

핵심 UNKNOWN: real_order: eActros 600의 실제 확정 미래 주문은 현재 근거에서 미확인

확인된 반대 근거: 미확인

반박 조건: 실제 주문 근거 없이 수사적 in order to를 주문으로 사용하는 해석은 기각

다음 조사 질문:

- 별도 지시가 있을 때만 eActros 600의 실제 확정 주문 근거가 있는지 확인. 이번에는 추가 조사하지 않음.

단일 출처: True · 재인용: Company statements reported by FreightWaves; no second independent original
confirmation 문서/같은 TARGET: NO/NO · T/T_scope: UNKNOWN/UNKNOWN
기존 V2 판정 참조: {"source": "Unchanged original V2 decisions, not rerun", "archive": "diagnostics/v2-origin-count-20261005/original/immutable-run.json.gz", "pair_ids": ["bd70faf154c761a12a08d9055427dc97c8d4a6e853f3e71106bf5cdefa8e92aa"], "states": ["DATA_WAIT"], "original_evaluated_at": "2026-10-05T10:46:04.796837+00:00", "formal_TARGET_ids": [], "first_strict_condition_met_at": "UNKNOWN"}
상태 근거: NO_FACTUAL_PRECURSOR_CHANGE
append-only 후속 기록: 0개

## Hemerdon → ELMT 텅스텐 정광 offtake / 생산 ramp — REVIEW_LEAD

검토 ID: `review-c3f7fbad7a1358e0d7425113` · 정식 TARGET ID: 없음 · `BACKFILL`

원문이 뒷받침하는 범위: facility=Hemerdon Mine, product=tungsten concentrate (WO₃ equivalent)

판독: MANUAL_SOURCE_READING_BY_ASSISTANT_USER_NOT_YET_VERIFIED / Codex: preserved full-source reading; not automatic extraction or independent gold (자동 추출 아님)

출처: The Elmet Group · https://theelmetgroup.com/the-elmet-group-secures-long-term-tungsten-offtake-agreement-with-tungsten-wests-hemerdon-mine/
문서 ID: `official-39b9dcdf59ca02ad28deb0497dd3b83a01312219a21e757fea0819fbc1c2e4d5` · SHA-256: `75e95fe2653d7d7c92186031a7f052213dd691856453e096a97312d472fc8334`
공개: 2026-09-22T20:06:48+00:00 · 확보: 2026-10-04T01:57:41.132019+00:00 · 보존 가용: 2026-10-04T01:57:41.132019+00:00

최초 검토: 2026-10-05T15:35:13.019995+00:00 · 엄격 후보 최초 충족: UNKNOWN

- 원문 사실/표현 [FACT, EXPECTED]: ELMT가 Hemerdon 정광 >1,000톤/년 인수를 예상. 인수 시작일·배정 보장량은 미확인.
  > Under the terms of the agreement, ELMT expects to take more than 1,000 metric tonnes per year of tungsten concentrate (WO₃ equivalent) from Hemerdon, with both parties aiming to increase production volumes over time.
  위치: 855–1071 · 문서 `official-39b9dcdf59ca02ad28deb0497dd3b83a01312219a21e757fea0819fbc1c2e4d5`

- 원문 사실/표현 [EXPLICIT_PLAN, PLAN]: 2027년 1분기 말까지 full-scale 생산 ramp 목표. 확정 적격 준비일로 해석하지 않음.
  > The mine is targeting ramp-up to full-scale production by the end of the first quarter of 2027.
  위치: 3313–3408 · 문서 `official-39b9dcdf59ca02ad28deb0497dd3b83a01312219a21e757fea0819fbc1c2e4d5`

- 원문 사실/표현 [FACT, CONDITIONAL]: 본문에 공급 존재 조건이 명시됨. 이 문구만으로 부족이 확인됐다고 해석하지 않음.
  > if supplies exist
  위치: 1433–1450 · 문서 `official-39b9dcdf59ca02ad28deb0497dd3b83a01312219a21e757fea0819fbc1c2e4d5`

가설(확인 사실과 구분): 동일 Hemerdon 생산을 받는 ELMT 인수 요구가 full-scale ramp·정광 품질 검수보다 먼저 시작하면 계약 경로의 공급공백 가능성을 조사할 이유가 있다. 현재 원문만으로 시점 역전이나 부족을 확인하지 못했다.

가정: offtake 인수 시작이 ramp 목표보다 빠를 수 있다는 가정은 미확인; 해당 인수에 쓸 재고·동등한 대체 공급이 충분하지 않다는 가정은 미확인

핵심 UNKNOWN: offtake_start_need_window: 인수 시작·연간 물량의 적용 첫 기간과 단계별 물량은?; ramp_stage_and_calendar_basis: first quarter가 달력/회계 분기인지, full-scale이 어떤 생산 단계인지?; qualified_allocated_supply: ramp 전후 회수율·품질/수율·ELMT 배정량과 재고/대체 공급은?

기간 원문: “by the end of the first quarter of 2027” · 정규화=UNKNOWN · targeting 표현 유지. 달력/회계 분기·ramp 단계 UNKNOWN; 날짜로 변환하지 않음

반대 근거: processing operations underway and continuing to ramp라는 진행 설명은 생산 개선의 반대 근거 후보이나 정량 실적/적격 능력 확인은 필요함.

반박 조건: 인수가 검증된 안정 생산 뒤에 시작됨; 필요기간의 적격 생산·재고·대체 공급이 배정 인수를 충분히 충족함

다음 조사 질문:

- ELMT 계약은 언제 인수를 시작하며 >1,000톤/년이 첫해부터 적용되는가?
- first quarter of 2027의 분기 기준과 full-scale 정의·검수 이정표는 무엇인가?
- Hemerdon 단계별 생산·회수율·정광 품질과 ELMT 배정량은 계약 필요량을 충족하는가?
- ELMT의 재고·다른 광산/정련망 공급으로 초기 요구를 대체할 수 있는가?

단일 출처: True · 재인용: Company official release; independent second original not verified
confirmation 문서/같은 TARGET: NO/NO · T/T_scope: UNKNOWN/UNKNOWN
기존 V2 판정 참조: {"source": "Unchanged original V2 decisions, not rerun", "archive": "diagnostics/v2-origin-count-20261005/original/immutable-run.json.gz", "pair_ids": ["56438a0fcb8c0aad95479331437111f471ae94bcb14a6e5503252c809146176c", "94ebbf1c403966f1771676c7ca1f942c119e8ff40645a7f55e019b351b904d79", "ab155e48688d31085c5189ac2747902df2d34d8f79c67f1cd8696aa24b925598", "8e424704600c05712fb95580d33de1a323da9f1c68df6061674139068808fc6c", "89a53b0222f3dd1fc1f642a2c29d3b2eab1b02ea4c53dd18908c956b1a7537c4", "3644e9b838cb72b6f0c43ec8055ca0fbd4e79d2a5fe9cc44987b590f5cb754a8", "d9aa824f4528aefcc38ae925c3ebbb34525d91b0f6b1e9c5ed01457a44f01bea", "6c8432066e986db745b75ba8ab605f035a00cec60a304b763287613098a830af", "6e2220728fe7ba3664784f3963ba252175dc49aa5481c1ad4326a05d583bc62b", "c7cf96a6667b7a276b8173507c2232b364f89e076b4303a5d429edd83d161512", "e126ebd73c592649519b12e3186285d8dc99024eff4ea82f8b4ac621884dd5da", "95c56dbcbcb6de1278ef07cae76e649da1d23ee96bddb8672958be96f1e6b587"], "states": ["DATA_WAIT"], "original_evaluated_at": "2026-10-05T10:46:04.796837+00:00", "formal_TARGET_ids": [], "first_strict_condition_met_at": "UNKNOWN"}
상태 근거: SOURCE_BOUND_CHANGE_AND_FALSIFIABLE_RESEARCH_QUESTION
append-only 후속 기록: 0개

