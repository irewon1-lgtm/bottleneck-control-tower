# BCT V4 한국어 연구 대시보드

시작 SHA: `f977119c6edddff201e421d360fe01e6aca2a1da` · 개발 브랜치: `codex/bct-v4-integration`

실제 연구 DB와 보존된 연구 보고서를 읽는 로컬 웹앱이다. 새 외부 서비스·프런트엔드 프레임워크·AI 호출 없이 Python 표준 HTTP 서버와 기존 웹의 DOM 렌더링 방식을 사용했다. 기존 운영 화면과 배포 작업은 수정하지 않았다.

## 화면과 실제 기능

| 화면 | 확인할 수 있는 내용 |
|---|---|
| 한눈에 보기 | 후보 집계, 원본·본문 확보, 실제 판독 범위, 기존 검토 사건, 산업별 자료 공백 |
| 미래 병목 후보 | 미래 후보와 검토 중인 변화를 분리. 산업·제품·수요/공급 역할·예상 시기·검증 상태, 검색·필터·페이지 이동·상세 |
| 판단 근거 | 제품 탐색·원문 검토·공식 표의 변화 549개. 실제 인용·앞뒤 문맥·해시·좌표 대조, 표의 두 시점 행·셀 대조, 전체 조회 자료 다운로드 |
| 자동화 현황 | 수동 수집 2회, AI 자동 판독 중단, 과거 세 시험의 생성·응답·HTTP/근거 검증 실패, 연구 검토, 수집 실패 12건, 접근 표시 자료 6건 격리, 대기·호출·토큰·비용 |

사용자 설명과 조작 문구는 한국어다. 제품명·고객명·인용문·공식 표 값은 원문 그대로 유지하며 원문 표기임을 알린다. 번역문을 새 근거로 만들지 않는다.

## 실제 연결 자료

- 기본 DB: `var/v4/cross-industry/ledger/v4.sqlite3`. 실제 SQLite의 `events`, `runs`, `documents`를 읽는다. 공통 근거의 수정 기록은 ID별 마지막 버전을 조회하며 549개를 1,098개로 중복 계산하지 않는다.
- 새 체크아웃에서 기본 DB가 없으면 `docs/v4/cross-industry/research-snapshot.sqlite3.gz`를 `verification.json`의 해시와 확인한 후 별도 `var/v4/dashboard/<hash>.sqlite3`로 복원한다. 기존 DB가 잘못되거나 사용자가 지정한 DB가 없으면 가짜 빈 DB로 대체하지 않고 오류를 낸다.
- 고정 판독 범위·산업 힌트·미래 후보 집계: `docs/v4/cross-industry/analysis.json`. 실제 DB의 현재 근거 목록과 과거 평가 범위를 구분한다.
- 자동화 설정과 이번 수집의 API 사용량: `docs/v4/PROGRESS.json`의 `cross_industry`. 과거 API 실험 누적량이나 현재 프로세스 상태를 뜻하지 않는다.
- 공식 표: 기존 `docs/v4/path-comparison/structured-native/`의 2026년 6·7월 EIA 원본. 기존 `structured_changes.snapshot` 파서를 재사용한다. 파일 버전별 파싱 결과를 캐시한다.

현재 연결값: 근거 549개 = CPU 탐색 315 + 별도 AI 원문 검토 23 + 기존 EIA 보고 변화 211. 본문 40개, 부분 판독 110개 문서의 58,488/601,012자(9.73%), 대기 URL 295개. 전체 본문 확보 표시는 첨부·표를 포함한 전체 내용 판독을 뜻하지 않는다.

저장된 변화 신호(S1) 표기는 14개이며 별칭 미통합의 과거 연구 사건이다. 고유한 미래 병목 후보 수가 아니다. 새 12~36개월 후보 집계 S1/S2/S3는 0/0/0이다. 화면은 새 후보를 만들거나 수급 근거를 임의로 결합하지 않는다. 예상 병목 시기와 독립 적격 공급 근거가 없는 곳은 미확인으로 표시한다.

## 실행

저장소의 기존 가상환경에서 실행한다. 서버는 화면 조회만 제공하며 프로세스는 환경 재시작 뒤 다시 실행해야 한다.

```bash
cd /workspace/bottleneck-control-tower
.venv/bin/python -m bct.v4.dashboard --repo . --port 8765
```

실행한 컴퓨터의 브라우저에서 `127.0.0.1:8765`를 입력한다. 이 주소는 공개 배포 주소가 아니다. 기본 인터페이스는 로컬 전용이며 같은 컴퓨터에서만 접근한다. 외부 공개·호스팅·운영 화면 전환은 하지 않았다.

다른 **기존 V4 연구 DB**를 확인하려면 `--database /absolute/research/v4.sqlite3`를 명시한다. DB와 연결된 연구 보고서가 같은 연구 범위인지 확인해야 한다. 임의 운영 DB로 연결하지 않는다.

자료 확인 API는 `/api/dashboard`, `/api/evidence/<기록 ID>`, `/api/export`, `/api/health`다. POST/PUT/DELETE는 거부한다. 파일 제공은 화면 파일 세 개로 제한한다. DB·비밀키·원본 HTML 파일은 HTTP로 공개하지 않는다. 외부 스크립트·폰트 요청, AI 호출, 수집 실행 버튼은 없다.

## 실제 검증

- 관련 Python: `tests/test_v4_dashboard.py tests/test_v4_cross_industry.py` **38 PASS**. 실제 백업 복원, 549개 수정 중복 제거, 23개 검토 사건의 원문 대조, 표 두 시점 대조, 잘못된 인용/해시/좌표/URL 거부, 없는 DB·변조 백업·연결 오류, 쓰기 차단·경로 제한을 검사했다.
- 기존 UI: `tests/test_readable_view_model.js tests/test_future_ui_clarity.js` **8 PASS**.
- 실제 Chromium: **12개 검증 시나리오 PASS**, 브라우저 실행 오류 0. PC 1440×1080, 휴대폰 390×844와 320×720. 작은 휴대폰에서 발견된 메뉴 가로 넘침을 수정하고 다시 검사했다.
- 네 화면과 상세·앞뒤 문맥·식별 정보, 검색·산업/역할/검토 상태 필터·초기화·이전/다음·빈 결과·Esc·닫기, 다운로드 실제 파일, 새로 읽기·첫 연결 실패·갱신 실패 후 복구를 검사했다. 실패 응답은 브라우저 시험에서만 주입했으며 연구 원문이나 결과를 바꾸지 않았다.
- 원문 링크는 브라우저의 새 탭과 저장 URL 목적지를 확인했다. 외부 사이트 응답을 재수집한 검증은 아니다.
- 연구 DB, 기존 운영 UI 네 파일, 운영 Actions는 브라우저 시험 전후 해시가 같다. 증거: `BROWSER_RESULTS.json`.
- 웹 정적 파일 세 개가 배포용 Python 패키지에 포함되는지 로컬 wheel 빌드로 확인했다. 운영 배포는 하지 않았다.
- 기존 가상환경에는 빌드용 setuptools가 없어 첫 wheel 명령이 실패했다. 추가 설치 없이 이미 준비된 시스템 Python의 setuptools/wheel로 `python -m pip wheel --no-deps --no-build-isolation --no-index --disable-pip-version-check . --wheel-dir var/v4/dashboard/wheels`를 실행해 빌드와 세 정적 파일 포함을 확인했다.
- 환경 설정 초안의 `start_skill`에 검증된 시작 명령·읽기 전용 점검·재시작·보존 범위를 저장했다. 기존 설치 스크립트·네트워크·비밀키는 변경하지 않았다. 초안 저장은 새 환경 게시나 운영 배포가 아니다.

브라우저 검증을 다시 실행할 때는 이미 설치된 시스템 Python Playwright와 Chromium을 사용한다. 일반 기능시험에 브라우저나 CPU 모델 설치를 강제하지 않는다.

```bash
python tools/v4_dashboard_browser.py
```

## 작동 화면

| 화면 | PC | 휴대폰 |
|---|---|---|
| 한눈에 보기 | [실제 화면](screenshots/overview-desktop.png) | [실제 화면](screenshots/overview-mobile.png) |
| 미래 병목 후보 | [실제 화면](screenshots/candidates-desktop.png) | [실제 화면](screenshots/candidates-mobile.png) |
| 판단 근거 | [실제 화면](screenshots/evidence-desktop.png) | [실제 화면](screenshots/evidence-mobile.png) |
| 자동화 현황 | [실제 화면](screenshots/automation-desktop.png) | [실제 화면](screenshots/automation-mobile.png) |
| 원문 상세 | [실제 화면](screenshots/evidence-detail-desktop.png) | [실제 화면](screenshots/evidence-detail-mobile.png) |

[공식 표 두 시점 대조 화면](screenshots/structured-detail-desktop.png)

## 남은 범위

- 공개 접속 주소·운영 배포·실시간 프로세스 감시·새 수집/AI 실행·알림은 제공하지 않는다. 현재 UI는 실제 저장 기록과 명시된 설정을 조회한다.
- 새 미래 후보의 개별 상세 연결은 해당 후보와 독립 수급·기간 근거가 실제 생성되어야 검증할 수 있다. 현재는 후보 0건 상태와 기존 연구 사건 상세를 실제 검증했다. 데이터를 가정해 양성 후보 화면을 PASS 처리하지 않았다.
- 원문 인용 일치는 의미 정확도·판독 성능·미래 예측 적중을 뜻하지 않는다. AI 자동 판독·Shadow는 계속 보류한다.
- 새 Groq 요청 0, 토큰 0, API 비용 0원. Codex 플랫폼 사용량·비용은 별도이며 이 앱에서 조회할 수 없다.

현재 재개점은 연구 결과를 이 화면에서 확인하면서 기존 295개 미시도 URL·제품/의미 검토 큐를 진행하는 것이다. 화면을 열거나 새로 읽는 동작이 수집·분석을 시작하지 않는다.
