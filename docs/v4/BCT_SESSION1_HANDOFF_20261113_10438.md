# BCT V4 — RSS 세션 1 감사 인계 (2026-11-13 KST)

**판정: 기사별 저장 및 처리 상태 전수 감사 PASS, 병목 판단 완료는 아님.**

- 최신 RSS `data`: `0cd08529dff5291634e5934489301f2862ada234` — 10,438개 기사 기록, 2026-11-13 02:50 KST 최신 수집분 포함.
- 원본 전수 감사 DB: `75e2705e1381d9a2a469d4f22360f2fb95fa820b` — 10,365개 레코드 검증(무결성 PASS).
- 증분 73개: GitHub Actions `43273459122` 의 성공 RSS manifest와 기존 ID/URL 전수 비교. 이전 10,365개의 ID/URL은 그대로, 신규 73개는 ID/URL 중복 없음.
- 별도 후보 저장소: `e8acd5e91f9f972974b5027a36056651098da71f` — sidecar 조각 27개 및 전체 manifest 해시 검증 PASS. 기준 8,145건이 10,438건으로 갱신되지 못함.

## 기사 상태 — 상호 배타적 합계 10,438건

| 상태 | 기사 |
|---|---:|
| FULL 본문 + 심층 검토 진행 기록 | 534 |
| FULL 본문 + 심층 검토 기록 없음 | 4,107 |
| PARTIAL 본문 + 심층 검토 진행 기록 | 9 |
| PARTIAL 본문 + 심층 검토 기록 없음 | 1,103 |
| UNAVAILABLE 본문 | 2,392 |
| 분석 sidecar 연결 없음 | 2,293 |
| **합계** | **10,438** |

- 원문 FULL 확보 증거는 4,641건(44.46%), 확인되지 않은 FULL 원문은 5,797건(55.54%).
- 심층 검토 '진행기록 존재' 689건이며 완료/입증이라는 뜻 아님.
- RSS AI DB 리뷰는 기본 원본 기준 9건. 기존 후보 플래그 5,147건은 검증된 병목 개수가 아님.
- 원본 DB 10,365건: ID 중복 0, URL 중복 0, 정규화 URL 중복 0, 날짜 누락 172, 요약 누락 66. 별도 감사 `43257020760`이 교차 검증.
- 같은 RSS DB의 `claims`, `evidence`, `candidates` 등 테이블은 각각 0행. 외부 연구 DB 전체가 0이라는 뜻은 아님.

## 갱신 실패의 재현된 원인

1. `43281231512` 미래 병목 후보 갱신: release guard 단계에서 `validated code/test file set changed or missing`로 실패. 본문 분석·후보 갱신 작업이 시작되지 않음. 어느 변경 파일이 문제가 됐는지는 별도 확인 필요.
2. `43279290610` RSS AI: `OPENAI_API_KEY_NOT_CONFIGURED`, 0건 처리, 정상 종료처럼 표시됐으나 실제 분석 skipped.
3. `43273459122` RSS 수집 자체는 정상: 피드 116개 성공, 실패 0개, 신규 73개 저장.

## 세션 2 인계

미확보·부분확보·미연결 기사 5,797건의 원문 확보 원인을 분리하고, release guard 판정과 CPU 자동 분석 연결을 복구한다. 검증되지 않은 후보 승격·기존 데이터 삭제·유료 API 자동 등록은 금지. 새 기사와 과거 미처리 자료의 대기열을 나누어 신규 기사 지연을 방지한다.

## 실제 검증 실행

- 10,365건 전수 기록 감사: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43257178219
- 독립 교차감사: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43257020760
- 최신 추가 수집: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43273459122
- 분석 실패: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43281231512
- AI 미실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43279290610

원본 main/data/future-bottleneck-data는 이 감사로 수정하지 않았다. 전체 10,438개 상태표 및 세부 결과는 해당 ChatGPT 대화의 `BCT_SESSION1_AUDIT_20261113.zip` 첨부본이 정본이다.
