# REVIEW_LEAD intake

半자동 source-bound triage; not EARLY performance.

## Katy 수소 플랜트 → Hyroad offtake 공급 착수 — REVIEW_LEAD
SOURCE_BOUND_CHANGE_AND_FALSIFIABLE_RESEARCH_QUESTION
Semantic review: COMPLETED
Hypothesis: Hyroad offtake의 실제 공급 필요일이 commissioning·안정 생산보다 빠르면 Katy 설비에 연결된 초기 공급공백이 생길 수 있다. 공급공백이 확인됐다는 뜻은 아니다.
Questions: Hyroad 계약의 최초 납품일·최소 물량·순연/취소 조항은 무엇인가?; 해당 Katy 플랜트의 통전·commissioning·검수 완료 계획/실적은 무엇인가?; 초기 off-take를 저장분 또는 외부 수소로 이행할 수 있는가?
UNKNOWN: [{"field": "offtake_need_date_quantity", "status": "UNKNOWN", "question": "Hyroad가 언제부터 얼마를 받아야 하는가?"}, {"field": "commissioning_stable_output", "status": "UNKNOWN", "question": "통전·commissioning·안정 생산의 실제 이정표와 적격 물량은?"}, {"field": "storage_or_alternate_supply", "status": "UNKNOWN", "question": "저장량·외부 대체 공급이 초기 납품을 충족하는가?"}]
Refutation: 납품 요구가 안정 생산 이후에만 시작되거나 수요와 함께 순연됨; 저장/외부 적격 공급이 초기 물량을 충분히 충족함
Confirmation: {"document": "NO", "same_TARGET": "NO", "method": "Full preserved source-body reading; absence here is not global T proof", "references": []}
Mode/recorded: BACKFILL / 2026-10-05T16:35:02.787575+00:00

Source: https://www.powermag.com/hydrogen-award-finalist-total-hydrogen-solutions-texas-production-facility/ / SHA256 aa7801159857a50ccbf8a46ef351daf1f22fd1dfac2f7bb80f50647d9a4a8a9d
Published/acquired: 2026-09-29T21:30:53+00:00 / 2026-10-04T14:46:43.723688+00:00

Hyroad 관련 offtake와 지역 사용자 공급 관계가 보고됨. 시작일·구속 물량은 미확인.
> Demand for the hydrogen is meant to come partly from Hyroad. The nomination says an offtake agreement with the company supports distribution to regional users, and Hunt called the relationship an important part of connecting supply with real demand.
Locator: {"start": 2985, "end": 3234}

Hunt가 초기 통전·commissioning에 접근 중이라고 설명. 완료일·운영 실적은 미확인.
> It is approaching initial energization and commissioning, Hunt said, so it is too early to share operating results or verified energy savings.
Locator: {"start": 635, "end": 777}

nomination 기재 공칭 능력 500 kg/day. 실제 적격 공급량으로 보지 않음.
> The nomination puts capacity at 500 kilograms of hydrogen per day
Locator: {"start": 1206, "end": 1271}

2026년 말 2 MW 증설 목표 및 5 MW까지 가능한 설계. 수소량이나 확정 준비일로 환산하지 않음.
> The nomination targets expansion to 2 MW by the end of 2026, with a modular design that could reach 5 MW.
Locator: {"start": 3235, "end": 3340}

## PrSM Increment 2 계약 / 시험·생산 전환 — HOLD
POSSIBLE_PRIOR_CONFIRMATION
Semantic review: COMPLETED
Hypothesis: IDIQ 개별 주문의 필요일이 해당 Increment 2 시험·적격 생산 전환보다 빠른지 조사할 수 있으나 원문이 이미 같은 계열의 부족을 공개하므로 선행 조사대상으로 바로 분류하지 않는다.
Questions: 이미 공개된 PrSM 부족이 Increment 2를 포함하는지 먼저 구분할 수 있는가?; 포함하지 않는 경우에만 Increment 2 개별 주문·납기와 시험/생산 전환을 비교할 수 있는가?
UNKNOWN: [{"field": "confirmation_scope", "status": "UNKNOWN", "question": "기존 부족이 정확히 Increment 2인지?"}, {"field": "orders_delivery_and_readiness", "status": "UNKNOWN", "question": "IDIQ 개별 확정 주문·납기와 적격 생산 전환일은?"}]
Refutation: 같은 Increment 2의 부족이 이미 공개 확인됨: confirmation으로만 처리; 실제 주문 요구가 적격 생산 후이거나 배정이 충분함
Confirmation: {"document": "YES", "same_TARGET": "UNKNOWN", "method": "Full source reading: generic strike-missile shortage and lack of PrSM; Increment 2 scope not confirmed", "references": [{"document_id": "74b13ec8-e0f3-4cc4-9a69-b3ee58d2b6ed", "body_sha256": "f72dcb5f9b163c2377bc43cf553fdfec3bf0c879b0f53700c173485da8f735dc", "locator": {"start": 1778, "end": 1895}, "quote": "The U.S. military faces a desperate shortage of strike and air defense missiles after expending vast numbers in Iran."}, {"document_id": "74b13ec8-e0f3-4cc4-9a69-b3ee58d2b6ed", "body_sha256": "f72dcb5f9b163c2377bc43cf553fdfec3bf0c879b0f53700c173485da8f735dc", "locator": {"start": 1896, "end": 1944}, "quote": "This reportedly includes a lack of PrSM weapons."}]}
Mode/recorded: BACKFILL / 2026-10-05T16:35:02.805456+00:00

Source: https://www.defensenews.com/industry/2026/09/22/us-army-awards-lockheed-martin-12b-prsm-contract/ / SHA256 f72dcb5f9b163c2377bc43cf553fdfec3bf0c879b0f53700c173485da8f735dc
Published/acquired: 2026-09-22T15:04:23.290000+00:00 / 2026-10-04T20:30:41.131099+00:00

PrSM Increment 2 초기 생산·향후 주문에 관한 IDIQ 계약 보도. Lockheed 발표 재인용으로 표시.
> The indefinite-delivery, indefinite-quantity contract covers initial production and future orders of Increment 2 of the Precision Strike Missile, or PrSM , according to a Lockheed Martin announcement .
Locator: {"start": 102, "end": 303}

2027 추가 비행시험 계획. 납품일·qualification 완료일로 바꾸지 않음.
> More PrSM Increment 2 flight tests are scheduled for 2027.
Locator: {"start": 1417, "end": 1475}

## eActros 600 — 기존 수요 이벤트 판독 제외 — EXCLUDED
NO_FACTUAL_PRECURSOR_CHANGE
Semantic review: COMPLETED
Hypothesis: 기존 pair의 수요 근거는 실제 주문이 아니므로 같은 eActros 600의 미래 공급공백 가설을 이 근거로 만들지 않는다.
Questions: 별도 지시가 있을 때만 eActros 600의 실제 확정 주문 근거가 있는지 확인. 이번에는 추가 조사하지 않음.
UNKNOWN: [{"field": "real_order", "status": "UNKNOWN", "question": "eActros 600의 실제 확정 미래 주문은 현재 근거에서 미확인"}]
Refutation: 실제 주문 근거 없이 수사적 in order to를 주문으로 사용하는 해석은 기각
Confirmation: {"document": "NO", "same_TARGET": "NO", "method": "Full preserved source-body reading; absence here is not global T proof", "references": []}
Mode/recorded: BACKFILL / 2026-10-05T16:35:02.876150+00:00

Source: https://www.freightwaves.com/news/daimler-truck-scale-electric-trucks-europe / SHA256 ebbcfa567e34cee818407f23c4829488248e550201f6dd169ca6d6234660399f
Published/acquired: 2026-10-02T12:00:00+00:00 / 2026-10-05T03:02:22.753185+00:00

in order to는 목적을 말하는 수사적 표현이며 구매 주문 사실이 아님.
> in order to build the ecosystem around those electric trucks
Locator: {"start": 5836, "end": 5896}

## Hemerdon → ELMT 텅스텐 정광 offtake / 생산 ramp — REVIEW_LEAD
SOURCE_BOUND_CHANGE_AND_FALSIFIABLE_RESEARCH_QUESTION
Semantic review: COMPLETED
Hypothesis: 동일 Hemerdon 생산을 받는 ELMT 인수 요구가 full-scale ramp·정광 품질 검수보다 먼저 시작하면 계약 경로의 공급공백 가능성을 조사할 이유가 있다. 현재 원문만으로 시점 역전이나 부족을 확인하지 못했다.
Questions: ELMT 계약은 언제 인수를 시작하며 >1,000톤/년이 첫해부터 적용되는가?; first quarter of 2027의 분기 기준과 full-scale 정의·검수 이정표는 무엇인가?; Hemerdon 단계별 생산·회수율·정광 품질과 ELMT 배정량은 계약 필요량을 충족하는가?; ELMT의 재고·다른 광산/정련망 공급으로 초기 요구를 대체할 수 있는가?
UNKNOWN: [{"field": "offtake_start_need_window", "status": "UNKNOWN", "question": "인수 시작·연간 물량의 적용 첫 기간과 단계별 물량은?"}, {"field": "ramp_stage_and_calendar_basis", "status": "UNKNOWN", "question": "first quarter가 달력/회계 분기인지, full-scale이 어떤 생산 단계인지?"}, {"field": "qualified_allocated_supply", "status": "UNKNOWN", "question": "ramp 전후 회수율·품질/수율·ELMT 배정량과 재고/대체 공급은?"}]
Refutation: 인수가 검증된 안정 생산 뒤에 시작됨; 필요기간의 적격 생산·재고·대체 공급이 배정 인수를 충분히 충족함
Confirmation: {"document": "NO", "same_TARGET": "NO", "method": "Full preserved source-body reading; absence here is not global T proof", "references": []}
Mode/recorded: BACKFILL / 2026-10-05T16:35:02.913921+00:00

Source: https://theelmetgroup.com/the-elmet-group-secures-long-term-tungsten-offtake-agreement-with-tungsten-wests-hemerdon-mine/ / SHA256 75e95fe2653d7d7c92186031a7f052213dd691856453e096a97312d472fc8334
Published/acquired: 2026-09-22T20:06:48+00:00 / 2026-10-04T01:57:41.132019+00:00

ELMT가 Hemerdon 정광 >1,000톤/년 인수를 예상. 인수 시작일·배정 보장량은 미확인.
> Under the terms of the agreement, ELMT expects to take more than 1,000 metric tonnes per year of tungsten concentrate (WO₃ equivalent) from Hemerdon, with both parties aiming to increase production volumes over time.
Locator: {"start": 855, "end": 1071}

2027년 1분기 말까지 full-scale 생산 ramp 목표. 확정 적격 준비일로 해석하지 않음.
> The mine is targeting ramp-up to full-scale production by the end of the first quarter of 2027.
Locator: {"start": 3313, "end": 3408}

본문에 공급 존재 조건이 명시됨. 이 문구만으로 부족이 확인됐다고 해석하지 않음.
> if supplies exist
Locator: {"start": 1433, "end": 1450}
