# BCT V4 — 세션 2 원문 수집 복원 인계 (2026-11-13 KST)

## 고정 판정
- 이전 원문 캐시 복원 장애 `ACQUISITION_PRIOR_ATTEMPT_BINDING` 원인을 실제 생산 로그·기존 실행 증명서에서 확인.
- 문제 원인: cache_run `43245595579`는 정상 완료된 수동 `workflow_dispatch`였는데 복원 코드는 자동 `workflow_run`만 통과시킴.
- 기존 5개의 정상 원문 검증 작업을 동일 GitHub 회차에서 재검증하는 조건으로 복원 코드를 최소 수정.
- 테스트: main commit `a897e80d392911c4ea9dc4dc3a44908aa83dab3a`; Python 1,163 PASS/1 SKIP, JS PASS.
- 실제 read-only pilot run `43329924578`: 저장 원문 문서 3,097기록 + capture 기록 8,450 복원 성공.
- 새 RSS 실증 11건: CAPTURED+출처검증 5, PROVENANCE_BLOCKED 5, HTTP_403 1. 운영 DB에는 실증 결과 미기록.
- PR #66 merged: https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/66

## 최신 상태 스냅샷
- data SHA `da7b17f34d58c69c72b5d067d6279ec98db8bb44`: canonical RSS 10,510건, run 43327217572.
- future-bottleneck-data SHA `e8acd5e91f9f972974b5027a36056651098da71f`: sidecar 결과 8,145건. 기록 차 2,365건, 직접 ID별 최신 교집합 검증 필요.
- 세션 1 고정 DB 10,438건 중 FULL 미확인 기사 5,797건. 대기 작업 분류만 완료, 본문 복원 완료 아님.
- 세션 2 분류: NO_ANALYSIS_RESULT 2,273, ORIGINAL_UNAVAILABLE 2,334, PARTIAL_ORIGINAL 1,082, MEDIA 108.

## 자동분석 연결 차단
- `bct_release_guard.py`는 구형 receipt와 다른 현재 main 코드 파일 집합을 거부. 우회/삭제/수정하지 않았음.
- 실 Gates 0-6 revalidation run `43330584731` 시작. 결과 확인 전 미래 병목 분석 복구 확정 금지.
- RSS AI OpenAI API 키는 미설정, 기존 무료 정책에 따라 AI 단계를 SKIPPED_CONFIG로 유지. 임의 유료 API 연결 없음.

## 다음 작업 인계
1. 실제 Gate 0-6 실행 결과와 receipt 새 SHA를 확인. FAIL시 실패 단계만 보완하고 전체 증명 다시 생성.
2. `New precursor evidence acquisition` 다음 main 실행에서 과거 source archive 복원 PASS 및 새로운 검증 원문 보존 여부 확인.
3. 원문 5,797건의 부분/불가/미분석 상태를 원본 단위로 유지하며 실패 원인별 복구. 403·페이월 우회 금지.
4. 10,510건 최신 저장 RSS ID를 별도 sidecar와 1:1로 reconcile 후 미분석 대기열 자동 처리.
5. 원문 본문을 읽었다는 사실과 S1/S2/S3 독립 수요·공급 증거 검증을 엄격히 분리.

## 검증 URL
- 실증 run: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43329924578
- 운영 main Stage0: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43330573047
- Gate 0–6: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43330584731

원본 data/main 외의 별도 격리 감사 브랜치에 결과만 기록하며 민감 원문·API 키는 저장하지 않음.