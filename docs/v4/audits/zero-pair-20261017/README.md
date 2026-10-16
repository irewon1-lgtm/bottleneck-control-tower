# BCT V4 0건 원인 감사 결과

기준 SHA: 23a0615f1a10f2b938cb2b5401706a1995b4d4f2

전체 판정은 PARTIAL/BLOCKED다. 전체 최신 DB와 약30개 공식 원문을 직접 복원한 전면 감사 완료가 아니다.

- ROOT_CAUSE_REPORT.md: 핵심 원인·최초 차단·확정/추정/미확인·접근 장벽.
- STAGE_LOSS_EVIDENCE.csv: 분모를 분리한 14개 단계/경로의 증거표.
- CASE_EVIDENCE.csv 및 JSON: 고정된 기존31개 검토 행 전체. 31개 신규 심층 원문 검토가 아니다.
- CODEX_MINIMAL_FIX_SPEC.md: 확인된 제품 누락2사례와 진단 결손의 최소 보수, 시점 경로의 추가 계약시험.
- reproduction-results.json / additional-reproduction-results.json: 실제 재생과 합성 진단 분리.
- source-integrity.json: 읽은 텍스트125개가 기준 Git blob과 바이트 일치.
- q1-count-reconciliation.json: 저장 출처별 최종 수치의 합계 검산. 최신 DB SQL 전수계수 아님.
- SOURCE_CODE_INDEX.md: 함수별 코드 위치.

재현은 기준 SHA의 읽기 전용 소스와 reading-quality DB 복사본을 사용한다. 원격 자료 수집·모델 추론·운영 DB 수정은 없다. 스크립트는 원본 함수의 AST 정의를 그대로 실행해 관련 없는 수집기 초기화 의존성을 피한다. 모의 대체 추출기를 쓰지 않는다. 전체 원장 재생을 대신하는 것이 아니다.

```
BCT_AUDIT_SOURCE_ROOT=/absolute/repository \
BCT_AUDIT_DB=/absolute/read-only-copy/reading-quality.sqlite3 \
PYTHONPATH=/absolute/repository/src python3 reproduce.py

BCT_AUDIT_SOURCE_ROOT=/absolute/repository \
BCT_AUDIT_DB=/absolute/read-only-copy/reading-quality.sqlite3 \
PYTHONPATH=/absolute/repository/src python3 additional_replays.py
```

reading-quality DB는 저장소의 docs/v4/reading-quality/research-snapshot.sqlite3.gz를 별도 경로에 압축 해제한다. 전체 최신 CPU/정량 DB로 오인하지 않는다. 원문이 포함된 상세 로컬 재생 출력은 채팅 묶음과 감사 브랜치에 재게시하지 않는다.

실제 수급쌍0 / 신규 S2·S3 0 / 실제 선행탐지 입증0을 유지한다. 과거 계획·PROGRESS·운영 코드·연구 원장을 변경하지 않았다. 문서 보존 커밋의 CI는 새 기능시험이나 미래 병목 성능시험이 아니다.
