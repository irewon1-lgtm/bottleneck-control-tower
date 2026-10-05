# 사람이 2차 조사할 1차 검토 목록

실제 개발 예시는 [검토 카드 보고서](examples-20261005/report.md)와
[기계 판독 기록](examples-20261005/report.json)에 있다.
조사대상 2개, 보류 1개, 제외 1개. 17개 관계쌍은 기존 판정 참조일 뿐
17개 독립 사례가 아니다. EARLY/선행탐지 성공은 0이며 이 목록은 BACKFILL이다.

규칙/적용시각은 [별도 검토 계약](contract.json)과 [계약 설명](CONTRACT.md)에
있다. 기존 Objective Lock·EARLY·strict·v2 activation/hash는 수정하지 않는다.

## 구현과 입력

`python -m bct.review_leads`는 별도 검토 기록 생성/읽기/append-only CLI다.
동결 이벤트를 수정하거나 기존 evaluator를 실행하지 않는다. 수집 기능,
자동 2차 조사, 업종 사전, 점수, UI, 운영 스케줄이 없다.

`examples-20261005/input.json`은 보존된 4개 원문과 새 판독 주석이다.
주석은 assistant가 원문을 읽어 작성했고 사용자/독립 판독자 확인 전임을
표시한다. 자동 추출 성능이나 정답 데이터가 아니다. 확인된 사실/계획은
원문 인용·body hash·위치로 묶고, 조사 가설·가정·미확인 사항을 별도로 둔다.
원출처/공개/확보 정보는 기존 보존 기록에서 왔다. 원문 없는 값은 만들지 않는다.

범용 검토기는 특정 사례명/ID로 상태를 반환하지 않는다. 선언된 범위와
사실의 literal source binding을 검증하고, 명백한 범위 불일치·비사실 표현·
confirmation·일반적 가설을 구분한 뒤 상태를 계산한다. 동일 scope/hypothesis
중복 주석은 하나의 기록으로 처리한다. 다른 주석을 조용히 버리지 않도록
동일 identity의 상이한 주석은 명시적 병합 또는 append를 요구한다.
명칭만 유사하거나 UNKNOWN을 공유하는 별개 대상을 자동으로 합치지 않는다.

원문 의미/가설 연결/confirmation scope 판단에는 명시된 수동 판독 주석을
사용한다. 이것을 자동 분류의 정확도로 해석해서는 안 된다. 조작된 주석의
모든 의미적 오류를 자동으로 검출한다고 보장하지 않는다.

## 실행한 명령

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest tests/test_review_leads.py -q -p no:cacheprovider --junitxml=review-leads/examples-20261005/tests.xml

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m bct.review_leads generate --input review-leads/examples-20261005/input.json --contract review-leads/contract.json --store review-leads/examples-20261005/review-state --report review-leads/examples-20261005/report

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m bct.review_leads read --store review-leads/examples-20261005/review-state --report /workspace/bct-review-leads-readback
```

결과: 합성 경계시험 **12 PASS**. 실제 개발 입력은 **4문서 → 4기록**:
REVIEW_LEAD 2, HOLD 1, EXCLUDED 1, CONFIRMATION 0. 실제 확정된 same-TARGET
confirmation이 0이라는 뜻이지 PrSM 문서의 병목 공개를 지웠다는 뜻이 아니다.
그 문서는 confirmation=YES / same-TARGET=UNKNOWN으로 보류했다.
합성 시험과 실제 예시는 분리했으며 ablation A/B는 재실행하지 않았다.

새 입력은 같은 source-bound schema로 명시적 판독 주석을 제공한다. 근거
위치/hash, factual change, 구체적 조사 연결, UNKNOWN/가정/반박조건/질문이
필요하다. 일반 성장/증설만으로는 HOLD이고 동일 모델/시설 충돌은 EXCLUDED다.
단일 출처·미완성 period/배정은 그 자체로 차단하지 않는다.

## 시간·보존·후속 기록

`review-state/activation.json`에 검토 계약/구현 hash를 고정했다.
`first/*.json`은 실제 생성시각의 최초 기록이며 immutable hash·objective
binding을 가진다. `formal_TARGET_id=null`, 기존 strict 최초 충족은 UNKNOWN.
과거 공개일·DATA_WAIT 평가시각을 검토 최초 시각으로 사용하지 않는다.
원문 공개/자료 확보/검토 최초/strict 최초 충족을 구분하며 T/T_scope는 UNKNOWN.

후속 입력을 확보한 뒤에만 다음 append 경로를 사용할 수 있다. 이번에는
실제 후속 조사나 증거 추가를 수행하지 않았다. 합성시험에서만 append,
재실행 중복 제거, 최초 바이트 보존, 시각 보존과 EARLY 상태 거부를 검증했다.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m bct.review_leads append --store review-leads/examples-20261005/review-state --contract review-leads/contract.json --input VERIFIED_LOCAL_REVIEW_INPUT.json --review-id EXISTING_REVIEW_ID --event OBJECTIVE_BOUND_FOLLOWUP.json --report /tmp/review-followup
```

event는 Objective Lock binding, `kind`(EVIDENCE/REVIEW/CONFIRMATION/REFUTATION),
`annotator`, `summary`, 원문 `references`를 갖는다. 상태 변화는 REVIEW_LEAD,
HOLD, EXCLUDED, CONFIRMATION, REFUTED만 가능하며 EARLY로 승격할 수 없다.
확인/반증으로 상태를 바꾸려면 같은 TARGET이라는 명시적 판독이 필요하다.
참조된 원문도 후속 기록에 보존한다. 최초 카드와 과거 history는 덮어쓰지
않으며 후속은 `history/<review-id>/*.json`에 추가한다. 같은 event는 idempotent다.

## 바로 시작할 질문

- **Katy → Hyroad:** 실제 off-take의 첫 납품일·최소 물량은 무엇인가?
  초기 통전/commissioning·검수·안정 생산이 이를 앞서는가? 저장/외부 공급이
  초기 납품을 충족하면 가설이 반박된다.
- **Hemerdon → ELMT:** >1,000톤/년의 인수 시작·단계별 적용은 무엇인가?
  Q1 2027의 분기 기준·full-scale 생산 단계는 무엇인가? 단계별 적격 물량·
  배정/재고/대체 공급이 인수 요구를 충족하면 가설이 반박된다.
- **PrSM Increment 2 (보류):** 이미 공개된 부족이 정확히 Increment 2에도
  해당하는지 먼저 확인해야 한다. YES면 confirmation으로만 분류한다.
- **eActros 600 (제외):** 기존 pair의 “in order to”는 주문이 아니다.
  이 근거로 2차 조사를 착수하지 않는다. Lowliner/NextGenH2의 기간도 옮기지 않는다.

2개 조사대상은 엄격 후보나 예측 성공이 아니다. 단일 출처·자료 범위·수동
주석의 한계가 있으며 실제 미래 gap·독립 근거·성능은 확인하지 못했다.
분기 해석 단위시험, 추가 수집, 운영 반영은 이번 범위에 포함하지 않았다.
