# BCT V4 — Session 6 initial actual operating-sidecar metadata baseline (2026-11-16 KST)

## 판정

**PASS — 운영 `data` 및 `future-bottleneck-data` 두 브랜치의 실제 고정 SHA 기준 파일 5개 메타데이터 검증·SQLite 저장·재조회 완료.**  
**세션 6 전체 실제 원장 통합: NOT_RUN.**  
**공개 화면 근거 511건 정확한 식별자·중복·원출처 검증: NOT_DETERMINABLE_FROM_MANIFESTS.**

이 단계는 단순한 문서상의 예상 결과가 아니라, 실제 GitHub 운영 브랜치의 HEAD를 읽고 SHA를 동결하여 그 커밋의 파일 내용(정확한 Git blob SHA-1과 자체 SHA-256)을 확인한 실데이터 검사다. 두 운영 브랜치는 변경하지 않았으며 수집·AI·LIVE·후보 등급 승격도 수행하지 않았다.

## 실제 실행 / 이력

- [실제 S6 메타데이터 baseline 실행 #43830109486](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43830109486): **SUCCESS**.
- 우선 이전 S5 전체 등록 TARGET 22건의 고정 결과 [#43827657779](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43827657779) 및 source-free 아티팩트 `14207241610`/SHA-256 `84fe8339a0a8d0f0a733531e552cf8ae7c7827ba6705c86175efc1204272e136`를 확인.
- 이후 브랜치 변경 여부를 다시 검사해 해당 실행 중 두 HEAD가 바뀌지 않았음을 확인.
- 저장/재조회 결과: `PASS_READONLY_FIVE_MANIFEST_SQLITE_REQUERY` (5개 파일), `BCT_S6_CURRENT_METADATA_SOURCE_BOUND_GATE_PASS`.
- 결과 artifact: `bct-s6-research-only-metadata-43830109486`, ID `14207518996`, SHA-256 `eb22041a32391a271efc7061605efc3cae2e8201d921b27007e7dfbd620b1a29`.

### 검증 당시 기준 원격 커밋

| 브랜치 | 실제 검사한 SHA |
|---|---|
| `data` | `529d0667cf325d25a8d9b576a90e6a98f9d28ca5` |
| `future-bottleneck-data` | `3b39a670a040fdd1a8a9773c48a8754fc0eca50e` |

이는 **실행 당시의 읽기용 스냅샷**이며, 이후 자동화로 브랜치 HEAD가 변할 수 있다. 다음 분할 샤드 처리 시작 시 다시 최신 SHA와 CAS를 검증해야 한다.

## 두 종류의 카운트를 절대 혼동하면 안 됨

| 단위/원천 | 정확한 값 | 검증의 의미 |
|---|---:|---|
| `future-tracking.json`의 `targets` | **22** | TARGET 관리 인덱스 엔트리 수; S5 동결 22건과 수치 일치 |
| `future-candidates.json`의 `results` | **10,676** | `results` 객체의 메타데이터 기반 항목 수, 검증된 병목 근거 수 아님 |
| 같은 파일의 `hypotheses` | **8,415** | 가설 인덱스 항목 수, 완성된 독립 수급쌍 수 아님 |
| `data/v4-public/research.json`의 `PARTIAL` | **35** | 공개 V4 연구 스냅샷 내 상태 |
| 같은 파일의 `READ_EVIDENCE_HOLD` | **21** | 공개 V4 연구 스냅샷 내 보류 상태 |
| 같은 파일의 `UNREAD` | **165** | 공개 V4 연구 스냅샷 내 미판독 상태 |
| `data/precursor-index.json`의 최근 신규 검증 원출처 | **0** | 해당 이전 공개 수집 run의 신규 검증 수, 모든 기간의 누적 원출처 수 아님 |
| 전체 공개 섹터 순위표의 검증 근거 '511' | **미확인** | 이 5개 메타데이터 파일만으로 해당 숫자를 재검증할 수 없음 |

특히 V4 공개 연구 스냅샷의 35/21/165는 최근 별도 비공개 CPU epoch의 세션 4 원본 11건 판독 완료 상태를 반영했다고 단정하면 안 된다. 이 둘은 다른 세대/저장소다.

## 세션 6 다음 필수 작업

1. 이 고정된 운용 브랜치의 **실제 최신 분할 샤드 전체**를 선택한 시점의 SHA로 복원해 각 원본 내용 SHA-256과 자료 구조를 확인한다. 전체 파일 미복원 상태에서 `results`/가설/기사 개수를 근거 수로 대체하지 않는다.
2. 기사 ID / 원본 발행자+URL+공개일 / body SHA / 독립 DEMAND 및 적격 SUPPLY의 근거 ID / 재인용 중복 ID를 분리해 실 측정한다.
3. 기존 대시보드가 보여주는 ‘근거 511건’ 정의와 실제 데이터의 **고유 단위와 기간**을 대조한다. 숫자가 다른 이유를 데이터 불일치, 중복, 필터 및 미처리로 따로 분류한다.
4. S5의 22개 HOLD는 새 데이터에서 실제 검증 통과한 수급쌍과 원문 위치가 나올 때만 상태 변경 검토한다. 운영 `LIVE`와 순위표는 승인된 생산 검증 후에만 수정한다.
5. `data`, `future-bottleneck-data`, `live-state`, 기존 private 연구 상태 각각 소유권과 CAS 비교 기준을 지킨다.

## 안전 경계

`tools/bct_s6_operating_manifest_baseline.py`, `tests/test_bct_s6_operating_manifest_baseline.py`, `.github/workflows/bct-s6-metadata-baseline.yml` 및 이 보고서만 추가. 새로운 research-only SQLite와 JSON 영수증만 GitHub Actions artifact로 남긴다. 기존 운영 브랜치·원문·S4 CPU checkpoint·보호된 S1/S2/S3/STRICT/EARLY 엔진 및 대시보드는 변경하지 않는다.

**세션 6 현재 단계: metadata baseline PASS, 전체 증거 ID·수급쌍 원장 통합 NOT_RUN.**
