# BCT V4 — 세션 5 전체 등록 TARGET 검토 및 세션 6 연구용 이관 (2026-11-16 KST)

## 범위와 판정

**등록 TARGET 22개 고정 코호트 검토: PASS.**
**BCT 전체 시장·RSS 1만 건 전수 검증: NOT_PERFORMED.**
**세션 6 연구용 HOLD 이관 준비: PASS.**
**세션 6 운영 근거 DB 통합: NOT_RUN.**

이 검토는 기존 등록 대상 전체 22개에 대해 적격(QUALIFIED)·반려(REJECTED)·보류(HOLD)를 각각 출처가 있는 근거로 구별하는 제한된 연구 관문이다. 과거 대시보드 `FUTURE`나 `EMERGING` 상태를 자동으로 수급 검증 통과로 바꾸지 않는다. 반대 증거를 실제로 검증하지 못한 대상을 자동 반려하지 않는다.

## 실제 검증된 실행

- [2026-11-16 TARGET 22개 전체 검토, S6 연구용 인계 및 SQLite 새 프로세스 재조회: #43827359814](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43827359814) — **SUCCESS**, 개별 방어 시험 8개 PASS.
- Source-free artifact: `bct-s5-22-target-source-free-handoff-43827359814`, ID `14206987973`, SHA-256 `2a8d8b4fa605521ccd16af632684e96ef2949bc2ea6e96e150a10c71f154d36c`.
- Research SQLite SHA-256: `f3bdaab8fdfac72605d169b07bfdfbed128b0ebef41605b00f16b0f349987ae3`.
- 역사적 TARGET 목록: `docs/validation/precursor-evidence-graph-20261008/results.json`의 정확한 22 IDs, 공식 검증 원출처 고유 27건(2026-10-08 당시 저장된 별도 역사적 QA 결과, 이번 원문 재다운로드 건수 아님).
- 연구 검토 등록 보고서: `docs/registrations/2026*.json` **18개** 파일 및 대상별 역사적 검토 기록 **27건**. `docs/verified-bottlenecks.json`의 2026-09-30 기존 대시보드 등급은 불변.
- HALEU 신규 원출처 검증의 고정 실증: [#43824301850](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43824301850), 발행사 원문 3건, 별도 근거 코드 8개, 엄격한 동일기간 수요·공급 쌍은 **NOT_EVALUATED**. 이전 11개 S4 CPU 전수 판독은 재실행하지 않음.

| 검토 항목 | 실제 수치 | 의미 |
|---|---:|---|
| 고정 등록 TARGET IDs | 22 | 범위 한정 전체 검토 |
| QUALIFIED | **0** | 검증된 독립 수요·적격 미예약 공급·같은 기간의 차이를 입증하지 못함 |
| REJECTED | **0** | 같은 TARGET의 명백한 반증을 제시할 독립·해시 검증 근거가 없으므로 임의 반려 없음 |
| HOLD | **22** | 재검토할 기존 후보 모두 보존 |
| 역사적 등록 파일 | 18 | 파일별 원본 SHA-256 기록 |
| 역사적 검토 기록 | 27 | 이전 상태는 새 근거 자격으로 사용하지 않음 |
| 이전 검증 원출처 총합 | 27 | 고정 QA가 기록한 전체 고유 수, TARGET별 합산 금지 |
| 운영 DB/LIVE/순위표 변경 | **0** | 연구용 별도 SQLite만 생성 |
| RSS 약 1만 건 전수 의미 분석 | **NOT_PERFORMED** | 이번 범위에 포함되지 않음 |
| 기존 공개 근거 수 511 재검증 | **NOT_REVALIDATED** | 세션 6 운영 원장 직접 대조가 필요 |

## 종료 기준과 단계 이관

사용자가 승인한 운영 방향: 한 품목에서 부족한 비공개 물량을 무기한 기다리지 않고, 기존 등록 TARGET 전부를 **적격·반려·HOLD** 중 하나로 분류하여 이력을 보존한 다음, 세션 6 DB 통합으로 진행한다.

- 분류 판단: 개별 문서에 본문/제품명이 있다거나 2026-09 기존 FUTURE·EMERGING 등급이라는 이유로 QUALIFIED 부여 금지.
- 반려 판단: 원출처가 반증을 확정하지 못하면 REJECTED가 아니라 HOLD.
- HALEU의 누적 1 MTU/2030 납기, 7 MTU 선택권, 0.5 MTU/년 현재 설비, 5.5 MTU/년 건물용량, Centrus 16 원심분리기, BWXT 작업주문 불확정은 같은 연도·같은 제품의 적격 미예약 공급량으로 합산 불가.
- 모든 22건은 기존 ID를 유지하고, source-free 연구용 `s5-to-s6-research.sqlite3`에 해시가 있는 개별 사례로 기록.
- `s5-closed-review.json` 및 `s6-research-handoff.json`으로 각 분류와 세션 6 인계 조건을 명확히 표현.
- 별도 Python 프로세스에서 SQLite·22 사례·자기 기록 SHA-256·HOLD 상태·전후 연결 해시를 실제 재조회하여 PASS.

**세션 6 즉시 우선 업무**: 현재 운영 `future-bottleneck-data` 및 `data` 브랜치의 **실제 증거 ID**·기사 ID·원문/근거 SHA·처리 상태와 연구용 22 HOLD 코호트를 대조한다. 공용 대시보드의 511 근거 건수는 최신 실 데이터에서 재산출하기 전까지 승인된 누적 건수로 취급하지 않는다. 생산 원장을 덮어쓰지 않고, 중복 재인용·같은 원천 발표를 독립 수요·공급으로 세지 않는다.

## 변경 범위

새 `tools/bct_s5_22_target_disposition.py`, `tests/test_bct_s5_22_target_disposition.py`, `.github/workflows/bct-s5-22-target-review-handoff.yml` 및 이 보고서만 추가. 이 검토는 외부 AI 모델 호출이 없으며 기존 CPU/원문/원장을 재처리하지 않는다. 기존 Objective Lock, RAW/RSS, 수집기, protected EARLY·STRICT, LIVE, 운영 대시보드, 과거 증거·승격 이력은 전부 보존.

**결론:** 등록된 22개 TARGET의 검토라는 한정 관문은 완료(PASS). 실 수급 검증률과 전체 1만+ 기사 연구 완료는 주장하지 않는다. 세션 6 연구용 이관·운영 근거 현황 대조를 다음 단계로 진행할 수 있다.
