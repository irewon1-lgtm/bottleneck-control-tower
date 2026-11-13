# BCT V4 — 세션 3 전체 RSS 메타데이터 선별 인계 (2026-11-13 KST)

## 실행 검증 (실데이터)
- GitHub Actions: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43332621635 — PASS
- Stage 0 전체 회귀: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43332621541 — PASS
- 원본 data: `da7b17f34d58c69c72b5d067d6279ec98db8bb44`, 기사 총 10,510건, 원본 DB SHA256 `39d6d562d398a60ce1345ec6a6d84a512a56d5c3994593fa25a4be2b25337b06`.
- 과거 sidecar: `e8acd5e91f9f972974b5027a36056651098da71f`, 결과 8,145건. Manifest와 27개 분할파일 SHA256 검증 PASS. 기존 분석 기록 없는 기사 2,365건.
- 이번 세션 신규 *본문* 다운로드 / 유료 AI API / 증거 승격: 각각 0.

## 제목·요약 선별 결과 (원문 FULL 분석과 명확히 구분)
| 우선 검토 | 건수 |
|---|---:|
| P1 다중 신호 + 구체 키워드 | 66 |
| P2 구체 키워드 또는 다중 신호 | 1,075 |
| P3 넓은 의미 변화 신호 | 2,509 |
| P4 제목·요약 단서 미발견 | 6,860 |
| **총합** | **10,510** |

- 키워드/넓은 신호 총 3,650건. 이는 병목 확정 수치가 아님.
- 중복 집계 가능한 분류 신호: 수요(DEMAND) 2,812, 공급 제약(SUPPLY) 658, 공급 완화(RELIEF) 1,332.
- 기존 FULL 4,641 / PARTIAL 1,112 / UNAVAILABLE 2,392 / 측정기록 없음 2,365. FULL 미확인 합계 5,869.
- P1 66건: FULL 23, PARTIAL 6, UNAVAILABLE 24, prior 측정 없음 13. 원문 미확인 P1 43건.
- 48개 출처 도메인; RSS 발행일 없음 174, RSS 요약 없음 66.
- 기사별 상태 CSV 10,510줄+헤더 / 동일 ID 중복 0 / 키워드 이외의 병목 확정 근거 0.
- P1은 메타데이터 검토 *순서*일 뿐 S1/S2/S3가 아니다. 제목·요약의 단어만으로 제품, 필요기간, 적격 공급능력을 연결하거나 '병목 없음'으로 확정하지 말 것.

## 코드/파일
- `tools/bct_session3_firstpass.py`: 원본 DB 무결성, 모든 ID 보존, 동일 실데이터 재현, 엄격한 sidecar 원본 해시 검증, 제목·요약 신호 분류
- `tests/test_bct_session3_firstpass.py`: 미검증 상태 및 중복 방지, 신호 탐지, 보수적 판정
- `.github/workflows/bct-session3-firstpass.yml`: 격리 브랜치 읽기 전용 실행. `contents: read`, 0 API 호출, DB 및 sidecar 게시 변경 없음.
- 아티팩트: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43332621635 (article_firstpass.csv/firstpass_summary.json/firstpass_report.md).

## 추가 교차검증: 제목·요약만 기준으로 후순위 처리하는 오류 발견 및 수정
- P4 제목·요약 신호 미발견 6,860건 중 **2,843건**은 과거 FULL 본문 분석의 CONTEXT_REVIEW 또는 CANDIDATE_ONLY 기록이 있다.
- 그러므로 메타데이터 P4는 기존 본문 근거 없음으로 표시하면 안 된다. 신규 코드에서 과거 FULL 본문 단서가 제목 우선순위보다 먼저 검토되도록 통합 queue 추가.
- 모든 기사를 정확히 한 번 포함하는 통합 queue (고정 source를 로컬 교차 검증, 실행 기반 재검증은 별도): Q1 기존 FULL 원문 단서 4,236 / Q2 PARTIAL 단서 642 / Q3 원문 불가 과거 단서 269 / Q4 제목·요약 단서만 1,898 / Q5 현재 분류에서 단서 없음 3,465.
- 이 5개 queue 상태는 **병목 판정 등급이 아니라 향후 검토 순서**이다. 본문 FULL 단서 4,236건은 독립 수요·공급 검증 4,236건이 아니다.
- 추가 검증: P4 2,843건 복원/유지, P1 기존 FULL 23건과 미확인 43건을 분리, 총합 10,510 보존.
- 단일 키워드의 오탐이 예상되므로 Q1을 통째로 승격하거나 기존 P4를 통째로 폐기하지 말 것.

## Gate 0~6 / 운영 상태
- 이전 main `a897e80d392911c4ea9dc4dc3a44908aa83dab3a` Gate 실제 재실행 ID `43330584731`: 이 기록 작성 시 Gate0/1 처리 진행 중, 전체 PASS 미확인.
- 이 세션 연구 브랜치 결과는 Gate를 우회하여 운영 main 또는 verified future-bottleneck-data로 승격하지 않았음.
- 최신 data가 전수 스냅샷보다 증가하면 다음 실행은 새 데이터 커밋과 정확한 분모로 다시 검사할 것.

## 다음 작업의 우선 순서
1. 최신 Gate run 결과 및 운영 release receipt 갱신 여부 확인.
2. P1 66개 가운데 원문 FULL 미확인 43개부터 확보 시도/원인 분리 (접근 제한 우회 금지).
3. P1 FULL 23개 + P1 미확인 사례를 실제 원문으로 독립 평가해 Precision/Recall 측정 (세션 4).
4. 신규 RSS와 미분석 2,365건의 queue 연결은 별도 자동화 개발에서 검증; 이 메타데이터 run만으로 완료라 주장 금지.
5. 원문 확보 실패 5,869건은 단서 미발견의 근거가 아님.

검증된 실행 기록에 없는 성공·숫자·미래 병목 확정을 추가하지 말 것.
