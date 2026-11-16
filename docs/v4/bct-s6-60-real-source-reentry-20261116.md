# BCT V4 — Session 6: 실제 공개 원출처 60건 재진입 실행·판독 (2026-11-16 KST)

## 최종 범위와 판정

**고정된 기존 316건 중 선별된 60건에 대한 실제 공개 원출처 재접근과 기존 엔진의 본문 추출·스크리닝: PASS.**

**운영 연구 DB·LIVE·대시보드 최종 통합: NOT_RUN. 세션 6 전체: PARTIAL.**

기존 316건을 단순 PENDING으로 다시 표기한 작업이 아니다. GitHub Actions에서 60개 실제 기사 URL에 접근했고, 기존 `bct.future_bottleneck.run`을 **BACKFILL / SCHEDULED** 모드로 실행했다. 추출된 본문 전체·원출처 HTML·비공개 임시 캐시는 해당 실행 환경 밖으로 내보내지 않았다. 이미 현 최신 sidecar에 결과가 있는 기사는 중복 수집하지 않도록 사전 확인했으며 실제 이번 선택 60건은 재검사할 기존 결과가 0건이었다.

## 재현 가능한 실제 검증 증거

- [실제 원문 수집·본문 분석·저장·새 프로세스 재조회 #43861667664](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43861667664) — **SUCCESS**
- 방어적 단위 시험 6건 PASS, GitHub Actions 2개 작업 성공
- Source-free artifact `bct-s6-real-60-original-sourcefree-43861667664`, ID `14224420540`, GitHub SHA-256 `07584445de593e7d65923d6e17cbd39513bc6f6c8bd6df41e796de1b42e052e3`.
- 산출 `s6-60-sourcefree.sqlite3` SHA-256 `cb5b08065bd5083168520ed05abeaee0fec53d2adb4f2099b0891ab2e15ea292`. SQLite `integrity_check=ok`, 소스 요청 60행·본문 위치 해시 연구 단서 147행. 별도 Python 프로세스에서 재조회 `PASS_S6_60_REAL_ATTEMPT_SOURCE_FREE_FRESH_READBACK`.
- 이전 316/22/20 연구 원장 [#43857086796](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43857086796)의 원본 실행 ID·commit SHA·artifact ID/digest와 원장 내용을 재검증.
- RSS 정본 `data` SHA `a42a370044c3a5f8dc67af1faa1ec8bac6993e48`, SQLite SHA-256 `8fe6199653b6190e984844fbd352be43b15cec917911ec54386822e16c6fde7e`.
- 이번 재시도 전 확인한 `future-bottleneck-data` 최신 원격 SHA `cbca0429c8564982ffa9f24b7e0299423586a54a` 및 전체 저장 문서 SHA-256 `a88f33e96509892ad85668127f03bbabe77675dde9634551861e4d21cb759dbf`. 시작 시 갱신 세대의 39개 실제 샤드를 해시 복원해 60건 중 중복 처리 대상이 없다는 것을 입증. 자동 LIVE/CAS 갱신은 전혀 하지 않음.

## 실제 60건 처리 수치

| 항목 | 처리 수 / 주의사항 |
|---|---:|
| 원본 재접근 실행 | **60 / 60** |
| 현 sidecar 기존 결과라 실제 접속 생략 | 0 |
| 본문 `FULL` 판정 | **24** |
| 본문 `PARTIAL` 판정 | **22** |
| 본문 `UNAVAILABLE` 판정 | **14** |
| 원출처 발행자·실제 발행일·원본 본문을 엄격히 확인 | **18** |
| `FULL`이지만 엄격한 원문 출처 조건을 전부 통과하지 못함 | **6** |
| 원출처 본문 위치·해시로만 연구용 기록한 DEMAND/SUPPLY/RELIEF/CHANGE 탐색 단서 | **147** |
| 독립·적격·동일 기간 물리량 수급쌍 | **0 승격 (자격 증빙 부족)** |
| 기존 운영 원장·순위표·LIVE 쓰기 | **0** |
| 외부 유료 AI API / 비공개 모델 호출 | **0** |
| 임시 본문 전체·URL을 artifact에 포함한 건수 | 0 |

원문 오류·제한 사유 중 `HTTP_403=6`, `TIMEOUT=1`, `ARTICLE_CONTROL_ONLY=6`, `UNSTRUCTURED_ARTICLE_TEXT=11`, `TERMINAL_EXCERPT_MARKER=5`, `PREVIEW_OR_SUMMARY_CONTENT=2`, `NO_ARTICLE_CONTENT=1` 등은 **서로 겹칠 수 있으므로 14건과 합산 금지**. 어떤 출처는 본문이 일부 확보되어도 스니펫·기사 카드 형태로 제한된다.

## 판단 방식과 한계

- `FULL`은 기사 본문 형태를 통과한 상태이며 **원출처 검증 성공과 다르다**. 별도 publisher/body SHA/발행일 검증 통과 18건만 source-confirmed 코호트로 분리했다.
- 확인된 147개 문장 위치·SHA는 **연구용 추출 힌트**이다. 실제 고객 주문·제품 규격·기간·적격 미예약 공급능력의 독립 검증 완료 147개가 아니다. 동일 문서 내 DEMAND+SUPPLY 태그만으로 독립 공급 부족 쌍을 만들 수 없다.
- 사용자 승인에 따라 고정 TARGET 22건 HOLD와 기존 공식 원출처 근거 코드 20개를 그대로 보존한다. 이번 자료를 이전 섹터 순위표 '511건'에 더하지 않는다.
- `BACKFILL` 실험은 임시 캐시와 내부 결과 JSON을 실행 종료 시 삭제하고 **해시 기반 연구용 SQLite만** GitHub Actions artifact에 저장한다.
- 기존 본문 수집기·보호된 STRICT/EARLY/S 판정식·투자 순위/투자 의견·운영 대시보드·정식 RSS 데이터는 수정하지 않았다.

## 다음 우선 관문

1. 새로 원출처가 엄격 검증된 **18건**의 범위·기간·명시적 고객 수요와 적격 잔여 공급량을 독립 발행자 기준으로 대조. 147개 단서 가운데 같은 계약/보도자료 재인용을 중복 수요·공급으로 세지 않도록 한다.
2. **22건 PARTIAL + 14건 UNAVAILABLE**를 접근 제한, 복구 가능 여부, 도메인, 출처 특성으로 분리한 재시도 예산 수립. `HTTP_403`·인증/과금 접근 제한은 무단 우회 없이 HOLD.
3. 검증 가능한 source-bound 사실만 별도 운영 연구 DB 소유권·CAS 저장/재조회로 통합. 현재 60건 source-free 연구 스냅샷 자체가 LIVE 후보·운영 대시보드 갱신 승인을 뜻하지 않는다.
4. 나머지 316−60 = 256개 과거 미연결 RSS ID도 현재 sidecar 재조회 기준으로 새 처리와 중복을 제거하며 후속 회차에 진행한다.

**이번 단계 판정:** `PASS_ACTUAL_PUBLIC_REENTRY_ATTEMPTS_AND_RESEARCH_HOLD`. 전체 세션 6 완료는 아직 **PARTIAL**.
