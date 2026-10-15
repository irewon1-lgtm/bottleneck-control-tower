# BCT V4 Q1 — 공통 정량 수급자료 연결·실제 값 검증 지침

계획 ID: BCT-V4-Q-1.0
고정 상위 하위계획: docs/v4/quantitative/FIXED_SEQUENCE.md
현재 단계: Q1 / 작업 전 NOT_RUN
담당: 기존 BCT Codex 작업
저장소: irewon1-lgtm/bottleneck-control-tower
브랜치: codex/bct-v4-integration
참고 인계 SHA: 155063676782ebb10a590d489899c281b922da8f

이 지침을 받은 뒤 실제 최신 상태에서 Q1을 실행한다. 여기서 Q1은 기존 과거 Stage 1 재실행이 아니라 새 정량 수급 강화 하위 작업이다. UI·수집·CPU·비공개 연구 상태를 새로 만들지 않는다.

## 1. 이번 종료 목표

뉴스 주소를 늘리는 것이 아니라, 공식 수요/공급 수치를 실제 받아 기존 연구 데이터 경로에 보존하고 값·단위·기간·출처·수정 이력을 검증한다.

8개 출처군 각각에 등록/접근/실제 수집/파싱/단위·기간 확인/연구 저장/새 프로세스 재조회/변경 비교/재시작의 증거를 남긴다. 등록한 연결 수와 물리량 확보 수는 별개다. Q1에서는 새 S3·예측 성능·AI 품질 PASS를 만들지 않는다.

## 2. 시작 조건과 기존 작업 보존

실제 HEAD, 원격 branch, 미커밋 변경, 연구 DB·데이터 분리 스키마, 기존 연결기와 캐시를 확인한다. 참고 SHA로 reset하지 않는다. BCT_OBJECTIVE_LOCK.md, 기존 EXECUTION_PLAN.md/PROGRESS.json, quantitative/FIXED_SEQUENCE.md를 읽고 기존 결과를 재사용한다.

정상 토큰·Secret·CPU 모델·캐시·완료 1,277창을 다시 준비하거나 시험하지 않는다. UI 정적 파일, main/data/live-state, 기존 RSS/CPU 예약 상태·권한·단계 판정은 변경하지 않는다. 병행 작업과 저장 충돌을 확인한다. 문서 커밋을 BCT_V4_CPU_CODE_SHA로 덮어쓰지 않는다.

진행 정보는 기존 PROGRESS.json의 quantitative_plan 하위에 기록한다. 기존 모든 키와 과거 상태를 보존하고 기존 계획 hash 관리 규칙을 따른다. 이 지침의 처음 실행에서 Q1=IN_PROGRESS로 기록한다. 다른 진행 JSON을 새로 만들지 않는다.

## 3. 실제 연결할 8개 출처군

아래 URL은 공식 문서/목록 또는 API 기점이다. 파일명·필드·enum은 현재 공식 스키마를 읽고 확정하며 없는 endpoint를 추측하지 않는다. 이번 Q1은 아래 8개까지만이며, 부족한 세부 공급능력의 기업별 조사 확대는 Q2로 넘긴다.

### 3-1. SEC EDGAR — 전 산업 기업 공시

공식 문서: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
접근 규칙: https://www.sec.gov/about/developer-resources
공통 제출 이력: https://data.sec.gov/submissions/CIK{10자리CIK}.json
전체 초기 색인: https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip
공시 아카이브: https://www.sec.gov/Archives/edgar/data/

기존 SEC transport/parser를 재사용한다. 공통 색인으로 기업들을 발견하고 신규 accession과 수정 공시만 본문/첨부 큐에 넣는다. 기본 범위 10-K/10-Q/8-K/20-F/6-K 및 수정본을 구분한다. 새 회사가 기존 목록 밖이어도 배제하지 않는다. 전체 ZIP은 필요한 최초 동기화에만 검토하고 매 회차 companyfacts/submissions 대형 ZIP 전체를 재다운로드하지 않는다.

CIK, accession, form, acceptance/publication time, 문서/첨부 경로를 저장한다. Company Facts는 비기업고유 표준 태그의 재무 보조 자료로만 사용한다. 생산능력/주문량/납기는 공시 본문과 표/첨부의 정확 위치까지 확보해야 하며 미검증 자동 추출은 제안 상태다. 달러 backlog·CAPEX와 제품 수량을 별도 필드에 저장한다.

기존 BCT_SEC_USER_AGENT에 실제 승인 연락처가 있는지 확인한다. 없으면 SETUP_REQUIRED로 기록하고 임의 이메일을 만들지 않는다. 전체 프로세스의 SEC 요청량을 합산하여 공식 fair access 상한을 지키며, 기존 더 엄격한 한도를 유지한다.

### 3-2. Census M3 — 제조업 주문·출하·재고

목록: https://api.census.gov/data/timeseries/eits/m3.html
API: https://api.census.gov/data/timeseries/eits/m3
공식 다운로드/과거 데이터: https://www.census.gov/manufacturing/m3/historical_data/index.html
발표: https://www.census.gov/manufacturing/m3/current/index.html

변수/업종 분류 목록을 먼저 저장한다. 신규 주문·미이행 주문·출하·재고, 업종 분류, 월, 계절조정 여부, 단위/배율, 수정 여부를 수집한다. 달러 금액을 제품 개수로 변환하지 않는다. 월별 흐름과 월말 잔액을 구분한다.

Census API는 키가 필요하다. 기존 키가 없으면 공식 다운로드 파일에서 동일 의미의 자료를 확보할 수 있는지 확인한다. 파일 대안의 실제 범위가 다르면 대등한 전체 대체라고 하지 않는다. 접근 제한 우회나 비공식 미러로 바꾸지 않는다.

### 3-3. Federal Reserve G.17 — 생산지수·생산능력·가동률

공식 다운로드: https://www.federalreserve.gov/releases/g17/download.htm

페이지에 연결된 Tables 1/2/10(생산), Tables 7/8(능력/가동률), 해당되는 Table 3(자동차 조립) 파일과 코드 설명을 따른다. 텍스트/CSV/XML/공식 파일로 수집하고 DDP 화면 자동조작에 의존하지 않는다. DDP 변경 공지가 있으므로 현재 안정된 기계판독 파일과 공식 대체 경로를 registry에 기록한다.

시리즈 코드·산업 코드·기준연도·지수/퍼센트/물량·계절조정·월·발표 버전·수정 여부를 보존한다. FRED에서 같은 자료를 받아도 원출처는 Fed 하나로 계보를 묶는다. 산업 생산지수와 가동률을 개별 부품의 적격 공급량으로 채택하지 않는다.

### 3-4. USAspending — 계약과 변경 거래

문서: https://api.usaspending.gov/docs/endpoints
검색: POST https://api.usaspending.gov/api/v2/search/spending_by_award/
거래: POST https://api.usaspending.gov/api/v2/transactions/

기존 USAspending transport/parser를 재사용한다. 계약 A-D 범위를 기본으로 하고 grants/loans/보조금은 다른 종류로 구분한다. NAICS/PSC·기관·기간의 고정 조회 조건과 페이지를 관리한다. 실제 지원 필터/응답 필드는 공식 계약을 확인한 뒤 사용한다.

award/transaction ID, 발주기관, 수령자 식별자, 설명, 계약 종류, 금액 종류(총액/당기 의무액/수정 증감), action date, 계약기간, 수정번호를 저장한다. 최신 action date만으로 과거 계약 수정 탐지의 완전성을 주장하지 않는다. 지원되는 수정일/증분자료를 사용하고, 없으면 겹치는 재조회 구간과 이전 응답 hash 대조 범위를 명시한다.

계약 총액과 각 거래 증액을 중복 합산하지 않는다. 계약 종료일을 납품일로 단정하지 않는다. 물량/규격이 계약 원문에 없으면 UNKNOWN이다. 숫자 금액 확보만으로 적격 공급/수요량이 확보됐다고 하지 않는다.

### 3-5. Census 품목별 무역 — 물리 수량·국가·품목

수입 API: https://api.census.gov/data/timeseries/intltrade/imports/hs
수입 필드: https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.html
수출 API: https://api.census.gov/data/timeseries/intltrade/exports/hs

공식 HS 품목표와 단위 정의로 범위를 고정한다. 텅스텐·흑연·리튬·희토류 등 초기 물질/공정별 매핑을 검증하며 실제 HS 코드는 추측하지 않는다. 품목 설정은 확대 가능하며 미국 무역이 세계 전체 생산을 대체하지 못함을 표시한다.

월별 GEN_QY1_MO/CON_QY1_MO와 수량단위, 가치, 국가, 품목 수준, 실제 0/누락 플래그를 공식 스키마에 따라 저장한다. 사용 endpoint의 실제 변수명만 쓴다. 운송중량과 함유 금속량·제품중량은 다르다. 일반수입/소비용수입을 섞지 않고 상위 총계와 하위품목·국가 합산을 중복하지 않는다. 연도별 HS 개정/단위 변경 시 비교를 격리한다. Census 키는 M3와 재사용하며 값을 로그에 남기지 않는다.

### 3-6. EIA — 발전설비·발전/판매량·연료·재고

API 문서: https://www.eia.gov/opendata/documentation.php
API 기점: https://api.eia.gov/v2/
설비 월별 XLSX: https://www.eia.gov/electricity/data/eia860m/index.php

기존 EIA860M snapshot/compare를 재사용한다. API는 부모 metadata에서 실제 route/facet/단위를 발견하고 /data, 기간, 정렬, offset/length로 전 페이지를 회수한다. 기존 EIA 키가 없으면 860M 등 공식 파일 경로를 먼저 실행하고 API 부분만 SETUP_REQUIRED로 기록한다.

860M은 Plant ID+Generator ID, 상태, 명목/계절 능력, 가동/퇴역/취소·예정일을 실제 열 정의와 연결한다. 발전/전력판매/연료 생산·재고는 각 시리즈의 단위를 보존한다. MW와 MWh, 배터리 MW와 MWh, 명목능력과 적격 확약을 섞지 않는다. 예비추정/수정치를 사건과 구분한다. EIA API는 페이지 제한 및 숫자 문자열 반환을 처리하고 응답의 request echo에 포함될 수 있는 API 키를 저장·로그에서 제거한다. 키 제거 전 원응답이 필요한 무결성 검증은 메모리/허용된 비공개 처리로 구분하며 공개에 저장하지 않는다.

### 3-7. USGS — 광물 생산·무역·소비·재고

상품 목록: https://www.usgs.gov/centers/national-minerals-information-center/commodity-statistics-and-information
텅스텐 목록: https://www.usgs.gov/centers/national-minerals-information-center/tungsten-statistics-and-information

공식 품목 페이지가 연결한 Mineral Industry Surveys와 Mineral Commodity Summaries의 XLSX/구조화 자료를 사용한다. 초기 텅스텐·리튬·흑연·희토류는 실제 제공 빈도에 맞춰 처리한다. 모든 품목이 월별 수치나 모든 수급 항목을 공개한다고 가정하지 않는다. JS/접근 차단이면 공식 다운로드/공식 카탈로그의 동일 자료 경로를 확인하고 차단을 우회하지 않는다.

품목/생산단계/국가/연도·월/단위/생산·소비·수입·수출·재고/추정·잠정·비공개 플래그를 저장한다. 광석 총톤, 금속 함유톤, 산화물 환산톤, 완제품톤을 구분한다. D/W/e 등의 코드를 임의로 0으로 바꾸지 않는다. 근거가 Census 등 다른 원천인 수치는 source lineage를 연결해 독립쌍으로 중복 계산하지 않는다.

### 3-8. EU TED — 유럽 공공조달

문서: https://docs.ted.europa.eu/api/latest/search.html
검색: POST https://api.ted.europa.eu/v3/notices/search

공식 Swagger에서 필드·쿼리 문법·페이지 방식을 확인한다. 인증 없는 공개 검색과 공고 XML을 활용한다. CPV/NUTS·공고 ID·절차/lot ID·공개일·변경/취소·계약/낙찰 상태·수량/단위/금액/기간을 확보한다.

예정 공고·입찰·낙찰·계약 변경을 같은 주문으로 세지 않는다. 최대 framework 금액과 실제 발주액, 옵션과 확정 계약을 구분한다. 수량/납기 정보가 없는 공고를 물리 수요로 환산하지 않는다.

## 4. 수집 범위와 규모를 고정하는 방법

Q1 첫 실행에서 8개 출처의 manifest를 먼저 고정한다. 이것은 산업별 순차 승인 과정이 아니다. 출처별 key, URL, 방식, 실제 필드, 단위 종류, 범위, 갱신 주기, 인증 필요 여부, 이용/보관 정책, 현재 상태, 다음 cursor를 갖는다.

초기 기본 범위는 월간 계열 최근 36개 발표대상월, 주간 계열 최근 52주, 연간 계열 최근 3개 공개연도, 설비목록 최신 2개 공개판, 공시/계약/공고 최근 30일과 그 범위의 수정 이력이다. 이미 보유한 같은 버전은 재사용한다. 세부 분류 범위와 큰 파일/페이지 수는 실행 전에 manifest에 고정하고 비용·기존 저장 상한 안에서 처리한다. 이 범위는 최초 연결 검증용이며 전 세계 전체 자료 완전 수집 주장이 아니다.

원래 제한 내에서 소량 왕복을 확인한 뒤 같은 고정 범위의 미처리 페이지를 체크포인트로 계속 처리한다. 출처당 첫 페이지·수치 1개만 읽고 끝내지 않는다. 시간/자원 제한에 걸리면 실제 완료·잔여·resume cursor를 저장한다. 임의로 범위를 축소해 완료 숫자를 맞추지 않는다.

새 회사·품목·자료는 별도 다음 배치에 보존한다. 최초 작업 중 새로운 범위를 무한히 늘려 끝나지 않게 하지 않는다. 후속 정기 처리는 Q5에서 발표 주기 기반으로 통합하되, 기존 수집이 정상적으로 돌아가는 것은 중단하지 않는다.

## 5. 공통 숫자 레코드

기존 Ledger/공통 관찰 이벤트를 우선 재사용하고 제2의 무관한 DB를 만들지 않는다. 최소 다음 정보가 필요하다.

source_id / source_document_id / source_lineage_id / source_url
raw_or_safe_payload_hash / original_version / parser_version / source_locator
entity_or_facility_id / product_or_classification / sector_hint / geography
metric / value_original / value_decimal_or_null / unit_original / unit_normalized / scale
measurement_type(물리량·금액·지수·비율) / stock_or_flow / adjustment
period_start / period_end / published_at / acquired_at / revised_at / vintage
status(실적·확정계약·계획·전망·추정·비공개·누락) / coverage_scope
rights_scope / original_available_for_replay / quality_state / unknown_reason

순수 통계의 관측월만 있고 필요시점/가동시점이 없으면 만들어 넣지 않는다. 기업/제품 미확인 자료도 산업 통계로 보존한다. 단계별 판단은 별도이며 숫자 추출과 S1/S3를 같은 레코드 상태로 취급하지 않는다.

source_locator는 JSON row/path, CSV 행+필드, XLSX sheet/cell, 공시 table/문단을 실제 원본 버전에 연결한다. PDF만 있으면 표 텍스트와 렌더링 대조를 하며 확인하지 못한 값은 보류한다. OCR은 필요한 경우만 쓰고 자동 정답으로 세지 않는다.

## 6. 반드시 처리할 오류·개정·보관

숫자 문자열·천/백만 배율·음수·대시·N/A·D/W/e·진짜 0·소수점·각주·숨김표·단위 열을 처리한다. 모르는 값은 0이 아니라 UNKNOWN으로 남긴다. API200이어도 오류 본문/로그인/빈 결과면 정상 수치 확보가 아니다.

관측값 변화, 과거 수치 개정, 행 추가/삭제, 단위 변경, 공시 정정은 별도 변경 유형이다. 두 관측월의 차이는 실제 원본 두 개의 발행 버전 비교와 다를 수 있다. 최신 개정 파일의 과거 값은 과거 선행시험에 바로 쓸 수 없다. 최초 공개일/원본 버전이 확보되지 않은 자료는 BACKTEST_UNAVAILABLE로 남긴다.

공통 큐에서 기존 안전한 병렬도를 재사용하되 호스트별 요청 제한은 따로 지킨다. 401/403은 설정 변화 없이 반복 금지. 429는 Retry-After 및 기존 예산/재시도 정책 범위에서 큐에 보존하며 회피하지 않는다. 반복적으로 실패하는 자료를 완료/성공으로 옮기지 않는다. 다른 출처는 계속 처리한다.

허용된 공식 구조화 수치와 자체 연구 상태는 기존 비공개 저장 경로를 재사용한다. 보관 불명 기사 본문·인용을 함께 업로드하지 않는다. 새 원문 보관이 기존 source-separated 스키마와 충돌하면 기존 원본을 삭제하거나 차단을 풀지 말고 허용된 관측 레코드/파일 보관을 구분한다. 재조회 가능한 원본이 없으면 전체 근거 복원이라고 표시하지 않는다. 기존16MiB 체크포인트/64MiB 이력/8GiB 캐시 등 적용 상한은 임의 상향하지 않는다. 예상 초과 시 범위와 초과 원인을 기록하고 체크포인트에서 중단한다.

## 7. 품질·실행 시험과 완료 판정

각 출처에서 실제 자료 → 파서 → 단위/기간 검증 → 기존 연구 저장 → 새 프로세스 재조회 → 백업/복원까지 실행한다. 기존 설정 인증을 다시 전부 시험할 필요는 없지만 이번 쓰기의 실제 성공과 해시는 확인한다.

회귀 검증: 같은 입력 no-op, 새 관측월 append, 같은 기간 개정 보존, 페이지 누락 탐지, 크래시 후 미완료만 재개, 저장 충돌/CAS 후 복구, 단위/코드 개정 격리, 비밀값 비노출, 원문 보류를 시험한다. 개정자료가 실제 두 판 없으면 합성 개정 시험으로 구분하고 실자료 개정 검증은 미완료로 둔다.

실제 수치 검증은 source의 가능한 행수/합계와 대조하고, 서로 다른 metric/unit/status가 포함되도록 고정한 검토 표본에서 원문 값을 직접 대조한다. 그 표본의 값·단위·배율·기간·부호·근거 위치 오류는 0건이어야 한다. 모르는 값의 정당한 보류는 오류가 아니지만 모두 보류한 출처를 성공으로 세지 않는다. 실제 물리량 계열을 가진 출처에서 물리량 레코드가 확보되지 않았다면 그 공백을 숨기지 않는다. 단위시험 PASS는 전 자료 정확도 100%가 아니다.

출처별 결과를 아래와 같이 분리한다.
- COMPLETE: 고정 범위 실제 수집·파싱·저장·검증·재개 모두 통과, 미처리 페이지 없음.
- PARTIAL: 실제 확보는 있으나 잔여 범위/검증/개정자료 공백 존재.
- SETUP_REQUIRED/BLOCKED: 키·연락처·접근·권리·스키마 문제로 필요한 처리가 불가.
- NOT_RUN: 아직 실행하지 않음.

8개 모두 필요한 범위가 COMPLETE일 때만 Q1 전체 완료다. 일부가 막혀도 준비된 출처의 Q2 작업은 진행할 수 있지만 Q1 전체 PASS로 바꾸지 않는다. 예상 물량을 얻을 수 없는 금액/지수 출처를 물리량 성공으로 계산하지 않는다. 새 병목 후보 0건은 Q1 실패 조건이 아니다.

기존 UI는 디자인/메뉴를 바꾸지 않고 기존 조회/API의 호환성만 확인한다. Q1 수치 표시는 기존 전달 형식으로 검증용 내보내기를 준비한다. 새 화면 기능/정식 배포는 Q5까지 미룬다.

## 8. 금지사항·실행 권한

이번 실행은 Q1의 개발 브랜치 최소 구현·실제 무료 자료 수집·관련 시험·허용된 비공개 연구 저장·commit/push까지다. 유료 API·새 모델·GPU·추가 인스턴스·외부 AI 호출·운영 DB 변환·main 병합·예약 활성화·후보 승격·알림 발송은 하지 않는다.

Census/EIA 키와 SEC 연락처는 기존 설정부터 확인한다. 신규 필수 설정이 정말 없으면 기관·항목명·용도·영향 범위를 최종 보고 한 곳에 모으고 나머지 작업은 계속한다. 토큰·64자 암호 재설정을 다시 요구하지 않는다. 사용자가 승인하지 않은 비용은 발생시키지 않는다.

본문 의미 판독이 미완료인 자료는 정량 제안/관측과 검증 완료 사실을 분리한다. 기존 AI FAIL·독립평가 BLOCKED·과거 선행성 미입증은 그대로 유지한다. 기준을 낮추거나 수동 정답을 자동 엔진 출력으로 넣어 성공처럼 보이지 않는다.

## 9. 산출물·최종 보고·재개

docs/v4/quantitative 아래에 source-registry.json, coverage/quality 증거, Q1_RESULTS.md를 둘 수 있다. 이는 증거이지 별도 진행 원장이 아니다. 실제 raw/DB는 기존 승인 저장 위치에만 둔다. PROGRESS.json.quantitative_plan에 단계와 결과 파일 위치·커서·남은 의존성을 기록한다.

최종 보고는 쉬운 한국어로 다음 항목만 제시한다.
1) 8개 출처별 COMPLETE/PARTIAL/SETUP_REQUIRED/BLOCKED와 실제 조회 범위.
2) 숫자 관측 수·물리량 수·금액 수·지수/비율 수·기간/출처 확인 수. API 응답/문서/행/독립 사건 수를 섞지 않음.
3) 실제 확보한 대표 수치와 단위/기간/원문 위치. 가상 수치 사용 금지.
4) 개정·단위·중복·범위 누락·재시작·비공개 저장/복원 시험 결과.
5) 키/연락처/권리/접근 등 남은 공백과 미시도 잔여.
6) 신규 네트워크/API·외부 AI 호출·실행시간/저장량·실측 또는 미확인 비용.
7) 변경 파일·최종 원격 SHA·그 SHA CI의 실제 실행범위. 실행 안 한230원문 QA는 PASS 금지.
8) 다음 Q2로 넘길 실제 준비 자료와 아직 의존하면 안 되는 출처.

계획 제안만 다시 쓰고 종료하지 않는다. 허용 범위 안에서는 작은 배치마다 영속 저장하고 계속 실행한다. 실패가 있으면 해당 출처를 분리하고 완료된 수집/판독을 처음부터 반복하지 않는다. 최종 CI는 정확한 push SHA로 확인하되 무한 대기하지 말고 종료 시점의 상태를 적는다.

Q1 이후는 FIXED_SEQUENCE.md의 Q2로 이어간다. 목표·순서·비용·판정 기준을 임의로 바꾸지 않는다.
