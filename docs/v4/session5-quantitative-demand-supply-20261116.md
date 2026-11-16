# BCT V4 Session 5 — Antares / Standard Nuclear 정량 계약·생산능력 실증 (2026-11-16 KST)

## 판정

- **실제 원문 정량값 추출·원문 위치 해시·SQLite 저장·재조회: PASS**
- **공개 원문 확보:** Standard Nuclear 공식 2026 Q3 Form 10-Q 1건 PASS; Centrus Q3 원문은 자동 수집 HTTP 오류로 ACCESS_HOLD (원문 확보 1/2).
- **Standard Nuclear 원문 특정 사실:** `12/12`개 필드 원문 위치와 SHA-256 검증.
- **세션 5 적격 수급쌍 검증: PARTIAL / `NOT_EVALUATED`**. 동일 연도 고객 확정 수요와 적격·미예약·가용 공급량 부재. 병목 후보·LIVE 새 기록 0. `확정 부족 0`이 아니라 `확정 여부 UNKNOWN`.
- **목적 제한:** 기존 세션 4 완료 원본 11건, RSS 전체 기사 1만+건, 구형 CPU 원장·원격 private epoch, 기존 strict/EARLY/S 엔진·실시간 대시보드는 이번 작업에서 읽거나 수정하지 않았다.

## 실제 재현 근거

1. 고정된 8개 공개 원출처 선행 증거: [#43815790180](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43815790180), source-free artifact `14202675339` 및 SHA-256 `a5b6db4373d060f933fb77e5cbad44ba67cc065f4f1618a98622367b7484b5b4`.
2. 새 Q3 보고서 직접 HTTPS 수집, URL 및 본문 바이트 해시 검증, 수치별 문서 위치/근거 해시, 별도 SQLite 원장 저장: [#43821707141](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43821707141) **SUCCESS**.
3. 신규 저장 파일을 다른 Python 프로세스로 다시 조회: `PASS_QUANTITATIVE_SOURCE_FREE_SQLITE_READBACK` 2개 원출처 행(성공 1, 접근 보류 1), 숫자·시점·조건 12개 검증.
4. 전체 회귀시험: [#43821706981](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43821706981) **SUCCESS**.

공개 읽기 전용 원문(중요: 후속 검증은 동일 버전과 기간을 계속 유지):

- [Standard Nuclear 2026-11-12 3분기 Form 10-Q 원문](https://ir.standardnuclear.com/sec-filings/all-sec-filings/content/0001628280-26-073090/nucl-20260930.htm)
- [Centrus Energy 2026-11-04 3분기 보고서](https://investors.centrusenergy.com/news-releases/news-release-details/centrus-reports-third-quarter-2026-results) (이번 GitHub 실행에서는 자동 원문 수집 ACCESS_HOLD)
- [GAO 2026-08-20 핵연료 공급 평가](https://files.gao.gov/reports/GAO-26-107385/index.html) (이전 8개 공개 원출처의 조건·반대 근거)

## 정량 근거를 혼합하지 않는 별도 원장

| 자료 | 확인 수치 | 시간 범위·분류 | 병목 판정에 이용할 때의 제한 |
|---|---:|---|---|
| Antares–Standard 확정 계약 | **1 MTU** (1,000 kgU) | **2030-12-31까지 누적 필수 인도**, 완성 TRISO 연료 | 연도별 2027/28/29/30 확정 배송량은 공개 분배 없음 |
| Antares 고객 선택 물량 | **최대 7 MTU** | 선택권 행사 마감 2027-12-31, 선택된 물량은 빠르면 2028년 배송 | 아직 확정 계약 이행량에 포함하지 않음 |
| Standard 현재 가동 설비 `SN-0` | **0.5 MTU/년** | 2026-09-30 기준 허가·설치된 모듈의 연환산 처리능력 | Antares 전용 미예약 생산·적격 출고 가능 물량이 아님 |
| Standard 건물 규모상 수용 가능한 처리용량 | **5.5 MTU/년** | 2026-09-30 건물 용량의 최대치 | `SN-TN`·`SN-ID` 각 2.5 MTU/년은 미설치/미운영 가능한 설계상 최대. 운영 공급량으로 합산 금지 |
| Standard 제조 수율 KPI | **63.3%** | 2026-09-30 공정 수율 | 회사의 처리용량 정의에 수율이 이미 반영됨. `0.5×0.633` 재곱셈 금지 |
| Standard SN-0 현재 가동률 | **25% 초과** | 2026 Q3 공시 현재 | 가동률 비율을 고객용 미예약 공급량으로 계산 금지 |
| 새 시설 승인 목표 | **2027-02** | `SN-TN`·`SN-ID` 목표, 심사/준비 진행 중 | 규제 당국이 이미 실제 운전 허가를 승인했다고 간주 금지 |
| Standard 2027~2030 연도별 미예약 적격 공급 | **UNKNOWN** | 고객별 원자재 확보·현장 승인·계약 할당 미확보 | 연간 총량 상한 = 시장 납품 가능량 아님 |
| Centrus 16대 기존 cascade·계약 금액 | **이번 CI ACCESS_HOLD** | Centrus Q3 보고서 미수집 | 기존 보고서의 수치 언급은 독립 수급쌍의 실제 원문 증빙으로 대체하지 않음 |

계약 체결일 2026-08-26. 본문에 있는 날짜 조건은 계약 전체 납기이며 2027~2029년 확정 **연간 소비량**을 증명하지 않는다.

## `연도별 동일 물리 범위 비교` 규칙

| 연도 | Antares 확정 TRISO 물량 MTU | 해당 고객·규격·기간의 적격 미예약 TRISO 공급 MTU | 비교 가능한 수급차 |
|---|---|---|---|
| 2027 | UNKNOWN | UNKNOWN | **UNKNOWN** |
| 2028 | UNKNOWN | UNKNOWN | **UNKNOWN** |
| 2029 | UNKNOWN | UNKNOWN | **UNKNOWN** |
| 2030 | UNKNOWN | UNKNOWN | **UNKNOWN** |

공시상 누적 1 MTU 이행 기한은 2030-12-31이며, 특정 회계/배송 연도의 단위 물량은 명시되지 않았다. 가동 설비의 연환산 처리능력과 계약 전체 누적 수요량은 기간이 다르다. 단위 `MTU finished TRISO`와 `upstream enriched HALEU feedstock`도 동일한 생산 단계가 아니므로 더하지 않는다.

추가로 BWXT는 Antares 고객의 두 번째 연료 제조 계약 당사자이며, 1 MTU 초기 할당이 별도로 보도됐지만 동일 원자로 및 일련의 제품 수요 중복 여부가 미확인이다. 정부 조건부 HALEU 배정이나 GAO의 unobligated 용도 미확정 역시 수요/공급 완성 조건을 자동 충족시키지 않는다.

## 다음 우선 증빙 (이번 완료에 포함하지 않음)

1. Antares 연도별 확정 2027–2030 TRISO 연료 인수·일자·규격·제품/동위원소 농도·고객 사용 목적 등 원출처 공개.
2. BWXT, Standard Nuclear, Centrus 단계별 고객 적격 인증·미예약 물량·이미 할당된 물량·수송/허가 상태·연도별 납품 가용일 원출처.
3. 충분한 대체 공급·재고·규제 승인·고객 옵션 미행사·일정 지연이라는 **반대 근거**와 실 수요가 같은 프로젝트인지 교차 대조.
4. 신뢰할 수 있는 **서로 독립한 인과 사실**이 같은 5차원 TARGET·동일 납기·같은 단위로 연결되면 그때에만 보호된 기존 strict/graph 엔진을 별도 검증 실행. 최초 확인 시점 이전 확보 자료만 선행 신호에 포함.

## 범위 / 안전 통제

새 파일: `config/bct-s5-quantitative-originals-20261116.json`, `tools/bct_s5_quantitative_capacity_audit.py`, `tests/test_bct_s5_quantitative_capacity_audit.py`, `.github/workflows/bct-s5-quantitative-capacity-audit.yml`, 이 보고서. 변경은 코드·검증 규칙·source-free 연구 파일뿐이다.

외부 유료 AI/API, 새 모델 추론, 민감한 내부 원문 검색어 외부 전송, 자동 투자 점수, 신호 후보 승격, 기존 RSS 데이터·private epoch·protected strict 엔진·운영 대시보드 변경 **없음**. 새 데이터셋은 원문 전체를 공개 저장하지 않고 수치와 source locator/해시만 저장한다.

**최종 상태: `PASS_SOURCE_BOUND_QUANTITATIVE_EXTRACTION / PARTIAL_S5_SAME_PERIOD_DEMAND_SUPPLY_COMPARISON`.** 이 기술적 PASS를 시장 병목 발견이나 최종 세션 5 PASS로 표현하지 않는다.
