# BCT V4 — 세션 6 교차 수요·공급 원문 검증 및 인계

- 검증일: 2026-11-13 (KST)
- 기준: 세션 5의 302건 중 본문 및 언론사 출처가 검증된 45건 전체
- 기존 엄격한 precursor_evidence_graph를 수정 없이 BACKFILL(과거 자료 재검토)로 실행
- 기존 main, data, future-bottleneck-data, LIVE 후보, S1·S2·S3 판정은 수정하지 않음

## 실제 검증된 데이터

| 항목 | 건수 |
|---|---:|
| 최초 검증 대상 | 45 |
| 기존 본문 SHA-256과 동일하며 언론 원본도 다시 확인 | 35 |
| 게시 후 본문 버전 변경 | 9 |
| FULL 본문 재확보 불가 | 1 |
| 35개 기사에서 기존 그래프의 문장 관측 | 1,502 |
| 기존 그래프의 원문 참조 위치 검증 | 2,248 |
| 문장별 DEMAND 단서 | 43 |
| 문장별 SUPPLY 단서 | 51 |
| 완전한 동일 제품/규격/고객/지역/공급주체 연결 사건 | **0** |
| 적격 공급생산능력 확인 사건 | **0** |
| 독립적으로 비교 가능한 수요·공급쌍 | **0** |
| 확인 가능한 신규 미래 병목 | **0** |

주요 누락 사유: 사건 단위 제품 연결 미확정 78건, 규격 미확정 16건. 사건별 결손은 기사 수가 아니며 중복될 수 있다. 단일 그래프 연결선 1개는 독립 수요·공급 검증쌍 1개가 아니다.

전체 45개 재접속 실증: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43344245036

## 독립 공식 원본에 대한 휴리스틱 오판 발견

기존 source_search.primary_origin 로직은 언론사 자기 이름이 포함된 다음 기사 4건을 직접 발주처/공급업체 같은 1차 원본으로 잘못 취급할 가능성이 있다.

- The Loadstar — 스페인 항만 컨테이너 적체
- POWER Magazine — DOE/Constellation 원전 출력 증대
- Defense News — 장갑차/군장비 운송
- POWER Magazine — AI 자산관리

언론사의 작성자/발행사 식별은 해당 제품 제조사나 고객의 원본 증명이 아니다. **기존 휴리스틱 양성 4건은 1차 적격 공급 증거로 인정하지 않음.** 35개 검증 언론 원문으로부터 별도로 확정한 발주처·적격 공급업체의 원본은 0건(아직 미검증)이다.

기존 45개 URL을 다시 방문하지 않고 최초 성공 실행의 메타데이터만 정정:
https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43345038261

- 11개 언론사 출처, 동일 해시 35, 변경 9, 재확보 실패 1 보존
- 신문기사와 기업/기관 공식 발표의 증거 등급은 구별
- 새 HTTP 요청 0, AI API 0, S1/2/3 승격 0
- 정정된 기사별 근거상태표는 session6_evidence_45_corrected.csv

## 추가 발견한 직접 원문 후속 검증 링크 (45개 연구표본과 별개)

1. 미 DOE (2026-10-27): Constellation의 조건부 최대 50억 달러 자금지원·원전 약 1.1GW 출력 증대
   https://www.energy.gov/articles/energy-department-announces-5-billion-loan-boost-nuclear-power-and-help-lower-costs
2. Constellation(2026-10-27): 동일 DOE 대출·원전 출력증대 발표
   https://www.constellationenergy.com/news/2026/10/constellation-secures-conditional-doe-loan-commitment-of-up-to-5-billion-to-expand-nuclear-output.html
3. Curtiss-Wright(2026-10-29): Round Rock 3,000만 달러 투자, 압력·온도센서 제조 확장
   https://curtisswright.com/news/press-releases/news-release-details/2026/Curtiss-Wright-Announces-30-Million-Capital-Investment-to-Expand-Its-Operations-in-Round-Rock-Texas
4. 미국 LA항 공식 화물·철도 적체 운영 대시보드
   https://portoflosangeles.org/business/operations

이 주소는 공식 원문 후보이며 현재 연구 DB에 수요·공급 검증쌍으로 추가하지 않았다. DOE와 Constellation은 같은 대출 사건의 양측 발표이므로 독립된 수요/공급 사건 두 개로 세면 안 된다. Curtiss-Wright의 센서 생산능력은 Constellation의 발전량 GW와 동일 제품·규격/수량 단위가 아니며, LA항의 적체 통계는 미래 12~36개월 선행 부족의 증명이 아니다.

## 보존된 실행과 검증

- 연구 엔진: tools/bct_session6_cross_evidence.py
- 정정 분석기: tools/bct_session6_source_role_correction.py
- 단위/오탐 차단: tests/test_bct_session6_cross_evidence.py + tests/test_bct_session6_source_role_correction.py
- 실제 원문/그래프 시험 성공: 43344245036
- 신문/발주처 분리 교차감사 성공: 43345038261
- 기존 기능 회귀 테스트 성공: 43344244926 / 43345038179
- 제3자 기사 전문/원본 HTML/사용자 인증정보/유료 AI API 저장 없음
- 연구 브랜치에서만 추가; 운영 main과 배포 승인 기록은 이 작업으로 변경하지 않음

## 다음 단계: 세션 7 — 전체 기사 자동화

고정 목표는 12~36개월 미래 병목의 선행 발견이며 수집 기사 건수를 증거로 승격하면 안 된다.

- 10,510건 고정 DB의 전수 메타데이터 대기열을 신규 기사 및 과거 적체와 분리
- 원문 수집→해시/발행시점 검증→원본 발주처/적격 공급사 직접 발표→동일 제품/규격/수량/필요기간 교차 확인→반대 증거 검토
- 언론 보도는 검증해야 할 원본 링크를 찾기 위한 참고자료로 유지
- 원문 변경은 새 버전으로 관리, 기존 판단/출처 해시 삭제 금지
- 검증된 수요·공급쌍만 병목 후보로 올리고, 누락은 UNKNOWN으로 보존
- 자동화 고장/마지막 성공 업데이트/대기량을 대시보드에 별도 표시
- 원문 확보 미완료 5,869건과 연구용 45건을 전체 수집 성공률로 혼동하지 않음

**세션 6 최종 판정: 교차검증 작업 PASS, 확인된 적격 미래 병목 0건, 전체 산업에 병목이 없다는 증거는 아님.**
