# BCT 작업 재개 안내

BCT 작업 전 BCT_OBJECTIVE_LOCK.md와 docs/v4/EXECUTION_PLAN.md, docs/v4/PROGRESS.json을 읽는다.

정량 수급 강화 작업은 docs/v4/quantitative/FIXED_SEQUENCE.md(계획 ID BCT-V4-Q-1.0)를 함께 읽는다. 고정 순서는 Q1 공통 정량자료 → Q2 세부 공급/수요 능력 → Q3 동일 TARGET 비교 → Q4 독립 선행성 평가 → Q5 검증 경로 자동화/UI → Q6 실제 7일 → Q7 승인 전환이다. Q1 실행 지침은 docs/v4/quantitative/STEP1_INSTRUCTIONS.md이다. 과거 단계 번호와 완료 증거는 바꾸지 않는다.

진행은 기존 PROGRESS.json의 quantitative_plan 하위에 기록하고 기존 필드를 보존한다. 별도 진행 원장이나 경쟁 마스터 계획을 만들지 않는다. 이 문서와 계획 저장은 Q1 실행 성공이 아니다. 기록이 없다면 Q1 NOT_RUN에서 시작한다.

목표·Objective Lock·S gate·최초 선행 판정·무료 원칙을 바꾸지 않는다. 동일 원문을 반복 읽거나 UI·모델·정상 Secret을 다시 만들지 않는다. 원문 없이 사실 검증 PASS를 주장하지 않는다. 기존 연구 CPU 운영의 허용 범위와 새 Q 단계 도입 완료는 분리한다. 문서 커밋 SHA를 실제 CPU 실행 pin/Actions 변수에 임의로 넣지 않는다.

하나의 출처가 막히면 해당 의존성만 보류하고 나머지는 계속한다. 미완료 출처를 숨기고 전체 PASS를 선언하지 않는다. 계획/기능/실제 수치 정확도/독립 선행성/정기 운영을 각각 보고한다. 작업 시작과 종료에 계획 ID·Q단계·증거·다음 행동을 남긴다.
