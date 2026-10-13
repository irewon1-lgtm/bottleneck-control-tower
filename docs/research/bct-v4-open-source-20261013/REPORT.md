# BCT V4 오픈소스 발굴·실증 보고서

조사일: 2026-10-13. 연구 대상: 12~36개월 미래 수요가 동일 규격·지역·기간의 적격 공급을 추월할 TARGET의 사전 발견. 주가·투자수익률 제외.

## 최종 판정

**검증된 부품을 재사용하는 무료 CPU 구성은 실제로 조립할 수 있다. 하지만 ‘병목 뉴스보다 먼저 미래 부족을 발견한다’는 핵심 성능은 이번 조사로 입증되지 않았다. V4 운영 대체는 HOLD, 읽기 전용 shadow 연구는 GO다.**

53개 고유 공개 프로젝트의 메타데이터를 확인하고, 소스·라이선스·문서 113개 파일을 조사 원장에 기록했다. 프로젝트별 조사 깊이는 다르며, 모든 프로젝트 전체 소스나 모든 릴리스·포크를 감사한 것은 아니다. 11개 프로젝트의 일부 코드 또는 공개 데이터를 실행·판독했다. README만 읽은 후보와 직접 실행한 후보를 아래에서 구분한다.

독립적인 실제 신규 병목 확정 후보: **0건**. EARLY: **UNVERIFIED**. 실제 TARGET 5필드 정확도·Demand/Supply 역할 정확도·독립 원출처 연결 정확도: **NOT_MEASURED**. 기능 fixture가 통과한 것을 미래예측 성공으로 바꾸지 않았다.

기존 BCT main·운영 DB·Actions·실패 목록·예측 이력에는 쓰지 않았다. 별도 연구 브랜치에 보고서와 연구 원장만 저장한다. 사용자의 첨부 US3700_ANALYSIS.csv 3,700행은 기업·CIK·산업 식별 참고다. 재무·주가 지표를 공급능력·주문량·적격 공급의 대체 입력으로 사용하지 않았다.

## 1. 범위와 중복 처리

수급 위험, disruption prediction, early warning, production bottleneck, lead time, qualified capacity, supplier knowledge graph, mineral exploration/mine development, event extraction, temporal reasoning, CPU inference와 관련 학술 구현·전력 연구 모델·정부 자료를 확장 조사했다.

- 지정한 13개 프로젝트 모두 포함했다.
- 정부/기관 자료는 SEC, EIA, USGS, USAspending, IEA를 추가 확인했다. 논문 구현은 PEMMSS, GCAM, EventPlus, GLiNER2, 공장 병목 도구를 포함한다.
- 잘못된 저장소 경로 `dateparser/dateparser`는 `scrapinghub/dateparser`로, `google/timesfm`은 `google-research/timesfm`로 교정했다. 오류를 프로젝트 부재로 판단하지 않았다.
- 조회한 53개 canonical 저장소에서 GitHub fork flag는 모두 false였다. 이 사실이 저자 독창성이나 복제품이 없다는 것을 보증하지는 않는다.
- 검색에 나온 GLiNER2·Stockpyl·Pymrio의 여러 fork/미러는 독립 엔진 수에 더하지 않았다. 포크 개선 성능의 전면 비교는 미실행이다.
- GitLab/Codeberg 및 전 세계 모든 공개 프로젝트를 빠짐없이 조사했다는 주장은 하지 않는다. 이번 결과는 명시한 53개와 공개 연구·자료의 접근 가능한 범위다.

## 2. 실사용 후보 TOP 10

아래 순서는 재사용 우선순위이며 예측 정확도 순위나 별점 순위가 아니다. NetworkX/SQLite는 공통 기반으로 별도 취급한다. 기능을 그대로 이용할 수 있어도 BCT 판단까지 자동 완료된다는 뜻은 아니다.

| 순위 | 프로젝트 | 맡길 기능 | 실제 검증 범위 |
|---|---|---|---|
| 1 | [adbar/trafilatura](https://github.com/adbar/trafilatura) | HTML 원문 추출 | 실제 EIA HTML 실행 |
| 2 | [fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2) | CPU 개체·수량·시간 후보 | CPU 실행·51개 원문 위치 확인; 의미 오류 존재 |
| 3 | [dgunning/edgartools](https://github.com/dgunning/edgartools) | SEC 공시·CIK·XBRL | 구버전 HTML 파서 실행; 최신 SEC end-to-end 미검증 |
| 4 | [py-pdf/pypdf](https://github.com/py-pdf/pypdf) | PDF 텍스트 | fixture 실행; 스캔·실제 표 NOT_RUN |
| 5 | [kurtmckee/feedparser](https://github.com/kurtmckee/feedparser) | RSS·날짜 | fixture 실행 |
| 6 | [scrapinghub/dateparser](https://github.com/scrapinghub/dateparser) | 정확한 날짜 정상화 | strict parsing 실행; 사건 역할 연결 없음 |
| 7 | [sanorthey/pemmss](https://github.com/sanorthey/pemmss) | 광산 공급능력·ready year | 광석→금속 및 지연 fixture 실행 |
| 8 | [Nixtla/statsforecast](https://github.com/Nixtla/statsforecast) | 수요 시계열 | 36개월 fixture 실행; 실제 산업 정확도 미측정 |
| 9 | [mercer14k/SupplyGraphAI](https://github.com/mercer14k/SupplyGraphAI) | 공급 중단·대체 공급 시나리오 | 기능 실행; 365일·고정수요·즉시 대체 제한 |
| 10 | [dgtlmoon/changedetection.io](https://github.com/dgtlmoon/changedetection.io) | IR·허가 페이지 변경 감시 | 소스 확인만; 운영 실행 NOT_RUN |

## 3. 지정 프로젝트에서 확인된 차이

WorldMonitor는 상황 인지·화면 참고에 적합하다. 국가 위험·뉴스 점수는 동일 제품의 수급 공백을 증명하지 않는다. AGPL 조건을 무시하고 화면/코드를 복사하지 않는다.

Horus의 SEC·정책·공급망 어댑터는 참고할 가치가 있다. 다만 `etl/sources/risks.py`의 확률·회복일·금액은 휴리스틱이 포함돼 있으므로 BCT 예측 확률로 가져오지 않는다.

World Mining Monitor의 DB를 직접 읽었다. 176개 mine 메타 레코드, 68개 company 값, 17,260개 생산/판매/품위/guidance 레코드가 있다. commodity 필드의 고유 문자열은 70개이며, 이를 검증된 70개 광물로 해석하지 않는다. source_url이 빈 레코드가 536개(약 3.1%)다. 실제 원문과 수량을 대조한 정확도 시험은 미실행이다. DB를 읽을 수 있다는 것과 생산량이 맞다는 것은 다르다. 코드 MIT와 데이터 연구·교육 조건을 구분한다. 공개된 것은 앱·DB builder·데이터 snapshot이며 보고서 추출/파이프라인 관리 코드는 공개 예정이다. 따라서 Gemini 추출 엔진을 무료로 복사할 수 있는 완제품으로 평가하지 않았다.

SupplyChain-Risk-Engine의 핵심은 geo/delay/financial 위험의 가중합이다. `score_delay_risk`는 납기와 variance의 선형 결합이다. 산업의 미래 총수요·적격 총공급 계산기가 아니다.

SupplyGraphAI는 AND/OR 공급 의존성, 재고 buffer, 대체 공급을 구현했다. 실제 fixture에서 영향을 확인했다. 그러나 `ScenarioRequest.duration_days`는 최대 365일이고 고정수요·이미 승인된 즉시 대체 공급을 가정한다. 730일 입력은 실제로 거절됐다. 장기 병목 엔진으로 사용하려면 새 도메인 모델이 필요하며 단순 상한 변경으로 해결할 수 없다. stars 1이라는 숫자가 실패를 뜻하지는 않지만, 성숙한 전문가 완제품으로 포장할 근거도 없다.

Sara Al Mahri의 agent 프로젝트는 연구·평가 자료 참고다. CC BY-NC 및 OpenAI search 도구가 있어 무료 핵심 운영에서 제외한다. neet813 예제는 API 실패 시 2138, 50, 고정 국가 LPI 같은 fallback을 사용하므로 UNKNOWN 원칙과 맞지 않는다. license도 없다.

KAG/Dify/n8n/Huginn은 추론·워크플로·감시에 쓸 수 있지만 TARGET·적격 공급·12~36개월 시간 공백은 별도 구현해야 한다. 큰 workflow 도구 2~3개를 동시에 설치할 필요가 없다.

## 4. 실제 시험 결과

시험 명령과 환경은 TEST_RESULTS.json 및 tests/에 남겼다. 모델을 호출한 것은 로컬 CPU뿐이다. 합성 fixture와 실제 입력을 분리한다.

| 시험 | 실제 입력/방법 | 관측 결과 | 판정의 한계 |
|---|---|---|---|
| 보존 원문 검증 | 기존 BCT EIA 자료 10,229자 | 기존 SHA-256·원문 locator 일치 | 한 문서; 당시 상태 PARTIAL |
| HTML 비교 | 동일 현재 EIA native HTML | 기존 10,259자 vs Trafilatura 4,646자; 핵심 숫자 양쪽 6/6 | 텍스트량 약 54.7% 감소. 완전한 표/첨부 확보·더 높은 정확도는 증명 안 됨 |
| HTML 처리 시간 | 같은 HTML 각 1회 | 기존 약 0.019초, Trafilatura 약 0.222초 | 초기 비용 포함; 새 파서가 더 빠르다는 결과는 아님 |
| 원문 접근 | EIA·USGS·SEC 3곳, 각 1회 | EIA·SEC HTTP200, USGS403 | HTTP 성공 2/3. 완전본문 확보율로 해석 금지; 표본 매우 작음 |
| CPU GLiNER2 | 보존 EIA highlight 1,666자 | load 39.09초; inference 1.13초; 최대 RSS 약 2,316MiB | entity 51개; 조직·수량 의미 오류. 전체 TARGET accuracy 미측정 |
| GLiNER2+단일 저장 | 실제 모델 출력→원문 span→SQLite | 51/51 위치 확인·중복 방지·오류 rollback·재열기 확인 | 최소 adapter 통합 PASS; 실제 사건 역할·독립성·forecast 아님 |
| EdgarTools | EIA HTML의 텍스트 함수 | 핵심 숫자 6/6; 표 0개 | 설치된 2.21.1은 구버전. 최신 SEC/XBRL 실증 아님 |
| RSS | synthetic 정상/손상 XML | 공개일 보존·손상 감지 | 실운영 피드 확보율 아님 |
| dateparser | exact date·year-only fixture | exact 날짜 처리; 연도만 있으면 None | 분기 interval·need/ready 연결은 없음 |
| pypdf | 숫자 포함 PDF·손상 PDF fixture | 숫자 보존·손상 파일 거절 | 실제 공시 PDF 표·OCR 미시험 |
| SupplyGraphAI | synthetic supplier/product/alternate | 5일 후 영향, 250단위; 대체 공급 시 영향 없어짐; dangling edge 거절 | 실제 기업 입력이 아님 |
| PEMMSS | synthetic 광산 | 2027 공급0; 2028 광석100×품위2%×회수율80%=금속1.6 | 실제 광산 수급 예측 아님 |
| StatsForecast | 상수100의 48개월 fixture | 36개월 출력100 | API 기능시험; 실제 수요 forecasting accuracy 아님 |
| 저장 반복·복구 | 동일 문서1건 1,000회 삽입 | distinct1건; rollback·재열기 확인 | 문서1,000개 처리나 전파 안정성 시험으로 표시하지 않음 |

GLiNER2 관찰: 실제 product 추출은 steam/metallurgical coal을 포함했지만 `electric power sector`를 organization으로 분류했다. quantity에 가격과 비율도 섞였다. 높은 confidence도 BCT 의미의 정답을 보증하지 않는다. 인용 span 검증은 가능하지만 공급/수요 방향, 단위·basis, 미래기간의 연결은 별도 정답셋으로 시험해야 한다.

최소 통합의 마지막 출력은 UNKNOWN이다. 한 원출처의 과거 석탄 통계이므로 미래 부족·독립 출처를 만들어내지 않았다. 새 sector/TARGET 발견 및 실제 EARLY 실증은 아직 성공하지 않았다.

EdgarTools 첫 시험은 optional html5lib 누락으로 실패했다. 해당 의존성만 추가한 뒤 텍스트/표 함수를 다시 실행했다. 단순 HTTP 오류를 신규 데이터 부재로 바꾸지 않았다. GitHub 직접 다운로드 403에는 연결 도구를 이용했으며, 대용량 기존 운영 shard 조회는 빈 content/transport closed로 끝나 전체 운영 후보군은 재현하지 못했다. 동일 shard를 반복해 성능시험을 꾸미지 않고 기존 공개 roundtrip 원문1건으로 범위를 제한했다.

## 5. 기존 BCT보다 개선 가능한 것과 불가능한 것

| 구분 | 판단 |
|---|---|
| 원문 노이즈 | 실제 EIA 1건에서 읽을 텍스트량 감소 확인. 중요한 표/각주 누락 위험은 별도 검사 |
| CPU 개체 추출 | regex 밖 product/location/quantity/date span 확보 가능성을 실제 확인. V3.3 전체 recall 개선은 미측정 |
| 공급 scenario | 광산 ready year·품위·회수율, 공급망 대체 공급 계산을 재사용 가능 |
| 저장 단순화 | 단일 SQLite의 원자적 저장·재시도 idempotence 최소 실증. 운영 GitHub 저장403 해결 증명은 아님 |
| 무료 운영 | 로컬 CPU 부품만으로 시험 완료; 유료 API·GPU·클라우드 사용0 |
| 공급 데이터 빈칸 | 패키지로 해결 못함. 제품별 자격·재고·배정·수율 비공개면 UNKNOWN |
| 동일 TARGET·독립 근거 | 원출처·제품규격·기간을 연결하는 BCT adapter 개발·실증 필요 |
| 뉴스보다 선행 | 시간증거·전체 당시 corpus·결과 사건·holdout 없으면 검증 못함 |

## 6. 무료 자료·이용조건

| 자료 | 활용 | 제한/현재 검증 |
|---|---|---|
| SEC | CIK·공시·계약 첨부·생산/주문·risk factors | identity와 fair-access 준수; 정형 재무 XBRL은 생산량 대체 아님. submissions HTTP 확인 |
| EIA | 전력·연료 생산/소비·계획 | free key가 필요한 API와 공개 웹 구분. native HTML 실제 비교 |
| USGS | 광물 생산·수급·수출입 | 웹 검색 공식자료 확인; 직접 URL403. 연간 총량을 제품 자격공급과 동일시 금지 |
| USAspending | 조달·계약·수요 원인 | API 문서 확인; 실제 contract quantity extraction NOT_RUN |
| IEA Critical Minerals Dataset | 광물 수요·공급 scenario | 공식 2026 데이터 페이지 free/CC BY4.0 표기 확인. 데이터 파일 직접 trial NOT_RUN |
| 기업 IR·고객 계약·허가 | 제품별 주문·증설·need/ready | 공개 원문·공개일 보존; 자료별 재배포 조건 구분 |
| Mining Monitor snapshot | 생산 fact의 보조 탐색 | 무료 DB 읽기 확인; 연구·교육 조건·원문 대조·staleness 한계 |

공식 자료 링크: [SEC](https://www.sec.gov/about/developer-resources), [EIA API](https://www.eia.gov/opendata/documentation.php), [USGS](https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries/), [USAspending](https://api.usaspending.gov/docs/), [IEA](https://www.iea.org/data-and-statistics/data-product/critical-minerals-dataset).

## 7. 라이선스·재사용 제한

MIT/Apache/BSD의 허용 여부는 실제 파일과 package/weights별 원문으로 판단한다. 저작권·license·NOTICE를 보존하고, 수정 내용과 원출처를 기록한다. 라이선스 없는 프로젝트는 참고 관찰만 하고 재사용 배포 대상에서 제외한다.

- WorldMonitor AGPL: 네트워크 제공·변경 시 대응 소스 제공 조건 검토가 필요하므로 최소 구조의 복사 대상에서 제외.
- Pymrio GPL: 결합·재배포 시 조건 검토. 필수 core에서 제외.
- n8n: Sustainable Use와 .ee 파일의 기업 라이선스 조건. 일반 MIT 프로젝트처럼 재배포하지 않음.
- Dify: 수정 Apache의 multi-tenant·frontend 로고 조건.
- Sara 프로젝트: CC BY-NC. 무료라고 해도 상업 이용에 자동 허용되지 않음.
- TimesFM: 코드 Apache와 weights 별도. 2.5까지 Apache 표기, 3.0 weights는 non-commercial/non-production 제한. 최신 모델이라고 운영용 기본 선택하지 않음.
- GCAM-CMM, neet813, DisruptIQ, disruption-sim: 확인한 LICENSE 없음. 임의 복사 금지.
- World Mining Monitor: 앱 코드 MIT와 생산 데이터 연구·교육 조건은 다름. raw DB는 보고서/ZIP/연구 브랜치에 재배포하지 않음.

재사용 예시 코드 패키지는 SupplyGraphAI의 domain/validation과 PEMMSS의 시험 모듈, 해당 LICENSE 및 출처 안내에 한정한다. 다른 소스는 코드 위치·local hash 원장으로 남긴다. 실제 운영 채택 전 선택 버전의 전체 전이 의존성/weights 라이선스·취약점 검토는 미완료다.

## 8. V4 구조와 필요한 자원

별도 DESIGN.md에 기능별 구체 코드와 최소 adapter를 정리했다. 큰 완제품을 여러 개 중첩 설치하지 않고, HTML/RSS/PDF → CPU span 후보 → 엄격 사건 검증 → 근거 그래프 → 수요/적격 공급 시간 비교 → UNKNOWN/검토후보 → 단일 원장 구조를 사용한다.

필수 신규 도메인 코드는 5종: TARGET identity, Demand/Supply event-role linking, 원출처 독립성, 전체 적격 공급/Relief, 공개시각·need/ready·EARLY 평가다. 새 코드가 0줄인 완제품 대체는 발견하지 못했다. 추가 개발량을 정확한 일수·줄수로 제시할 근거도 없어 기능 단위와 상대 난이도만 원장에 표시했다.

자원 측정과 권고를 구분한다. GLiNER2 trial은 CPU4threads·프로세스 최대 약2.26GiB. 작은 worker용 RAM8GB는 권고 추정이지 최소 RAM 통과 시험이 아니다. 다른 작업 병행은 16GB 이상 권고, 사용자 RAM32GB PC를 후속 trial 대상으로 삼을 수 있다. 9B LLM은 필수 부품이 아니다. 모델 초기 다운로드·디스크·상주PC·전기·인터넷과 플랫폼 한도는 별도다. 실제 하루 문서수/월 처리량/CPU 최대 queue throughput은 미측정이다.

## 9. 남은 핵심 문제와 종료 기준

1. 실제 계약·공시로 TARGET/규격/지역/기간/공급풀 5필드와 사건 역할을 정답화한 공통 corpus가 없다.
2. 제품별 적격 공급 총량·납품 시점·재고·대체 공급이 공개 자료에서 빠진 경우 UNKNOWN이 계속 필요하다.
3. 독립 원출처 자동 판정과 수량·unit·basis·기간 일치 비교가 아직 실행 검증되지 않았다.
4. 현재 BCT 전체 candidate/read corpus는 원격 shard 접근 문제로 확보하지 못했다. 운영 이력의 전면 비교나 3,696 실패 복구 성능을 검증하지 않았다.
5. live scheduling/알림/대시보드·대량 서로 다른 문서 처리·전향 예측 결과·blind holdout을 실행하지 않았다.
6. 예측 최초 시각이 shortage 뉴스보다 앞섰다는 검증 가능한 증거가 없다.

**지금 착수할 가치가 있는 것은 검증된 부품을 쓰는 shadow pilot이다. V4를 완성된 선행 병목 엔진으로 운영 채택할 근거는 아직 없다.** 재개는 새로운 도구 목록 추가보다 실제 문서 정답 corpus와 적격 공급 정보를 확보해 동일 입력 시험을 하는 단계다. V3.3 중단/교체는 하지 않는다.

## 10. 전체 프로젝트 원장

Stars/Forks/pushed_at은 조회 당시 GitHub API snapshot이다. pushed_at은 저장소 push 시각이며 마지막 의미있는 엔진 수정일/품질/정확도를 뜻하지 않는다. 소스 확인 범위·외부 의존성·추가 개발 난이도는 PROJECTS.json에서 확인한다.

| 프로젝트 | 기능 | 판정 | Stars / Forks | 마지막 push UTC | 라이선스 | 실행 |
|---|---|---|---|---|---|---|
| [Ali-datasmith/SupplyChain-Risk-Engine](https://github.com/Ali-datasmith/SupplyChain-Risk-Engine) | 위험 점수 | 핵심제외 | 1 / 0 | 2026-08-15T15:21:59Z | MIT | NOT_RUN |
| [IndEcol/pymrio](https://github.com/IndEcol/pymrio) | 산업연관·네트워크 | 연구참고 | 224 / 86 | 2026-10-13T10:56:42Z | GPL-3 계열: 원문 확인 | NOT_RUN |
| [JGCRI/gcam-core](https://github.com/JGCRI/gcam-core) | 장기 통합 평가 | 연구참고 | 433 / 226 | 2026-09-18T15:24:12Z | API NOASSERTION; 개별 라이선스 확인 필요 | NOT_RUN |
| [LarrySnyder/stockpyl](https://github.com/LarrySnyder/stockpyl) | 재고·다단계 공급망 | 선택 | 181 / 38 | 2026-06-10T19:07:52Z | MIT | NOT_RUN |
| [Nixtla/mlforecast](https://github.com/Nixtla/mlforecast) | 수요 ML | 후순위 | 1284 / 141 | 2026-10-12T23:08:11Z | Apache-2.0 | NOT_RUN |
| [Nixtla/statsforecast](https://github.com/Nixtla/statsforecast) | 수요 시계열 | 조건부 | 4929 / 412 | 2026-10-13T01:01:06Z | Apache-2.0 | 36개월 fixture |
| [OSeMOSYS/OSeMOSYS](https://github.com/OSeMOSYS/OSeMOSYS) | 전력·에너지 최적화 | 연구참고 | 193 / 122 | 2025-10-22T16:36:22Z | Apache-2.0 | NOT_RUN |
| [OpenSPG/KAG](https://github.com/OpenSPG/KAG) | 지식그래프 RAG | 보류 | 9091 / 723 | 2026-01-28T13:30:54Z | Apache-2.0 | NOT_RUN |
| [PlusLabNLP/EventPlus](https://github.com/PlusLabNLP/EventPlus) | 사건·시간 추론 | 연구참고 | 28 / 14 | 2023-03-07T20:14:26Z | Apache-2.0 | NOT_RUN |
| [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect) | 큐·복구·스케줄 | 확장시 선택 | 24013 / 2575 | 2026-10-13T08:24:28Z | Apache-2.0 | NOT_RUN |
| [PyPSA/PyPSA](https://github.com/PyPSA/PyPSA) | 전력 용량·계통 | 분야별 선택 | 2189 / 714 | 2026-10-13T10:09:34Z | MIT | NOT_RUN |
| [ReEDS-Model/ReEDS](https://github.com/ReEDS-Model/ReEDS) | 전력 용량계획 | 무료 핵심 제외 | 39 / 18 | 2026-10-13T02:26:28Z | BSD-3-Clause | NOT_RUN |
| [Sakshi3027/disruptiq](https://github.com/Sakshi3027/disruptiq) | 뉴스·위험전파 | 핵심제외 | 1 / 0 | 2026-07-17T04:32:48Z | LICENSE 미확인/없음; 복사 보류 | NOT_RUN |
| [Sanskar-soni04/supply-chain-disruption-sim](https://github.com/Sanskar-soni04/supply-chain-disruption-sim) | 납기 시뮬레이션 | 연구참고 | 0 / 0 | 2026-09-11T23:12:14Z | LICENSE 미확인/없음; 복사 보류 | NOT_RUN |
| [abelraphelp/AI-Driven-Supply-Chain-Disruption-Detection-System](https://github.com/abelraphelp/AI-Driven-Supply-Chain-Disruption-Detection-System) | 뉴스·가격 위험 | 핵심제외 | 0 / 0 | 2026-07-03T08:33:21Z | MIT | NOT_RUN |
| [adbar/trafilatura](https://github.com/adbar/trafilatura) | HTML 본문 | 우선 | 6965 / 459 | 2026-10-06T19:31:29Z | Apache-2.0 | 실제 HTML 및 fixture |
| [amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting) | 시계열 기반모델 | 후순위 | 6069 / 741 | 2026-10-05T14:25:02Z | Apache-2.0 | NOT_RUN |
| [brinday/GCAM-CMM-supply-demand](https://github.com/brinday/GCAM-CMM-supply-demand) | 논문 결과·데이터 | 연구참고 | 0 / 0 | 2026-10-07T15:38:09Z | LICENSE 미확인/없음; 복사 보류 | NOT_RUN |
| [carbon-evolution/horus](https://github.com/carbon-evolution/horus) | 수집·공급망 그래프 | 부분재사용 | 0 / 0 | 2026-09-13T22:58:23Z | MIT | NOT_RUN |
| [dgtlmoon/changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 변경 감시 | 선택 | 34956 / 2140 | 2026-10-13T10:34:01Z | Apache-2.0 | NOT_RUN |
| [dgunning/edgartools](https://github.com/dgunning/edgartools) | SEC·공시 | 조건부 우선 | 2786 / 506 | 2026-10-13T10:22:27Z | MIT | 2.21.1 HTML 기능 |
| [docling-project/docling](https://github.com/docling-project/docling) | PDF·표·OCR | 선택 | 68799 / 5065 | 2026-10-13T10:36:23Z | MIT | NOT_RUN |
| [duckdb/duckdb](https://github.com/duckdb/duckdb) | 분석 저장 | 후순위 | 42153 / 3916 | 2026-10-13T10:53:29Z | MIT | NOT_RUN |
| [fastino-ai/GLiNER2](https://github.com/fastino-ai/GLiNER2) | CPU 정보 추출 | 조건부 우선 | 2366 / 210 | 2026-10-09T17:53:44Z | Apache-2.0 | CPU 실문서 부분 |
| [frePPLe/frepple](https://github.com/frePPLe/frepple) | 기업 생산계획 | 후순위 | 761 / 337 | 2026-10-12T12:56:17Z | API NOASSERTION; Community/Enterprise 원문 검토 필요 | NOT_RUN |
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | CPU LLM 런타임 | 선택 | 131003 / 24354 | 2026-10-13T10:58:08Z | MIT | NOT_RUN |
| [google-research/timesfm](https://github.com/google-research/timesfm) | 시계열 기반모델 | 조건부 보류 | 34424 / 3322 | 2026-09-29T19:36:25Z | Apache-2.0 | NOT_RUN |
| [google/or-tools](https://github.com/google/or-tools) | 제약·배분 계산 | 선택 | 14188 / 2525 | 2026-10-13T09:24:00Z | Apache-2.0 | NOT_RUN |
| [hsinnearth7/ChainInsight](https://github.com/hsinnearth7/ChainInsight) | 수요 계획 | 후순위 | 0 / 0 | 2026-03-26T14:08:59Z | MIT | NOT_RUN |
| [huginn/huginn](https://github.com/huginn/huginn) | 감시·알림 | 대안 | 50052 / 4307 | 2026-10-10T19:21:46Z | MIT | NOT_RUN |
| [kadoa-org/world-mining-monitor](https://github.com/kadoa-org/world-mining-monitor) | 광산 생산 데이터 | 조건부 데이터 참고 | 18 / 1 | 2026-10-12T04:11:27Z | MIT | 공개 SQLite 읽기 |
| [koala73/worldmonitor](https://github.com/koala73/worldmonitor) | 상황판 | 참고 | 88353 / 13508 | 2026-10-13T10:51:56Z | AGPL-3.0 | NOT_RUN |
| [kurtmckee/feedparser](https://github.com/kurtmckee/feedparser) | RSS | 우선 | 2443 / 381 | 2026-10-06T00:52:50Z | BSD-2-Clause: 원문 확인 | RSS fixture |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | agent 상태 흐름 | 후순위 | 43189 / 7341 | 2026-10-13T01:43:34Z | MIT | NOT_RUN |
| [langgenius/dify](https://github.com/langgenius/dify) | LLM 워크플로 | 보류 | 158347 / 25026 | 2026-10-13T10:48:29Z | 수정 Apache: multi-tenant·로고 조건 | NOT_RUN |
| [mercer14k/SupplyGraphAI](https://github.com/mercer14k/SupplyGraphAI) | 공급망 전파 | 선택 모듈 재사용 | 1 / 0 | 2026-09-28T00:35:08Z | Apache-2.0 | domain 모듈 fixture |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 워크플로 | 보류 | 207193 / 61109 | 2026-10-13T10:57:36Z | Sustainable Use + Enterprise 파일 구분 | NOT_RUN |
| [neet813/Supply-Chain-Early-Warning](https://github.com/neet813/Supply-Chain-Early-Warning) | 물류 조기경보 예제 | 제외 | 1 / 0 | 2026-03-12T07:50:35Z | LICENSE 미확인/없음; 복사 보류 | NOT_RUN |
| [networkx/networkx](https://github.com/networkx/networkx) | 근거 그래프 | 우선 기반 | 17323 / 3636 | 2026-10-06T17:42:21Z | BSD-3-Clause: 원문 확인 | SupplyGraphAI 내부 |
| [nikolaiwest/2023-prepflow-webtool-bottleneck](https://github.com/nikolaiwest/2023-prepflow-webtool-bottleneck) | 공장 병목 | 연구참고 | 0 / 0 | 2023-10-17T09:35:16Z | MIT | NOT_RUN |
| [oladri-renuka/supply-chain-risk-gnn](https://github.com/oladri-renuka/supply-chain-risk-gnn) | GNN 위험 모델 | 연구참고 | 0 / 0 | 2026-09-12T22:12:19Z | MIT | NOT_RUN |
| [ollama/ollama](https://github.com/ollama/ollama) | 로컬 모델 운영 | 대안 | 182979 / 18245 | 2026-10-13T04:51:43Z | MIT | NOT_RUN |
| [pdfminer/pdfminer.six](https://github.com/pdfminer/pdfminer.six) | PDF 대안 | 보류 | 7037 / 1046 | 2026-03-13T13:46:54Z | MIT | NOT_RUN |
| [py-pdf/pypdf](https://github.com/py-pdf/pypdf) | 텍스트 PDF | 우선 | 10256 / 1647 | 2026-10-13T10:57:18Z | BSD 계열: 실제 LICENSE 원문 확인 | PDF fixture |
| [run-llama/llama_index](https://github.com/run-llama/llama_index) | RAG | 후순위 | 52473 / 8333 | 2026-10-12T19:28:17Z | MIT | NOT_RUN |
| [rxbinsingh/GHOST](https://github.com/rxbinsingh/GHOST) | 공급망 위험 연구 | 연구참고 | 1 / 0 | 2026-05-05T08:05:31Z | MIT | NOT_RUN |
| [sanorthey/pemmss](https://github.com/sanorthey/pemmss) | 광물 공급 시나리오 | 선택 모듈 재사용 | 22 / 4 | 2026-04-22T08:59:10Z | BSD-3-Clause | Mine.supply fixture |
| [sara-almahri/supply-chain-disruption-monitoring](https://github.com/sara-almahri/supply-chain-disruption-monitoring) | 에이전트·평가 자료 | 연구참고 | 4 / 1 | 2026-03-09T05:07:44Z | CC BY-NC 4.0: 비상업 제한 | NOT_RUN |
| [scrapinghub/dateparser](https://github.com/scrapinghub/dateparser) | 날짜 | 우선 | 2861 / 529 | 2026-10-12T07:17:04Z | BSD-3-Clause | 날짜 fixture |
| [scrapy/scrapy](https://github.com/scrapy/scrapy) | 수집기 | 선택 | 64778 / 12002 | 2026-10-13T11:02:05Z | BSD-3-Clause | NOT_RUN |
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | 대시보드 | 대안 | 45968 / 4423 | 2026-10-13T10:08:48Z | Apache-2.0 | NOT_RUN |
| [unit8co/darts](https://github.com/unit8co/darts) | 시계열 통합 | 후순위 | 9542 / 1053 | 2026-10-12T13:38:35Z | Apache-2.0 | NOT_RUN |
| [urchade/GLiNER](https://github.com/urchade/GLiNER) | 개체 추출 | 대안 | 4086 / 319 | 2026-10-05T09:06:36Z | Apache-2.0 | NOT_RUN |

증거: PROJECTS.json, SOURCE_MANIFEST.json, TEST_RESULTS.json, DESIGN.md, tests/, evidence/의 로그·입력 hash. 초기 실패 기록과 수정 후 결과를 모두 보존한다. GLiNER2의 초기 BLOCKED/no-weights 표기는 CPU 실행 이후 결과로 대체되었다.
