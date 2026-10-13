# BCT V4 실제 통합 결과 — 운영 교체 HOLD

2026-10-13 작업. **V4의 실행 가능한 CPU Shadow 코드를 제작·시험했다.
뉴스 이전 미래 병목 발견은 입증하지 못했으므로 전체 목표 완료는 BLOCKED다.**
main·V3.3·기존 운영 DB·Actions는 변경하거나 실행하지 않았다.
현재 개발 브랜치는 `codex/bct-v4-integration`이며 원문/모델/운영 DB는 Git에 넣지 않는다.

## 1. 실제 연결한 오픈소스

- Trafilatura 2.3.1: 동일 native HTML의 비교 추출. 기존 parser를 유지한다.
- feedparser 6.0.12: 공식 EIA RSS의 실제 URL 발견·날짜 원문 보존.
- dateparser 1.4.3: 엄격 날짜 정상화; 연도/월만으로 날짜를 만들지 않는다.
- pypdf 6.1.1: 공식 QCR PDF **55쪽**, 94,494자 추출. 표 정확도/OCR는 UNKNOWN/NOT_RUN.
- NetworkX 3.5: 기존 BCT 검증된 근거 그래프의 연결성/구성요소 측정.
- GLiNER2 2.1.0 + torch 2.8.0+cpu: 실제 로컬 CPU 추론과 원문 위치 확인.
- Python SQLite: V4 단일 append-only 원장, 트랜잭션, 재시작/백업/복원.

코드 라이선스는 설치된 LICENSE/NOTICE를 확인했다. 모델 가중치는 별도로 Apache-2.0
model card를 확인하고 고정 revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`를 사용한다.
모델 SHA-256 `845fc4bd93c525b86124c58ab4f56c9eacf8587953086b14c501fab25957c007`은 공식 LFS 체크섬과 일치한다.
제3자 코드를 무단 복사하지 않았으며 package LICENSE/NOTICE는 설치물에 보존한다.
원문 데이터는 코드/가중치 라이선스와 별도이고 원문·가중치는 재배포하지 않는다.

기존 53개 프로젝트의 재검토와 채택/제외 사유는 [REUSE_MANIFEST.json](REUSE_MANIFEST.json)에 있다.
EdgarTools는 기존 SEC 동일 기능을 교체할 비교 우위가 없어 새로 설치하지 않았다.
PEMMSS·StatsForecast·PyPSA·OR-Tools는 검증된 분야 입력이 없어 설치/실행하지 않았다.
SupplyGraphAI는 365일·고정수요 가정으로 12~36개월 핵심 경로에 넣지 않았다.
changedetection.io 상주 서버 대신 불변 원문 버전을 저장한다. 이들을 통합 완료했다고 주장하지 않는다.

## 2. 기존 BCT 재사용

`objective_lock`, `future_body.extract_document`, `SECTransport`, `parse_listing`,
`precursor_official_source.verify`, `precursor_collection.structure`,
`precursor_scope_reader`, `precursor_temporal`, `precursor_evidence_graph.analyze`,
`early_forecast.discover`, `forecast_discovery`의 URL/기간/독립성 계약을 재사용했다.
기존 future_store/recovery 모듈도 읽고 관련 회귀시험을 실행했지만,
V4 SQLite의 쓰기를 V3.3 JSON/운영 DB에 연결하지 않았다.
12개 기존 핵심 모듈의 원본 hash 불변은 [ANALYSIS_RECEIPT.json](ANALYSIS_RECEIPT.json)에 있다.

## 3. 새 코드와 이유

`src/bct/v4/`의 adapters는 직접 라이브러리 호출·CPU span 검증·공식 파일 hash 확인을,
store는 SQLite 원자성·immutable firsts·실패/복구 원장을,
pipeline은 기존 엄격 도메인 코드의 V4 경로 연결과 UNKNOWN 보존을 담당한다.
CLI와 sources 설정은 사용자가 패키지별 설치/코드 연결을 하지 않게 제공한다.
AI span은 scope/자격/주문 사실/독립 공급을 자동 확정하지 않는다.
라이브러리가 해결하지 않는 BCT 전용 연결과 보존 기능만 추가했다.

## 4. 단계별 결과

| 단계 | 결과 | 실제 증거와 제한 |
|---|---|---|
| 1 분석 | PASS | 연구 6개·53개 원장·목표 일치; 기존 기능 241 PASS, 실제 holdout 1 skip |
| 2 연결 | PASS | CPU 실제 추론·6개 라이브러리 호출·SQLite·반복 설치·복구 |
| 3 실제 원문 | BLOCKED | 3개 공식 원문의 CPU/저장 기능 PASS; 전체 TARGET/역할 정답 및 완전 누락률은 UNKNOWN |
| 4 판단 | NOT_RUN | 단계3 전체 미통과. 독립 합성 반례와 S단계 회귀는 PASS |
| 5 과거 선행 실증 | BLOCKED | 허용 가능한 Positive/Negative/hard Negative/미사용 HOLDOUT 각각 0건 |
| 6 7일 Shadow | NOT_RUN | 독립 실제 원문 수집 기록은 하루. 7일 경과·단계5 실증 없음 |
| 7 최종 | BLOCKED | 핵심 성능 미입증, V3.3 교체 HOLD |

최종 회귀 **261 PASS / 1 기존 skip / 0 FAIL**.
20개 V4 기능/반례 시험에는 동일 TARGET·원출처·가짜 계획·미래 정보·UNKNOWN 수량·Relief·
잘못된 S3 승격 방지와 중복/rollback/첫시각/백업/재열기를 포함한다.
합성 fixture는 실제 병목 Positive/Negative 사례로 집계하지 않았다.
전체 결과와 명령/입력 hash는 [TEST_RESULTS.json](TEST_RESULTS.json)에 있다.

## 5. V3.3 대비 수치

동일 EIA native HTML(113,819 bytes, 연구와 동일 raw SHA)에 미리 알려진 물리 수치 6개를 비교했다.
5회 반복에서 양쪽 모두 **6/6 보존**. 본문은 **10,259→4,646자 (54.7% 감소)**.
CPU 시간 중앙값은 기존 **0.0829초**, Trafilatura **0.2925초**로 새 경로가 더 느렸다.
노이즈 감소 가능성은 있으나 표/첨부 완전성·전체 정확도 향상은 증명하지 못했다.
따라서 기본 parser를 바꾸지 않았다. 원문 재구성 HTML을 native 시험으로 바꾸지 않았다.
TARGET 5필드·수요/공급 역할·독립성의 실제 precision/recall과 V3.3 전체 비교는 UNKNOWN이다.

## 6. 실제 발견 자료와 TARGET 상태

SEC 공식 listing과 primary filing 검증으로 Baker Hughes/Apple 공시 6건에서 공개일·원출처·FULL 본문을 확인했다.
전체 source URL/공개일/확보일/원문 hash는 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)에 있다.

실제 CPU 최종 시험은 Baker Hughes 10-Q(2026-07-27), 8-K(2026-09-09),
[미국 에너지부 원전 자료](https://www.energy.gov/articles/fact-sheet-golden-era-american-nuclear-energy-has-arrived)
(공개 메타데이터 2026-07-25)를 사용했다. DOE 본문 상태는 PARTIAL로 유지한다.
원전 자료에서 `advanced test reactors`, `nuclear fuel` 등의 원문 product span을 얻었다.
규격·지역·고객·적격 공급풀·필요/가용 수량·기간 및 산업 자동 분류는 UNKNOWN이다.
그 원전 관련 문서의 주제가 검증된 미래병목 산업/TARGET을 의미하지 않는다.

현재 모델 product span 중 기존 물리 제품 문법 검토를 통과한 탐색 lead는 2개,
추가 물리 TARGET 검토가 필요한 span은 21개다. 이는 중복 제거된 산업/TARGET 수가 아니다.
`Item 7.01.`, `notes`와 일반 명사/사업명 오분류도 원문 위치가 맞을 수 있다.
따라서 confidence/위치 정확성을 의미 정확성으로 바꾸지 않았다.
적격 미래 병목 후보 **0건**, 신규 검증 TARGET **0건**.
기존 TARGET 확인과 신규 TARGET 성능은 V3.3 전체 운영 corpus가 없으므로 UNKNOWN으로 별도 기록했다.

## 7. 뉴스 선행 실증

확인된 EARLY 성공 **0건**. 공개일 검증된 당시 corpus·동결 정답·최초 부족 공개일·
미사용 HOLDOUT이 없어 성능 BLOCKED다. 기존 holdout 파일은 이미 검사/수정에 사용된
회귀 자료로 명시돼 있어 untouched holdout으로 재사용하지 않았다.
BACKFILL/SYNTHETIC/LIVE는 분리한다. 현재 retrieval 시각을 과거 발견일로 바꾸지 않았다.

## 8. 자원과 비용

최종 실제 공식자료 3건의 수집/CPU/저장/그래프 실행: CPU **62.06초**,
경과 **47.27초**, 프로세스 peak RSS **2122.0 MiB**.
4 threads, GPU 필수 없음. 각 문서 최대 4개의 signal window를 판독해 미판독 window를 기록했다.
CPU smoke와 실문서 시험 일부는 병행됐으므로 다른 머신 처리량·전용 단일 프로세스 wall 성능으로 일반화하지 않는다.
모델 파일 약 834 MB, 패키지와 모델/캐시 디스크는 별도다.
유료 API 호출 **0회**, 추가 API 요금 **0원**. 플랫폼/전기/장기간 처리량은 측정하지 않았다.

## 9. 실패·수정·남은 제한

실제 실패 기록은 `var/v4/evidence`에 보존했고 checksum 목록을 공개 요약에 기록했다.
초기 dateparser/htmldate 버전 충돌은 지원 버전으로 수정했다.
잘못 가정한 DOE RSS 404는 공식 EIA RSS 디렉터리의 관측 URL로 교정했다.
모델 cache의 read-only 문제는 workspace cache 경로로 수정했다.
Xet stall과 hub HTTP403은 성공한 urllib HTTPS probe에 따라 동일 공식 고정 파일을
표준 TLS downloader로 받아 공식 LFS 체크섬을 검증했다. TLS/체크섬은 끄지 않았다.
반복 설치에서 원장 자기참조 hash 때문에 두 번째 load가 차단된 문제를 수정하고,
설치 2회·실제 CPU·공식 원문 시험을 다시 통과했다. 가중치 자체 hash는 변하지 않았다.
EIA의 0-window 문서는 AI PASS가 아니라 NOT_RUN이다. 실제 호출한 3개 문서로 별도 재시험했다.

미검증: 전체문서 recall, AI 사건 역할/부정문 의미, 표/OCR, 전체 적격 공급,
정량/시계열/분야 simulation, 원출처의 모든 재인용 관계, 블라인드 과거 성능,
7일 연속 자동 운영, V3.3 전체 corpus 비교, 알림/화면/배포.
기존 엄격 코드가 문서 전체의 shortage 표현을 차단하는 보수적 누락도 유지했다.
실제 DB backup을 별도 root로 복원해 21개 immutable 문서 행과 원장 무결성을 검증했다.

## 10. GitHub·재실행

개발 브랜치: `codex/bct-v4-integration`. 실제 push SHA/PR 상태는 작업 완료 응답과
[DELIVERY.json](DELIVERY.json)에 기록한다. main으로 병합하지 않는다.
[실행 안내](README.md), [사전 고정 시험 기준](TEST_PLAN.md), `scripts/v4/setup.sh`를 제공한다.
환경의 install_script/start_skill 및 필요한 공개 source/model 도메인은 재사용 초안에 저장한다.
초안 저장은 환경 게시나 새 작업 복원 검증을 의미하지 않는다.
실제 전체 목표 완료를 위해 당시 독립 corpus/미사용 HOLDOUT 확보와 실제 7일 운영이 필요하다.
