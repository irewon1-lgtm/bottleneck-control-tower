# BCT V4 RSS 기사 전수 감사 — 세션 1 인계 (2026-11-13 KST)

## 판정
- **PASS:** 고정 시점 기사 10,365건의 ID·원문 상태·분석 기록 연결과 DB 무결성 검사 완료.
- **NOT COMPLETE:** 10,365건 전체의 본문 의미 분석이나 미래 병목 검증 완료가 아니다.
- 운영 main/data/future-bottleneck-data 원본 변경 없음. 감사용 격리 브랜치에만 기록.

## 데이터 고정점
- data SHA: `75e2705e1381d9a2a469d4f22360f2fb95fa820b`
- future-bottleneck-data SHA: `e8acd5e91f9f972974b5027a36056651098da71f`
- main source SHA: `7fc96389c4d91d99b582a8b0fa2006a8d54b3860`
- DB SHA-256: `654fa13f8d93fe908ff9e02835b6467a3e4450b72fdf1fce5e62d0153a762b87`
- GitHub Actions 검증: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43258629814
- 원본 검사 결과 및 기사별 CSV: 위 실행의 `bct-session1-audit` 아티팩트(보존 30일).
- Sidecar 27개 SHA-256 및 전체 manifest SHA-256 검증 통과.

## 확인된 수치
| 항목 | 확인값 |
|---|---:|
| 저장 RSS 기사 수 | 10,365 |
| 이전 스냅샷 | 10,333 |
| 신규 | 32 |
| 삭제 | 0 |
| 전체 고유 ID | 10,365 |
| Sidecar 처리기록 있음 | 8,145 |
| Sidecar 처리기록 없음 | 2,220 (기존 2,188 + 신규 32) |
| FULL 본문 확보 기록 | 4,641 |
| PARTIAL 본문 확보 기록 | 1,112 |
| UNAVAILABLE 본문 | 2,392 |
| 과거 심층 검토 진행 기록 고유 기사 | 689 |
| 같은 과거 입력 본문 SHA 일치 | 608 |
| 위 608건 중 현재 FULL 상태 | **475** |
| 위 608건 중 현재 UNAVAILABLE 상태 | 133 |
| 과거 검토 기록이 있으나 현재 기록 해시 불일치/소실 | 81 |
| RSS AI 리뷰 고유 기사 | 9 (OK 9) |
| 발행일 누락 | 172 |
| 요약 누락 | 66 |
| URL 정확 중복 | 0 |
| 등록 기사 발행 도메인 종류 | 47 |

본문 확보 성공 기록·과거 검토 진행 기록·AI 판독 기록·확정 병목 근거는 각각 다른 개념이다. FULL/원문 SHA 일치만으로 원문 바이트의 현재 재현 가능성을 증명하지 않는다. 서로 다른 URL의 의미 중복도 이번 식별자 검사만으로는 배제하지 못한다.

## Sidecar 8,145건의 기존 처리 코드
- CONTEXT_REVIEW 4,240; UNREAD_MATERIAL 1,798
- CANDIDATE_ONLY 907; NO_EVIDENCE 774
- EXCLUDED_NOISE 317; BODY_UNAVAILABLE 109
- 후보 플래그 5,147건은 검증 완료된 미래 병목이 아니다.
- 별도 V4 연구 공개 경로의 독립 수요·공급 연결쌍은 0건이며 위 수치와 합산하지 않는다.

## 다음 시작점 — 세션 2
1. 원문 UNAVAILABLE 2,392건의 HTTP/DNS/페이월/렌더링 등 실제 실패 원인을 구분.
2. PARTIAL 1,112건의 완전성 보완 가능성 점검. 원문 없는 기사에는 분석 완료 표시 금지.
3. 이전부터 누적된 미처리 2,188건과 신규 32건에 원문 확보 및 기초 판독 경로 연결.
4. 과거 검토 689건은 버전·접근 가능성 재확인: 현재 FULL·동일해시 475건만 별도 표시.
5. 후속 세션에서 검증된 독립 근거만 병목 후보 순위에 반영. 원본 DB·운영 배포는 별도 승인 범위에 따라 보존.

재현: 격리 브랜치의 `tools/session1_rss_audit.py`와 `.github/workflows/bct-session1-rss-audit.yml`. 이 실행은 소스 데이터에 쓰기 권한이 없다.
