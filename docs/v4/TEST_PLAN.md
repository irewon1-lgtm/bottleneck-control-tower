# V4 실행 계약 (2026-10-13)

V3.3 base: `9cba69d1785daa9d3199dd6309d76b96ef64c797`.
Research reference: `fe35b117458056d590cfa87cd7efc323fff171f0`.
Development: `codex/bct-v4-integration`. No main merge, Actions, paid API,
production DB writes or changes to existing engine semantics.

| 단계 | 입력·실행 | PASS 기준 |
|---|---|---|
| 1 분석 | 연구 파일 6개, 53개 원장, objective, 수집/본문/예측/그래프/저장/복구 코드; 관련 기존 pytest | 6개 읽기, 재사용/제외 이유 기록, 객관적 목표 일치, 관련 기존 시험 통과 |
| 2 연결 | V4 라이브러리 adapter, CPU GLiNER2, SQLite; 기능 시험 | 실제 라이브러리·모델 호출, span 검증, 중복/rollback/재열기/backup 복원, V3.3 보존 |
| 3 실제 원문 | 서로 다른 공식 원문 native HTML/PDF, CPU 모델, 저장; 동일 입력 baseline 비교 | 원문과 공개일/원출처 검증, 실제 AI 실행, 사전 고정 정답의 정확도/누락/CPU/RAM 측정 |
| 4 판단 | 동일 TARGET, 원출처, 주문/계획, 준비일, 전체공급, Relief 반례 | 잘못된 연결/승격 차단; 실제자료 판정과 합성 기능 시험 별도 |
| 5 선행 실증 | cutoff 동결 실제 Positive≥5/Negative≥5/hard Negative≥3/미사용 HOLDOUT≥3 | 당시 입력만 사용, 최초 확인 공개일 동결, blind 평가; EARLY는 양의 선행일만 |
| 6 Shadow | V4만 실제 신규 문서를 수집, append-only 기록 | 실제 7일 운영, 신규 TARGET/실패/속도/복구 기록; BACKFILL 제외 |
| 7 최종 | 동일 조건 V3.3/V4 수치와 단계별 실행 증거 | 개선/악화 보고; 실증 미확인 시 교체 HOLD |

필수 선행 단계가 BLOCKED이면 다음 의존 단계는 NOT_RUN/BLOCKED로 남긴다.
독립적인 합성 회귀·저장·CLI 시험은 별도 실행할 수 있으며 실증을 대신하지 않는다.
연구의 과거 PASS는 이번 환경 PASS가 아니다. 원문/모델 접근 거부는 BLOCKED다.
기능용 fixture는 SYNTHETIC, 기존 원문 재생은 BACKFILL이며 LIVE로 바꾸지 않는다.

실행 증거: `var/v4/evidence/` (원문/모델/DB는 Git에 올리지 않음),
공개 요약: `docs/v4/TEST_RESULTS.json`, `docs/v4/REPORT.md`.
