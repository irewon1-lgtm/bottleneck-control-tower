# BCT V4 RSS — 세션 1 전수 감사 (2026-11-13 KST)

**판정: 세션 1 PASS / RSS 기사 전체 병목 분석 완료는 아님**

- 감사 실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43258060761 — success
- 기사별 CSV 포함 아티팩트: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43258060761/artifacts/13963890095
- 운영 data SHA: 75e2705e1381d9a2a469d4f22360f2fb95fa820b
- 분석 future-bottleneck-data SHA: e8acd5e91f9f972974b5027a36056651098da71f
- 감사 코드 SHA: 43e429b80bc3e2b59bd33c4ec1b2c514d7923cb9
- 기사별 CSV SHA256: 414f956bbe98a84df8e078f812c76b997b3d8c620b16b11fca8adbc2ea1b8fdd
- 현재·이전 SQLite 무결성/상태 해시, 현행 분석 조각 27개 해시 검증: PASS.
- 운영 main, data, future-bottleneck-data 내용 변경: 0건.

## 기사 10,365개 고유 ID 전수 대조

| 항목 | 기사 수 |
|---|---:|
| RSS 전체 / 감사 CSV 대장 행 | 10,365 |
| 분석 결과가 연결된 기사 | 8,145 (78.58%) |
| 분석 결과 없는 기사 | 2,220 (21.42%) |
| 본문 FULL | 4,641 |
| 본문 PARTIAL | 1,112 |
| 본문 UNAVAILABLE | 2,392 |
| 본문 상태도 미확인 (분석 결과 없음) | 2,220 |
| RSS 전용 AI 검토 | 9 (모두 OK) |
| 중복 기사 ID / 정확·표준화 URL 중복 | 0 / 0 |
| 발행일 누락 / RSS 요약 누락 | 172 / 66 |
| 기사가 저장된 출처 도메인 | 47 |

합계: 4,641+1,112+2,392+2,220=10,365. 직전 DB 10,333건 대비 신규 32건. 분석 결과 저장소 8,145개는 전부 현재 DB ID와 연결되고 고아 ID 0건.

### 분석 분류 상태 (검증 완료 아님)

- CONTEXT_REVIEW 4,240 — 문맥 검토 대상 표시이며 완료 의미가 아님.
- UNREAD_MATERIAL 1,798 — 실질 내용 미판독.
- CANDIDATE_ONLY 907 — 후보 수준, 병목 확정 금지.
- NO_EVIDENCE 774, EXCLUDED_NOISE 317, BODY_UNAVAILABLE 109.
- NOT_IN_SIDECAR 2,220.

### 세션 2 우선 점검할 출처

| 출처 | 전체 | FULL | PARTIAL | UNAVAILABLE | 분석 기록 없음 |
|---|---:|---:|---:|---:|---:|
| supplychainbrain.com | 619 | 0 | 0 | 390 | 229 |
| miningweekly.com | 616 | 147 | 0 | 341 | 128 |
| tomshardware.com | 697 | 0 | 458 | 106 | 133 |
| hpcwire.com | 350 | 12 | 166 | 69 | 103 |
| datacenterdynamics.com | 736 | 564 | 20 | 3 | 149 |
| autoevolution.com | 1,777 | 935 | 0 | 484 | 358 |

대표 원문 확보 실패 코드: HTTPError 938, UNVERIFIED_BODY_SCOPE 837, NO_ARTICLE_CONTENT 390, ARTICLE_CONTROL_ONLY 340, HTTP_403 300, TimeoutError 293. 여러 사유가 같은 기사에 중복될 수 있으므로 합산 금지.

## 세션 2 인계 기준

1. 위 고정 SHA들을 시작점으로 사용하고, 저장소 최신화가 있다면 차분만 계산한다.
2. 분석 미연결 2,220건과 원문 미확보 2,392건은 다른 대기열로 관리한다.
3. PARTIAL 1,112건은 전문 재확보를 시도하되 기존 FULL 4,641건은 재사용한다.
4. 재확보 전후 원문 해시와 수집·발행 시각을 확인하고 출처 오류는 보존한다.
5. 본문 또는 독립 수요·공급 근거가 없는 기사를 병목 확정으로 승격하지 않는다.
6. 과거 여러 버전 조각 파일이 누적된 future 브랜치 전체(약 31GB)는 가져오지 않고, 현행 불변 조각만 조회한다.
7. 운영 DB 무삭제, 무료 수단 우선, 세션별 점검 결과와 SHA 고정 기록.

세션 1 성공은 기사별 상태 및 증거 경로 감사 완료를 의미한다. 전체 기사 실질 의미 분석 완료를 뜻하지 않는다.
