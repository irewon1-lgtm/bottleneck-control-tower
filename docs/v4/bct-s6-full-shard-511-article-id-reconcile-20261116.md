# BCT V4 — 세션 6 운영 전체 샤드·공개 근거 511건·RSS 기사 ID 실데이터 대조 (2026-11-16 KST)

## 이번 검증 범위와 판정

- **분할 sidecar 전수 복원·SHA 검증: PASS** — 실제 운영 `future-bottleneck-data`의 독립 샤드 40개(후보 39, TARGET 추적 1)를 원격 저장된 Git blob과 전체 문서 재조립 SHA로 검증. `bct.future_github.assemble` 기존 정식 로더 그대로 사용.
- **공개 대시보드에서 511건이 생성되는 이유: PASS** — 실시간 RSS 신규 기사 수가 아니라 **2026-10-14 23:16:13 UTC 역사적 연구 자료**를 그대로 합산한 수치라는 것을 실제 게시된 Pages tar 1,703개 근거 상세 파일과 dashboard.json으로 검증.
- **정식 RSS SQLite와 후보 분석 sidecar 전체 ID 대조: PASS** — 실제 GitHub `data/canonical.sqlite3` SHA-256 검증, 10,992건 기사와 sidecar 10,676개 저장 결과 ID를 직접 조인.
- **이번 source-free 검증 DB 저장·재조회: PASS**, **운영 원장 변경 및 후보 승격 0건**.
- **세션 6 전체 적격 수요·공급 증거 DB 통합 / 선행탐지 성능 / 대시보드 최신 집계 교체: 아직 NOT_RUN·PARTIAL**. SHA/ID/URL이 있다고 실제 적격 수급쌍이 형성되지는 않는다.

## I. 최초 전수 복원 (실제 실행)

[GitHub Actions #43846030879](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43846030879) SUCCESS. 아티팩트 `14214378829`, SHA-256 `e289bdce90c734ca42cf869ac9ba280c0e859d4d32dce02b79e9bfa391eaf9a3`. 검증 당시 고정 커밋:

| 운영 브랜치 | 정확한 SHA |
|---|---|
| `data` | `a42a370044c3a5f8dc67af1faa1ec8bac6993e48` |
| `future-bottleneck-data` | `873c2ab0df51d5cbd81cceb4575bf6d0e98d74d7` |

복원된 `future-candidates.json` 전체 문서 SHA-256 `3609abfc29908ec8046e197fdde00a693143504b44f4d2d5f46fc8da5f56d236` (39 샤드), `future-tracking.json` `95538e7ef88e6c111c308085e9b6ae0249fdba517da54cbebc4b404a7ae622a8` (1 샤드). 각 샤드의 Git Blob SHA, 실제 바이트 SHA-256, 행 수, 필드 순서 및 복원 전체 문서 SHA PASS.

| 데이터 종류 | 확인된 저장 건수 | 해석 한계 |
|---|---:|---|
| 기사별 결과 `results` | **10,676** | 분석 내용 저장 객체, 독립 수급쌍 아님 |
| 가설 `hypotheses` | **8,415** | 확정 시장 병목 아님 |
| 묶음 사건 `events` | **13,077** | 인과 관계를 보장하지 않는 사건 묶음 |
| 상태 `FULL` | **6,052** | sidecar에 저장된 본문 판독 상태, 별도 원출처 검증 필요 |
| `PARTIAL` | **1,665** | 일부 본문 |
| `UNAVAILABLE` | **2,959** | 본문 미확보 |
| 수요·공급 양쪽 태그 동시 존재 | **738** | 한 문서의 두 태그로 독립 수급쌍 판정 불가 |
| 등록 TARGET | **22** | 고정 등록 TARGET |
| TARGET별 원문 링크 연결 | **427** | URL×TARGET 연결 수 |
| TARGET 전체 중복 제거 고유 URL | **383** | URL 수, 진짜 검증된 공급·수요쌍 수 아님 |
| 다른 TARGET에 반복 연결된 URL | **44개 연결분** | 중복 연결 (427−383) |

원출처 발행자/공개일/본문 해시가 기록되어 있어도 **본문 전체·사건 범위·제품 규격·고객 적격성·독립 출처와 공급량**을 별도로 입증해야 한다.

## II. 실제 공개 대시보드가 511건을 보여주는 이유

[최신 Published Pages 아티팩트 증빙 #43847161947](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43847161947) SUCCESS. 원본 아티팩트: 2026-11-16 [Read-only BCT Pages #43838794301](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43838794301), artifact `14211394848` ZIP digest `641cf9c02359db448a34e02f35e9a58b1d72453ee4be8514b053e39a25368316`. 1,703개 페이지 근거 JSON을 전수 검증하여 보고서·원장 ID가 게시된 본문 파일에 연결됨을 확인.

### 단위와 출처

| 집계 지표 | 값 | 실제 정의 |
|---|---:|---|
| 구 연구 순위표 근거 집계 `counts.evidence` | **511** | `reviewed=23` + `structured=211` + `discovery=277` |
| 511 중 섹터별 분류·순위 입력 | **508** | 과거 511 중 섹터 지정 |
| 미분류 과거 기록 | **3** | 508+3=511 |
| 공개 사이트 상세 JSON 총계 | **1,703** | 기존 511 + `cpu_product=1,186` + `reported=6` |
| 공개 사이트 새 원출처 랭킹 오버레이 | **520** | 과거 섹터 입력 508 + 별도 신규 원문검증 12 (적격쌍 미확인) |
| 해당 Pages 빌드의 정식 RSS 기사 | **10,992** | 운영 RSS DB 기사 수, 근거 레코드 511과 단위 상이 |

과거 연구 순위표의 기록 기준은 **2026-10-14T23:16:13.592709Z**. 2026-11-16에 사이트를 다시 생성했더라도 **과거 511건의 수집·분류·검증 생성 날짜가 자동 갱신된 것이 아님**. 실제 배포 빌드의 소스 브랜치는 `codex/bct-v4-integration`, 코드 커밋 `ce1c28ce20ea0dbccaef14794a03e81f0061eec3`이며 이번 작업의 최신 `main`/private CPU 검증 코드를 자동 반영한 것으로 보면 안 된다.

**결론:** ‘RSS 1만 건인데 왜 근거 511건인가’의 주된 원인은 게시된 과거 순위표의 **별도 역사적 자료 파이프라인 및 서로 다른 집계 단위**다. 511을 독립적으로 검증된 수급 증거로 해석하면 안 된다. 게시된 서술형 근거 증가는 실제 원출처·고유 사건 검증과 보완되어야 한다. S1/S2/S3 확정 선행 신규 후보=0.

## III. 정식 RSS 전체 ID와 sidecar 전수 결합

[실제 ID 조인 #43848052967](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43848052967) SUCCESS. RSS 원본 운영 SQLite SHA-256 `8fe6199653b6190e984844fbd352be43b15cec917911ec54386822e16c6fde7e`. 소스 39개 샤드를 모두 재조립한 실제 sidecar ID와 `radar_items.id` 필드를 연결. source-free 아티팩트 `14216431920`, digest `9451e9e01dbbaf26f65264a73f49cb04bb85531584b37f742ea1899b0f8a079d`.

| ID 결합 상태 | 기사 ID | 정식 RSS `status` |
|---|---:|---|
| BOTH: 정식 DB와 분석 sidecar 모두 있음 | **10,676** | 모두 active |
| CANONICAL_ONLY: 정식 DB에는 있지만 sidecar 결과 없음 | **316** | **전부 active** |
| SIDECAR_ONLY: 분석 결과만 있고 정식 DB에는 없음 | **0** | 해당 없음 |
| 고유 RSS 기사 전체 | **10,992** | 모두 active |

전수 조인을 이용한 결과로, 단순 `10992−10676` 계산과 달리 서로 다른 ID 집합이 섞여 있지 않다는 점을 증명했다. 10,992개 기사 ID의 SHA-256만 담은 원장 `s6-article-id-join.sqlite3` 및 fresh independent process SQLite readback PASS.

**후속 조치:** 누락된 316개 **active RSS 기사**를 기존 reader의 원문/분류/CPU 처리상태와 조인하여 `PENDING`/`SOURCE_WAIT`/`FAILED`/`DONE`을 분리하고, 새 수집과 과거 적체 혼합 처리 시 재진입 대상으로 사용한다. 하지만 이 316개가 전부 CPU 미판독이라는 주장은 아직 하지 않는다. 사이드카에 결과가 없다는 상태만 확인한 것이다.

## IV. 완료·보류 경계

이번 작업에서 **실제 전체 샤드 복원·현재 기사 ID 대조·511의 역사적 근거 원인 규명**은 모두 실데이터 PASS. 그다음 세션 6 핵심 남은 관문은 운영 정식 DB 기사·분석 기록·원문 해시·실제 근거(locator)·독립 발행자·동일 규격 수급쌍을 한 원장에 구조적으로 통합한 후 다시 조회하는 것이다. 기존 511·520·1,703·10,676을 한 열로 합산하거나 기존 TARGET 22 HOLD를 임의 승격/반려하면 안 된다. 

새 코드:
- `tools/bct_s6_full_sidecar_reconcile.py` / native assembler verified full shards
- `tools/bct_s6_pages_511_audit.py` / published Pages evidence category exact checksum and counts
- `tools/bct_s6_canonical_article_id_join.py` / real canonical SQLite-to-sidecar ID join and hashed replay
- 각 3개에 해당하는 adversarial tests와 branch-gated read-only GitHub Actions workflow

기존 `data`, `future-bottleneck-data`, `LIVE`, `RSS`, CPU private ref, source versions, Objective Lock, public dashboard, rank, strict/EARLY/S 엔진 **수정 없음**. 새 SQLite는 별도의 검증 아티팩트에만 저장했고, 모든 결과는 새 프로세스로 재조회했다.

**최종:** S6 기초 운영 DB 샤드·기사 ID 복원 및 공개 근거 집계 원인 감사 PASS. **S6 전체 실제 근거 DB 통합 PARTIAL / NOT_RUN**, 7·8세션 아직 시작 가능 PASS 아님.
