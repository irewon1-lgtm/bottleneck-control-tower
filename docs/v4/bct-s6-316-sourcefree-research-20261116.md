# BCT V4 — 세션 6: 미연결 활성 RSS 316건 분류와 공식 원문 20개 근거 연구 DB (2026-11-16 KST)

## 완료 범위 및 판정

- **316개 전건 ID 및 원문 처리상태 분류: PASS**
- **기존 TARGET 22개 HOLD 원장 + 공식 원문 근거 20개 별도 연구용 SQLite 연결: PASS**
- **독립 프로세스의 실제 SQLite 무결성·원장 재조회: PASS**
- **316개 실제 원출처 수집 또는 CPU 판독: NOT_RUN**
- **기존 운영 연구 DB CAS 통합 / 대시보드 최신 집계 교체 / 세션 6 전체 완료: NOT_RUN / PARTIAL**

[GitHub 실데이터 Actions #43857086796](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43857086796) SUCCESS. Source-free artifact `bct-s6-316-sourcefree-research-43857086796`, ID `14220458504`, SHA-256 `542d38565e7bf13051fb11e0c3f5b8d9de6f7c16b2d7a27c55d1f2d480e6c5eb`.

## 이전 완료 자료를 원본 SHA와 함께 재사용

새로 39개 샤드를 반복 내려받거나 10,992 RSS와 10,676 결과 ID를 재조립해 중복 개발하지 않았다. 이미 검증된 다음 4개 영수증·SQLite를 **원격 GitHub Actions ID/HEAD/artifact SHA-256와 실제 파일 SHA-256로 재인증**했다.

| 종류 | 고정 성공 실행 | 검증 내용 |
|---|---|---|
| RSS 기사 ID/결과 ID 전수 조인 | [#43848052967](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43848052967) | 전체 10,992 RSS, 결과 10,676, 미연결 316, ID 해시 기록 |
| S5 22 TARGET HOLD 분류 | [#43827657779](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43827657779) | HOLD 22, 적격 0, 반려 0 |
| Standard Nuclear Q3 원문 | [#43821707141](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43821707141) | 위치+해시 확인된 근거 12개 |
| Centrus·BWXT 공개 원문 | [#43824301850](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43824301850) | Centrus 2개 형식 동일 경제 사건 중복 제거; BWXT 별도 사건; 고유 사실 8개 |

운영 세대는 `data` `a42a370044c3a5f8dc67af1faa1ec8bac6993e48`, `future-bottleneck-data` `873c2ab0df51d5cbd81cceb4575bf6d0e98d74d7`, 정식 RSS SQLite SHA-256 `8fe6199653b6190e984844fbd352be43b15cec917911ec54386822e16c6fde7e`. 이 커밋과 이전 원장 집합을 확인한 고정 스냅샷의 결과이며 현재 실시간 DB와 동일한지는 새 실행 시 확인해야 한다.

## 실제 검증 결과

| 대상 | 수치 | 증빙 범위 / 해석 |
|---|---:|---|
| 저장된 정식 RSS 고유 기사 | 10,992 | 이전 ID 조인 원장의 pinned 세대 |
| 이전 저장 결과가 있는 기사 | 10,676 | ID 일치, 수급쌍 자격과는 무관 |
| 이전 분석 sidecar가 없는 ACTIVE RSS 기사 | **316** | 원본 ID→SHA 매핑 + SQLite 직접 조회 |
| 316건 원출처 재확인 대상으로 분류 | **316** | *실제로 조회·취득한 것은 아님* |
| 316건 중 원문 접근 실패를 직접 검증한 건수 | 0 | 검증 부재. 실제 실패 없음이라는 뜻 아님 |
| 316건 중 CPU 판독 실패를 직접 검증한 건수 | 0 | 판독 수행 여부가 별도 로그 없이 불명 |
| RSS 제목·요약 AI 기록 확인 | 0 | 이번 원장 해당 316건에 연결되는 별도 annotation 없음 |
| 다음 재진입 계획에 선별된 고유 기사 | **60** | 기존 hostname 쿼터/시점 편향 방지 계획. *실행 안 됨* |
| 등록 TARGET HOLD | **22** | 기존 상황 유지 |
| 공식 원출처 근거 고유 코드 | **20** | Standard 12 + Centrus 5 + BWXT 3, 연구용만 |
| 신규 독립 적격 수급쌍 | **0 승격** | 실제 물량 자격 충족은 NOT_EVALUATED |
| 기존 운영 DB / sidecar / LIVE / 순위표 쓰기 | **0** | 소유권 보존 |

316건에 이전 sidecar 기록이 없다는 사실만으로 `SOURCE_WAIT`, `CPU_FAIL`, `DONE`을 단정할 수 없었다. 전체를 `SOURCE_RECHECK_ELIGIBLE_UNKNOWN_PRIOR_BODY`로 분류했다. 존재하는 근거를 삭제하거나 기사 내용·계약량을 가정하지 않았고, 실 수급 비교를 진행했다고 주장하지 않는다.

## 새 연구용 원장

생성된 `s6-research-sourcefree.sqlite3`의 테이블:

1. `article_intake`: 기사 원본 ID 자체는 노출하지 않고 해시 ID 316건, 이전 결과 없음/원문 상태 불명/재확인 대상 상태
2. `source_reentry_plan`: 최대 120건 요청 범위 중 실제 60건 계획 순서, **수집 완료를 의미하지 않음**
3. `target_holds`: 22개 정식 TARGET HOLD
4. `research_facts`: 발행자·공개 원문 해시·문자 위치 해시를 가진 서로 다른 20개 SOURCE-BOUND 사실. Centrus 웹+PDF 재게시를 동일 인과 사건으로 병합. 자동 적격 수급쌍 생성 불가.

데이터는 GitHub Actions의 별도 source-free artifact에 저장했으며 새 Python 프로세스에서 316/60/22/20 전부 건수·payload SHA·SQLite integrity_check 및 HOLD 경계 검증 PASS를 확인했다. 원문 전체, 기사 제목/URL, 사적 모델 입력은 해당 artifact에 저장하지 않았다.

## 세션 6 최종 완료를 위해 남은 일

- 316개 미연결 중 실제 재진입 대상 60개의 원문 재수집/처리 작업 실행 및 저장 재조회. 작업 전에 최신 HEAD와 상태 변경 여부 다시 검증하고, 이미 작업을 완료한 기사는 다시 수집하지 않는다.
- 기존 공개 원문 근거 20개는 '확인된 기사 사실'일 뿐 '독립적·적격·미예약·동일 시점 수급 쌍'이 아니다. 규격·지역·기간·제품·고객·가용 공급량·독립 경제 사건 여부를 검사해 충분한 조건을 충족하지 않으면 HOLD 유지.
- 전체 정식 운영 연구 DB에 실제 근거 ID·버전·원문 해시·locator·인과 중복 계보를 CAS로 통합하고 재조회. 원본 511개 역사적 자료는 삭제하거나 근거 ID를 재사용하지 않는다.
- 분할 샤드의 분석 결과 건수 10,676, 공개 과거 511, 발표 사실 20, TARGET 22 HOLD를 **서로 다른 단위로 보존**한다.
- 세션 6 운영 DB 통합이 실제 저장·재조회 PASS를 보이기 전에는 전체 PASS·세션 7 자동 승격을 선언하지 않는다.

## 변경 및 안전 경계

추가 연구 코드 `tools/bct_s6_316_sourcefree_intake.py`, 적대적 회귀시험 `tests/test_bct_s6_316_sourcefree_intake.py`, 별도 branch-scoped 읽기 전용 workflow `.github/workflows/bct-s6-316-research-intake.yml` 및 본 보고서만 추가. 기존 운영 DB·RSS 파이프라인·CPU·protected STRICT/EARLY·LIVE·공개 화면·기존 S4/5 인증 아티팩트 원본 변경 없음.

**판정: S6 미연결 316건 분류 및 22+20 연구용 DB source-free 연결 PASS, 전체 세션 6 PARTIAL.**
