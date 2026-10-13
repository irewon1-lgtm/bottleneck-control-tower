# BCT V4 최소 재사용 구조 — 연구 설계, 운영 미반영

판정: 부품을 이용한 읽기 전용 shadow 연구는 착수 가능. V3.3 대체·중단·실제 선행예측 성능 통과는 보류.

고정 목표: 병목 뉴스 전에 독립적인 수요·공급 근거를 연결해 12~36개월 내 동일 TARGET의 수요가 적격 공급을 추월할 후보를 발견한다. 주가·수익률 제외. 불명확하면 UNKNOWN.

## 부품과 연결 코드

| 기능 | 재사용 부품/구체 코드 | 기존 기능 대체 범위 | 필요한 연결 코드 | 검증 상태 |
|---|---|---|---|---|
| RSS | feedparser `feedparser/api.py:parse` | RSS 파싱 | URL·공개일·수집일·원문 hash 기록 | 날짜·손상 XML fixture 실행 |
| SEC | EdgarTools `edgar/entity/core.py`, HTML/XBRL 모듈 | 기업 식별·공시 탐색·공시 구조화 | 기존 CIK와 accession mapping, SEC 식별·속도 제한 | SEC endpoint 접근; 구버전 HTML 파서만 실행 |
| HTML | Trafilatura `trafilatura/core.py:extract` | 범용 본문 추출의 선택 경로 | 기존 원문 버전과 별도 추출 hash; 실패·PARTIAL 유지 | 실제 EIA HTML 1건 실행 |
| PDF | pypdf `_page.py:extract_text`; 복잡한 표는 Docling `document_converter.py` 선택 | PDF 텍스트; 표/OCR는 후속 | 페이지·표·행·열 locator 및 첨부 누락 표시 | pypdf fixture 실행; Docling NOT_RUN |
| 변경 감시 | changedetection.io `processors/text_json_diff/__init__.py` | IR·인증·허가 페이지 변경 | 변경을 문서 버전으로 등록; 변경 자체를 Demand로 해석하지 않음 | 소스 확인; 상주 실행 NOT_RUN |
| CPU 판독 | GLiNER2 `inference/engine.py`, `fastino/gliner2-base-v1` | 문서에서 개체·수량·시간 span 후보 | 사건 schema, actual/planned, negation, quantity/unit/basis, role, confidence·원문 검증 | CPU entity 추출 실행; 의미 정확도 미검증 |
| 날짜 | dateparser `dateparser/__init__.py:parse` | 명확한 날짜 정상화 | 분기·연도 interval 보존; publication/need/ready 각각 별도 연결 | 엄격 parsing fixture 실행 |
| 그래프 | NetworkX + SupplyGraphAI `domain/graph.py`, `data/validation.py` | 관계·중단·재고/대체 공급의 제한된 scenario | 제품 규격·지역·기간·자격별 별칭; 원출처 의존성 등록 | 공급 중단 fixture 실행; 산업 그래프 정확도 미측정 |
| 광물 공급 | PEMMSS `modules/deposit.py:Mine.supply` | 광산의 ore capacity·grade·recovery·ready year 계산 | 검증된 광산·프로젝트 입력, 정련/규격 자격의 별도 단계 | fixture 실행; 실제 광산 forecast 미시험 |
| 수요 시계열 | StatsForecast `models.py:Naive/HistoricAverage`, `core.py:StatsForecast` | 실제 월별 수량이 있는 TARGET만 | target별 series, vintage cutoff, backtest split | 36개월 fixture 실행; 실제 산업 정확도 미측정 |
| 배분·용량 | OR-Tools 또는 분야별 PyPSA | 알려진 용량·납기 제약 계산 | 수량·범위가 비교 가능한 표준 입력 | 소스 확인; 실제 gap NOT_RUN |
| 저장·큐 | Python 표준 SQLite, 단일 worker | 로컬 단일 저장과 원자적 상태 처리 | append-only 문서버전/판독/예측/실패, lease·재시도 상한 | 최소 저장·중복·rollback·재열기 실행; 운영 큐 미구현 |
| 화면·알림 | 기존 정적 화면/알림을 read-only adapter로 재사용 | 보기·수동검토·변경 요약 | DB에서 요약 JSON export, UNKNOWN·근거·실패 표시 | 설계만; UI·알림·스케줄 NOT_RUN |

핵심 경로는 `공식 자료 → 원문 버전 → CPU span 후보 → 엄격 사건 검증 → 동일 TARGET 근거 그래프 → 기간별 조건부 공백 → UNKNOWN/검토 후보 → 예측 원장`이다. SQLite 하나를 상태 정본으로 두고 큰 원문은 hash-addressed 파일로 보관한다. 모델·본문을 공개 GitHub에 자동 업로드하지 않는다.

## 없어서는 안 되는 최소 도메인 코드

라이브러리는 아래 5가지를 대신하지 않는다. 이것이 V4의 실제 추가 개발 부담이며, 단순히 패키지를 연결하는 것만으로 목표가 달성되지 않는다.

1. TARGET identity: 제품·규격·지역·기간·적격 공급풀을 분리. 애매한 규격과 지역은 동일 대상 자동 병합 금지.
2. Event/role linkage: 주문·계약·CAPEX를 구분. CAPEX 달러를 제품 수량으로 환산하지 않음. 취소·조건부 계약·연간 vs 분기·total vs additional 보존.
3. Independence: 다른 URL/매체/도메인이라도 같은 계약·보도자료·기업발표를 복제했다면 한 origin. 고객·제조사의 동일 계약 언급도 사실 독립 corroboration과 별개. source_event_id, original_publisher, cited_origin를 기록.
4. Qualified supply: 명목 생산능력이 아니라 해당 기간의 자격·수율·납품가능량·재고·대체 공급·배정량. 숨은 공급을 0으로 채우지 않음. 정보가 없으면 UNKNOWN.
5. Time/evaluation: 공개일 precision, 실제 관측시각, need/ready interval, prediction frozen timestamp, 해당 기간 shortage confirmation을 분리. backfill을 LIVE로 표시하지 않음.

수치 공백은 동일 단위·지역·기간·규격·기준의 수요 하한 > 전체 적격 공급 상한일 때만 조건부 근거로 등록한다. 모델 전망이나 단일 업체 생산량만으로 전체 공급 상한을 만들지 않는다. Relief는 신공급·인증·재고·대체·효율·수요둔화까지 별도 기록한다.

## 선행예측 gate

이번 연구의 EARLY는 UNVERIFIED. 최소 재개 조건은 당시 공개문서군, 고정 cutoff, 독립 정답 사건, 미사용 holdout, 최초 부족 보도의 공개시각 범위, 양성·음성·어려운 음성 비교다. 검색에서 못 찾았다는 사실을 최초 보도 부재의 증명으로 사용하지 않는다. 전향 관측과 blind 과거 replay의 결과를 각각 보존한다.

## 자원·운영

측정: GLiNER2 CPU 4threads, 1,666자 inference 1.13초, model load 39.09초, 해당 프로세스 최대 RSS 약 2.26GiB. 이는 서버의 단일 입력 결과이며 사용자 노트북 속도나 최대 batch 처리량을 증명하지 않는다. 파서/그래프/시계열 fixture 한 프로세스의 누적 최대 RSS 약 332MiB. 다른 프로세스의 RSS를 합산하거나 부품별 독립 최소 RAM이라고 표시하지 않는다.

실용 권고(미측정 하드웨어 추정): CPU 4threads, RAM 8GB 이상으로 작은 GLiNER2 worker만 실행; 다른 작업 병행 시 16GB 이상이 여유롭다. 기존 사용자 RAM32GB PC는 trial 대상. GPU·유료 API는 필요하지 않지만 CPU 속도와 디스크 용량, 장시간 자동 실행은 별도 측정해야 한다. 9B LLM은 필수 경로에서 제외한다.

로컬 머신 사용 시 API 추가요금 없이 운영할 구성이며, 인터넷·전기·상주 PC가 필요하다. GitHub Actions 무료 한도·아티팩트 보존은 무제한 저장 대안이 아니다. 상주 모델은 로컬, GitHub는 코드·정적 요약·검증자료 버전 관리에 한정하는 구성이 가장 단순하다. Actions/FCM/메일/웹 배포는 이번에 실행·변경하지 않았다.

## 최종 제작 판단

- GO: 원문·CPU 후보 추출·단일 저장 shadow pilot. 이미 최소 통합 시험 실행.
- HOLD: V4 전체를 미래병목 예측 시스템으로 제작·운영 채택. TARGET/role/적격 공급/독립성/시간 gate가 실제 문서에서 검증되지 않았다.
- NO-GO: 기존 V3.3 중단·데이터 폐기·완제품처럼 복사해 대체. 이 연구가 이를 뒷받침하지 않는다.
