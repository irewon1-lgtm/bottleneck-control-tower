# 사건별 원문 검토 정책 v1

이 정책과 원문·해시·입력 범위만 별도 읽기 전용 검토 세션에 제공한다. 평가 대상 Groq/GLiNER2 출력, 구현 코드, 예상 정답은 제공하지 않는다. AI 검토를 인간 검증이라고 표시하지 않는다. 개발자는 개발30으로만 수정하고 평가20 출력/정답을 읽고 튜닝하지 않는다.

검토 범위는 패킷의 **windows 전체**다. 빈 windows는 미판독/정답 미검토이며 ABSENT가 아니다. 전체 원문에서 입력 범위가 차지하는 비율과 밖의 미검토 범위를 별도로 기록한다. 확보한 FULL 텍스트도 첨부·영상·표 전체 검증을 뜻하지 않는다.

한 문서에 여러 target, 한 target에 여러 event를 허용한다. 같은 제품의 다른 주문·다른 기간은 다른 event다. 제품군·제조장비·생산 슬롯은 물리 탐색 대상이고 프로젝트·기업명·일반 표현은 제품이 아니다. 제품은 맞지만 수급 변화가 없으면 탐색 사실만 기록한다.

사건별로 명시된 product, role, actuality, quantity, unit, period, customer_group, supply_pool, specification, region, need_time, ready_time, lead_time, relief, alternative를 검토한다. 동일 필드의 여러 독립 사실도 허용한다. 지원금·매출은 물량이 아니고 지원 수혜자는 고객이 아니다. 제조·매출 발표는 계약/발주와 다르며 생산계획은 실제 적격 공급과 다르다. 고객 또는 적격 공급자는 제품과의 관계가 입증돼야 한다. 시간은 발표일·계약일·수요 필요일·공급 준비일을 구분한다. 부정문·조건·완화·대체재를 포함하여 판정한다. 공급 감소가 있어도 잔존 수요·전체 적격 공급 없이 병목 확정하지 않는다.

출력은 다음 JSON 구조다. 문서별 `review_complete`는 제공한 입력 전체를 실제 검토했을 때만 true다. 아무 정보가 없으면 검토한 전체 windows와 `no_relevant_event_reason`을 남긴다. target/event 수를 채우기 위해 답을 만들지 않는다.

```json
{
  "version": "bct-event-gold-1",
  "reviewer": {"type": "AI_INDEPENDENT_SESSION", "session": "실제 세션 ID", "model": "실제 알 수 있는 모델 또는 UNKNOWN", "exposed_to_model_outputs": false, "human_verified": false},
  "documents": [{
    "document_id": "패킷 ID", "body_sha256": "패킷 SHA", "review_complete": true,
    "reviewed_ranges": [{"start": 0, "end": 100}],
    "targets": [{"target_id": "문서 내 안정 ID", "entity": "원문에 있는 표현", "entity_aliases": [],
      "events": [{"event_id": "문서 내 안정 ID", "reference": {"start": 0, "end": 100, "quote": "원문 정확 인용"},
        "facts": [{"field": "product", "status": "VERIFIED_PRESENT", "value": "원문 그대로의 제품명", "reference": {"start": 0, "end": 5, "quote": "원문 정확 인용"}, "reason": "제품 및 사건 관계를 확인한 이유"},
                  {"field": "quantity", "status": "VERIFIED_ABSENT", "value": null, "reference": null, "reason": "입력 전체에 이 사건의 물리 수량 없음"}]}]}],
    "no_relevant_event_reason": null
  }]
}
```

상태: VERIFIED_PRESENT는 명시 사실·관계·위치 확인, VERIFIED_ABSENT는 지정 범위를 검토했지만 해당 정보 없음, UNVERIFIED는 미검토, AMBIGUOUS는 의미/관계 불명확이다. 뒤 두 상태는 채점에서 제외하고 수를 보고한다. role 값은 DEMAND_INCREASE/SUPPLY_DECREASE/SUPPLY_DELAY/SUPPLY_INCREASE/RELIEF, actuality는 ACTUAL/PLAN/FORECAST/NEGATED/UNKNOWN이다. enum 사실은 값 자체가 인용에 없어도 근거 문장과 판정 이유가 필요하다. 나머지 PRESENT 값은 원문 그대로다. 원문에 없는 값을 상식으로 채우지 않는다.

독립 작성 후 별도 원문 대조 검토자가 위치·관계·누락을 확인한다. 의견 불일치는 근거로 심사하고 미해결은 AMBIGUOUS로 유지한다. 다수결·모델 자기 답은 정답 근거가 아니다. 미완료 세션은 정답 초안이며 독립 정확도 BLOCKED다.

평가기준: 같은 문서·동일 target/event와 인용 범위에서 사실을 비교한다. 이벤트 범위가 겹쳐도 제품이 다르면 합치지 않는다. 사전 지정 원문 별칭만 허용하며 유사 문자열 매칭은 없다. 중복 예측은 TP를 늘리지 않는다. 틀린 값은 FP+FN, 실제 정답 누락은 FN, 명시적 부재와 엔진 UNKNOWN은 별도다. P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN); 분모0은 null이다. 전송 차단·미실행·정답 미검토는 모델 누락 분모에서 분리한다. 입력 밖은 문서 전체 recall로 부르지 않는다.

도입 판단은 기존 계획대로 제품 오탐 감소·누락 악화 없음·근거 없는 채택 차단을 모두 본다. 새 합격 수치나 점수체계를 만들지 않는다. CPU 비교는 동일 windows 및 공통 entity 필드만이며 Groq 사건 의미와 직접 점수 비교하지 않는다. 과거 재생은 BACKFILL이고 선행 예측은 NOT_RUN이다.
