# BCT V4 Session 5 — Centrus·BWXT 독립 원출처 공급 제약 검증 (2026-11-16 KST)

## 판정

**공식 원출처 접근 복구 및 공급 제약 사실 검증: PASS.** **세션 5 전체 수급쌍 검증: PARTIAL.**

2026-11-16 실제 작업 결과: 고정 공식 URL 4개 시도, **원문 3건 확보**, 1건 접근 보류(SEC HTML HTTP 403). 원문 3건 중 Centrus의 HTML과 동일 공시 8-K PDF **2건**은 같은 발행자/동일 2026 Q3 사건에 해당하며, BWXT 공식 원출처가 **독립 계약 사건 1건**이다. 서로 다른 문서 3개가 서로 다른 경제적 수급 사건 3개를 의미하지 않는다.

원문 위치와 SHA에 결박된 **서로 다른 근거 코드 8개**, 별도 source-free SQLite 저장 및 새 프로세스 재조회 **PASS**. 이전 Standard Nuclear 10-Q의 확정 계약 총 1 MTU, 0.5 MTU/y 현재 가동 throughput, 5.5 MTU/y 건물 상한은 별개 기존 원장으로 보존한다.

[실제 검증 실행 #43824301850](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43824301850)  
아티팩트: `bct-s5-supplier-fact-source-free-43824301850`, ID `14205666980`, ZIP digest `sha256:f077f746cb06ce5de6efe59b77882a6136b00c77d6b9cc9e3d697c35624110a7`.

## 원출처 4개 접속 결과

| ID | 공식 원출처 | 직접 실행 상태 |
|---|---|---|
| `centrus_sec_q3_ex99` | [SEC Exhibit 99.1, 2026-11-04](https://www.sec.gov/Archives/edgar/data/1065059/000162828026070229/ex991-10q2026_11x04.htm) | **ACCESS_HOLD HTTP 403** |
| `centrus_issuer_q3` | [Centrus 발행사 2026 Q3 발표](https://centrusenergy.gcs-web.com/news-releases/news-release-details/centrus-reports-third-quarter-2026-results) | **PASS**: 원문·발행자·날짜·근거 5개 |
| `centrus_official_8k_pdf` | [Centrus 발행사 원본 8-K PDF](https://centrusenergy.gcs-web.com/static-files/cc3fa381-12cb-4630-a441-6b2667774398) | **PASS**: 원문·발행자·날짜·동일 근거 5개 |
| `bwxt_antares_issuer` | [BWXT 2026-10-27 Antares 계약 원문](https://www.bwxt.com/bwxt-announces-contract-with-antares-for-triso-nuclear-fuel-production/) | **PASS**: 원문·발행자·날짜·근거 3개 |

여기서 `PASS`는 두 종류의 실물 공개 원문에서 확인한 **제한적 발행자/제목/날짜/근거 단편의 검증**이다. 출처 해시·위치·본문이 남아 있지만, 이를 자동으로 protected strict 원본 provenance 검증 및 수급쌍 자격에 전환하지 않는다.

## 이번에 별도 원문에서 확인한 사실과 한계

| 사실 코드 | 확보 내용 | 적격 수급쌍 계산에서의 주의 |
|---|---|---|
| `CENTRUS_EXISTING_CASCADE_16` | 기존 **16대** 원심분리기 cascade로 HALEU 상업 생산 | 설비 대수는 **kgU/년** 생산량이 아니다 |
| `CENTRUS_CONTINGENT_LEU_HALEU_BACKLOG_5_4` | 약 **54억 달러**의 LEU·HALEU 조건부 enrichment 수주잔고 | HALEU만의 확정 물리 공급량이 아니다 |
| `CENTRUS_FY27_DOE_OPERATION_FUNDING_ABSENT` | 2027년 DOE 제출 예산안에 기존 cascade 운영 **추가 지원 미포함** | 제안 예산 위험이지만 2027년 실제 운영 중단이나 공급량 0을 뜻하지 않음 |
| `CENTRUS_DOE_NO_FURTHER_OPTIONS_INTENT` | DOE가 해당 운영계약에 대해 현재 추가 옵션 행사 의사 없음 통보 | 계약 자동 취소 또는 전체 HALEU 공급 중단으로 볼 수 없음 |
| `CENTRUS_NEW_CENTRIFUGE_SHIPMENT` | 원심분리기 제조 완료·배송 착수 | 실제 설치·준공·수율·적격·미예약 고객 납품 물량을 증명하지 않음 |
| `BWXT_ANTARES_INITIAL_ALLOCATION_1_MTU` | Antares 신규 연료 제조계약 **초기 할당 1 MTU** | 2027년 연간 확정 고객 인수량이 아님 |
| `BWXT_ANTARES_FUTURE_TASK_ORDERS` | 미래 작업주문에서 특정 물량·납기·기술요건 확정 예정 | 아직 개별 확정 작업주문 조건 미확보 |
| `BWXT_EXISTING_FABRICATION_LINE` | BWXT Lynchburg 기존 TRISO 제조 라인 활용 | 전체 적격 생산량과 타 고객 예약 후 잔여량 미확보 |

추가 공개 자료: [BWXT IR의 2026 Q1 공식 전사본](https://investors.bwxt.com/static-files/8572b08b-b0b2-499e-aee4-fc45e07c8409)에서 경영진은 과거 TRISO 제조 능력을 ‘연 수백 kg’ 수준으로 설명했다. 이는 과거 시점·근사치이며, 2026 Q3 실제 고객별 미예약 적격 물량이 아니므로 **이번 실제 자동 추출 근거·공급액으로 승격하지 않았다**. 동일 회사의 2026 Q3 제3자 전사본에는 최소 네 배로 규모 확대가 가능하다는 미래 주장도 있으나, 설치·허가·가용 물량 확인 없이 확정 공급으로 가산하지 않는다.

## 실제 수급 비교 상태

| 연도 | Antares 확정 TRISO 인수량 (MTU) | Antares 규격 적격·미예약 TRISO 가용 공급 (MTU) | 물리량 수급차 |
|---|---|---|---|
| 2027 | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |
| 2028 | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |
| 2029 | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |
| 2030 | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |

Antares–Standard의 누적 1 MTU(2030-12-31까지)와 별도 7 MTU 옵션, Antares–BWXT 초기 1 MTU 협상 프레임워크는 **확정 연도별 연료 인수량으로 분할할 수 없다**. Centrus의 농축 장치 대수와 조달 잔고도 연도별 실물 가용 TRISO 물량으로 변환하지 않는다.

**판정:** 실제로 입증한 적격 독립 수요·공급쌍 **`NOT_EVALUATED`**, 자동 신규 후보 0, 외부 AI API 0, LIVE 등록 0, private epoch 변경 0. ‘0쌍 확정’이나 ‘해당 시장에 병목이 없음’으로 해석하면 안 된다.

## 다음 판독·취득 우선순위

1. Antares-BWXT **서명된 향후 작업주문** 또는 해당 연도별 납품표·기술규격·확정 수량. 현재 1 MTU는 초기 할당이라는 사실과 구분.
2. Antares-Standard 확정 1 MTU의 연도별 출고·인수 일정 및 선택 물량의 행사 여부. 미행사 옵션은 수요로 승격 금지.
3. BWXT/Standard에서 고객별 적격 제조능력 중 **타 고객에게 예약되지 않은 검증된 실제 가용 생산량**, 재고·물량·수율·설비승인 등.
4. Centrus 제품 형태·농축도·의무 없는 연료 feed의 출고 시점 및 제조사에 도달하는 물량, 정부/민간 할당 중복 제거.
5. 동기간 같은 고객·규격·제품·지역 원출처만 묶고 충분한 공급·대체제·계약 취소·일정지연의 **반대 증거** 검증. 그 후 기존 보호된 strict 엔진의 별도 검증 실행.

## 코드·권한 경계

새로운 고정 원출처 manifest `config/bct-s5-supplier-official-followon-20261116.json`, 정량 근거 해시 audit `tools/bct_s5_supplier_fact_followon.py`, 적대적 시험 `tests/test_bct_s5_supplier_fact_followon.py`, 제한된 GitHub Actions `.github/workflows/bct-s5-supplier-official-followon.yml` 및 본 문서를 추가한다.

기존 main의 RSS·source queue·원래 S4 11건, 8개 public source cohort, 2개의 Q3 수치 검증, private research, Objective Lock, protected EARLY/STRICT 판단 기준, 운영 대시보드 **변경 없음**. 원문 전체를 공용 아티팩트로 저장하지 않으며 원출처 공개 URL·해시·위치·코드만 source-free 저장한다.

**완료 가능한 이번 기술 관문:** source verification / dedup / fresh readback PASS. **전체 세션 5:** PARTIAL (같은 연도·같은 물리 범위 적격 수요·공급 자료 부족).
