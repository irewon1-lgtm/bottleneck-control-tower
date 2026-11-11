# BCT V4 전체 파이프라인 진단·복구 결과

작업 ID `BCT_V4_FULL_PIPELINE_DEBUG_20261111`. 계획 `BCT-V4-Q-1.0`의 Q1 부분 완료·Q2 연구 부분 완료·Q3 적격쌍 차단 및 Q1~Q7 기준을 유지한다. 기준 개발 SHA `23a0615f1a10f2b938cb2b5401706a1995b4d4f2`, 운영 main `28d0b8c648c0218ab2e74a1fa04ca8d63e659933`. 전체 완료 판정은 **BLOCKED**다. 확인된 개발 결함은 수정·검증했으나 운영 릴리스·CPU 설정/캐시·최신 암호화 DB 복원·실제 독립 선행 성능은 완료하지 않았다.

Objective Lock, 12~36개월 범위, 최초 발견 원장, 기존 정답/HOLDOUT, 원문/운영 DB, CPU 실행 pin 및 S2/S3 승격 조건은 보존했다. 새 모델·키·유료 API·서버는 추가하지 않았다. 모든 복원/재생 쓰기는 임시 복사본에서 수행했다.

| 기능 | 수정 전 | 확인된 원인 | 수정 후 | 실제 검증 |
|---|---|---|---|---|
| 자동 스케줄 | FAIL / SKIPPED | 본문 릴리스 검증 불일치; CPU 조건 미충족; Q1/Q2는 원래 수동 | BLOCKED | 등록 27개, main 정의 16개·개발 18개; 최근 7일 259회. 실제 예약 운영 전체 정상화 아님 |
| RSS 수집 | PASS / FAIL | 수집·저장 작동; 최신 125개 중 ESA 7개 404, DOE 6개 통신, USGS 1개 빈 피드 | PASS / FAIL | 성공 실행 42회 신규 1,521행·중복 43,633행. 최신 신규 7행·111개 피드 성공/14개 실패. 출처 장애 유지 |
| 공식 정량자료 수집 | BLOCKED / NOT_RUN | Q1/Q2 정기 실행 없음; 최신 월별 원장 복호화 불가·일부 출처 접근/의미 검증 공백 | BLOCKED | 이전 Git anchor 실제 복원 후 38,046 숫자/21,916 물리량/42,601 버전 재계수. M3/G17/EIA 메타데이터 HTTP200은 실제 갱신 증거 아님 |
| 원문 확보 | PASS / BLOCKED | 선행자료 본문 수집은 작동; 일부 provenance HOLD·대형 전체 캐시 복원 실패 | PASS / BLOCKED | 성공 수집 40회의 신규 검증 문서 합계 492. 저장 HTML 1건 REPLAY 통과; 모든 출처·모든 형식의 최신 원문 전수 검증 아님 |
| CPU 판독 | SKIPPED | 현재 변수 조회 403으로 정확한 false 조건 불명; 필수 runtime/bridge 캐시 0개 | BLOCKED | 43회 모두 job SKIPPED, 신규 추론 0. 기존 1,277창 영수증 복원과 새 판독 실행을 구분 |
| AI 보조 판독 | SKIPPED | OPENAI_API_KEY 없는 경로에서 녹색 종료; 결과/저장 상태 미분리 | PASS / SKIPPED | 결과 영수증·실패 분류·저장 재조회 회귀 통과. 실제 15회는 판독/저장 모두 SKIPPED, 분석 0. 키 추가·유료 호출 없음 |
| 제품·사건 추출 | FAIL | 모델과 설명 명사를 별개 제품으로 취급; 명시적 주문 목록 연결 누락 | PASS / BLOCKED | 같은 FOX-XP/Sonoma 2문장 TP/FP/FN 0/1/2→2/0/0. 기존 6문서 제품 25개 표본은 1/4/24→1/4/24. 전체 정확도 개선 PASS 아님 |
| 수요·공급 연결 | FAIL / BLOCKED | 5필드 TARGET 누락 조용한 탈락; scalar 적격쌍의 source-bound graph 계약 없음 | PASS / BLOCKED | 59개 실제 사건 모두 ID/첫 차단/부수 누락 추적. 실제 완성쌍 0. 합성 적격 시점쌍만 forecast 1건; 불완전 공급은 SUPPLY_UNKNOWN |
| 연구 DB 저장·복원 | BLOCKED | 최신 월별 generation6는 암호화; 현재 셸에 기존 암호 미전달 | PASS / BLOCKED | 기존 Git 정량/CPU 체크포인트 8테이블 및 새 프로세스 복원 PASS. 최신 generation6 복원·재계수 BLOCKED; 빈 DB 대체 없음 |
| REVIEW_LEAD | FAIL / SKIPPED | 전체 캐시 ZIP의 evaluations 압축 해제로 디스크 고갈; 일부 provenance/입력 없음 | PASS / NOT_RUN | 필요한 capture/raw만 제한 복원하도록 수정. 실제 저장 자료 REPLAY 1건 HOLD·기존 6,046파일 보존. 수정 후 운영 실행 NOT_RUN; 신규 의미 검토 완료 0 |
| 최종 후보 판정 | BLOCKED | 실제 적격 독립 수급 근거 미완성; 운영 본문 경로도 검증에서 중단 | PASS / BLOCKED | 보류·차단 기능 회귀 PASS. 실제 독립쌍 0, 신규 적격 S2/S3 0/0. 기능시험을 미래 예측 성공으로 세지 않음 |
| 대시보드 갱신 | PASS / BLOCKED | Pages는 개발 코드의 검증된 정적 연구 스냅샷 사용; 최신 RSS/암호화 연구 상태 자동 결합 없음 | PASS / BLOCKED | 수정 전 배포 23a0615, 이번 실제 배포 09cbdf2·HTTP200·1,703 상세·새 전체 진행 기록 확인. 표시 연구 시점은 10월14일 유지; 실시간 연구 DB 갱신 아님 |

## 실제 자동 실행과 단계 처리량

기간은 GitHub에서 조회한 2026-11-04 이후부터 최신 2026-11-11 02:14 UTC 실행까지다. 수동 실행은 0회다. API 녹색 합계와 실제 처리량을 분리했다.

| 워크플로 | SUCCESS | FAIL | SKIPPED | 취소 | 실제 결과 |
|---|---:|---:|---:|---:|---|
| RSS live environment check | 42 | 1 | 0 | 0 | 성공 실행 신규 1,521·중복 43,633; 실패 1회는 GitHub `fatal error in commit_refs_rules` 저장 거부 |
| New precursor evidence acquisition | 40 | 1 | 1 | 1 | 신규 검증 문서 492; 추가 독립 원문 0·완성 TARGET 0; 실패는 대형 캐시 압축 해제 디스크 고갈 |
| Future bottleneck body candidates | 0 | 57 | 1 | 0 | 57개 실패 로그 모두 `validated code/test file set changed or missing`; 본문 처리 전 차단 |
| V4 CPU private research consumer | 0 | 0 | 43 | 0 | job 실행 0·신규 CPU 판독 0; 조건값 현재 조회는 403 |
| RSS AI annotation | 15 | 0 | 0 | 0 | annotation/save는 15회 모두 SKIPPED; 실제 AI 판독 0 |
| REVIEW_LEAD SHADOW intake | 42 | 1 | 0 | 0 | 실제 intake 39회/578 HOLD/703 provenance skip; 녹색 3회는 intake 자체 SKIPPED |
| BCT read-only evaluation observer | 14 | 0 | 0 | 0 | 읽기 전용 관측과 별도 평가상태 저장; 판독·수집 작업 아님 |
| 합계 | 153 | 60 | 45 | 1 | 259회, 녹색 워크플로 유형 5개 중 AI는 실제 분석 0 |

개별 SKIPPED 2회는 RSS 저장 실패 직후 생성된 수집/본문 job으로 실행 단계가 없으며 상위 성공 조건과 일치한다. 전체 triggering payload는 API에 없어 원인을 더 좁혀 단정하지 않았다. 취소된 수집 42224871845는 기존 캐시 복원 단계에서 취소됐고 수집/저장은 시작하지 않았다. 취소 주체/사유는 확보 로그 밖의 정보다. [OTHER_NONRUNS.json](OTHER_NONRUNS.json)에 실제 단계 상태를 남겼다.

실제 기능 실행이 확인된 자동 워크플로 유형은 **4개**(RSS·선행자료·SHADOW 보류 인계·읽기 전용 observer)다. 이 중 의미 있는 intake/관측을 수행한 성공 실행은 135회(42+40+39+14)다. 이를 135회 미래 병목 판독/예측 성공이라고 해석하지 않는다. 전체 파이프라인 LIVE 왕복 성공은 0회 입증 상태다.

단계별 단위를 합산하지 않는다. RSS 1,521행 → 신규 검증 본문 492문서 → 운영 신규 CPU/유료 AI 판독 0 → 완성 TARGET 0 → 검증 가능한 실제 독립 수급쌍 0 → 신규 적격 S2/S3 0/0이다. 이 화살표는 서로 다른 실행 영수증의 관측 합계이며 1:1 문서별 손실률이 아니다. 운영 영수증에 신규 제품 추출 개수·각 본문 저장 ACK의 독립 집계가 없어 그 수는 UNKNOWN으로 남긴다. SHADOW 578건은 검토 입력/보류 레코드이며 고유 수급 사건·완료된 의미 검토가 아니다. 703회 provenance skip과 40회 source-hold 표시는 반복 관측을 포함한다.

별도 실제 저장 원문 **REPLAY/BACKFILL 1건**은 raw/본문 해시 확인 → 현재 결정론적 추출 → 검증된 handoff 1건 → 연구 source 저장 1건 → SQLite 8테이블 백업 → 새 읽기 전용 프로세스 복원 → 복사 REVIEW 상태 HOLD 1건 → 공급검토 사건 1건/strict 후보 0건까지 실행했다. 신규 LIVE나 CPU/AI 판독으로 집계하지 않았다. 직접 과거 메타데이터를 넣은 두 보류 사례도 보존했다.

## 수정한 결함과 동일 입력 비교

수정은 **6개 결함군**이다. ① 일반 모델/물리 명사 identity 연결 ② 명시적 주문 목록 연결 ③ 불완전 TARGET의 조용한 탈락 추적 ④ 구조화 precheck 전달 누락의 명시적 source-binding 차단 진단 ⑤ RSS AI 실제 결과·저장 상태 분리 ⑥ REVIEW 전체 캐시 무제한 압축 해제. ④는 실제 전송 어댑터 구현이나 실제 적격쌍 복구가 아니다. 릴리스 guard·CPU 비활성 조건·공식 자료 접근 제한은 수정 완료 수에 넣지 않았다.

개발 입력/동결 정답을 바꾸지 않았다. 감사의 두 원문 문장에서는 TP/FP/FN 0/1/2→2/0/0이며, 이미 사용된 기존 6문서·25제품 표본은 1/4/24로 전후 동일하다. 누락과 오탐이 여전히 있으므로 전체 제품 판독 정확도 PASS를 주장하지 않는다. 동일 2문장 재생의 단회 시간은 수정 전 0.0152초·후 0.0127초(압축/SQLite/Git 입출력 포함)였다. 이 작은 실행은 처리량/성능 벤치마크가 아니다.

Python 전체 회귀 **1,828 PASS·1 SKIPPED**, JavaScript **5 PASS**. SKIPPED는 실제 pre-public holdout 부재다. 원래 가상환경에서의 19실패/3오류는 미설치된 기존 openpyxl 의존성과 GPG/소켓 샌드박스 제약을 구분하여 해결했고, 코드 변경 도중 실행한 중간 결과의 실패도 [ENVIRONMENT_BASELINE.json](ENVIRONMENT_BASELINE.json)에 숨기지 않고 남겼다. 최종 환경에서는 위 전체 시험을 새로 실행했다. 독립 코드 검토의 주문 목록 모호성 지적을 보수한 뒤 106개 관련 시험도 통과했다.

## 남은 운영 차단과 필요한 조치

1. **본문 릴리스**: 검증 SHA `1e4ec2aa…`는 235개 파일, 현재 main은 238개다. CPU 워크플로 3개 추가와 `ui-pages.yml` 변경이 실제 미검증 차이다. guard는 정상 차단 중이며 삭제/예외 처리하지 않았다. 기존 재검증 도구는 옛 `14c2de54…`와 세 파일 추가만 가정하여 현재 트리를 검증하지 못한다. 정확한 의도 운영 트리를 고정하고 기존 Gates 0~6 실제 실행 후에만 새 run/artifact/digest 영수증을 연결해야 한다. Gate5의 운영 큐 쓰기는 이 작업에서 실행하지 않았다.
2. **증거 수명**: 기존 release artifact `11783493914`는 **2026-11-12 01:47:21 UTC 만료**다. 원래 fixed230 run `37790294699`의 artifact 목록은 이미 비어 있다. 허용된 무결한 원문 사본을 확보하지 못하면 해당 실제 gate는 BLOCKED다. 과거 PASS 재기입으로 대체하지 않는다.
3. **CPU 설정**: GitHub Settings → Secrets and variables → Actions → Variables에서 `BCT_V4_CPU_CODE_SHA`, `BCT_V4_CPU_RESEARCH_ENABLED`를 소유자가 확인해야 한다. 현재 조회 403이므로 어느 값이 불일치하는지 단정하지 않는다. 운영 소비자의 승인 pin은 `221fa92b1cbff8950716ec373eac793ca340c873`이다. 문서/이번 수정 SHA로 임의 변경하지 않는다. runtime 및 encrypted bridge 캐시가 현재 0개이므로 **변수만 ON으로 바꾸지 말고**, 기존 승인 runtime과 최신 durable 상태에서 복원·검증한 뒤 활성화해야 한다. 새 모델 설치/키 발급 없음.
4. **최신 연구 DB**: 기존 Secret `BCT_V4_STATE_PASSPHRASE`가 전달되는 승인된 Actions의 읽기 전용 복원 문맥에서 월별 generation6를 재검증해야 한다. 로컬 셸에 값이 없는 사실은 Repository Secret 자체 부재를 뜻하지 않는다. 재발급·채팅 공유를 요구하지 않는다. 이전 Git anchor/CPU 복원 PASS는 최신 generation6 PASS가 아니다.
5. **자료/검토/화면**: 14개 최신 실패 피드, Q1/Q2 수동 상태, provenance skip, scalar→graph의 근거 계약 부재, 정적 화면의 오래된 연구 스냅샷은 남아 있다. 검증된 새 연구 자료가 없으면 `NO_NEW_INPUT`과 BLOCKED를 구분하고 신규 후보를 만들지 않는다. 화면 코드/진행 영수증 갱신만으로 최신 연구 DB 동기화를 주장하지 않는다.

운영 반영은 이 개발 수정의 영향 파일을 검토하고 정확한 대상 트리에 대한 게이트를 다시 만족시킨 뒤 별도 main PR/승인 절차로 진행한다. main 강제 push, 릴리스 검증 우회, 기존 연구 DB 변경은 수행하지 않았다. 개발 push/CI와 실제 main 예약 운영 PASS는 별개다.

## 증거와 완료 기준

- 현재 브랜치/실행: [GITHUB_STATE.json](GITHUB_STATE.json), [WORKFLOW_CONTRACTS.json](WORKFLOW_CONTRACTS.json), [SEVEN_DAY_THROUGHPUT.json](SEVEN_DAY_THROUGHPUT.json), [FUTURE_FAILURES.json](FUTURE_FAILURES.json).
- 장애/재현: [ACTIONS_RELEASE.md](ACTIONS_RELEASE.md), [EXTRACTION.md](EXTRACTION.md), [LINKAGE.md](LINKAGE.md), [RSS_AI.md](RSS_AI.md), [COLLECTOR_CONNECTIONS.md](COLLECTOR_CONNECTIONS.md).
- 복원·검토·배포: [STORAGE_DASHBOARD.md](STORAGE_DASHBOARD.md), [STORAGE_DASHBOARD.json](STORAGE_DASHBOARD.json). [기존 감사](https://github.com/irewon1-lgtm/bottleneck-control-tower/tree/2aaaa91f17ea1c29eb7a36c4cd26783e405610b9/docs/v4/audits/zero-pair-20261017)의 ROOT_CAUSE_REPORT/STAGE_LOSS/CASE_EVIDENCE/MINIMAL_FIX_SPEC를 실제 코드와 대조했다.
- 실제 실패: [본문](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42944587807), [CPU skip](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42942892160), [최신 RSS](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42939431146), [최신 선행자료](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42939818925), [최신 REVIEW](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42942892140), [배포 화면](https://irewon1-lgtm.github.io/bottleneck-control-tower/).

**코드 기능 정상화:** 확인된 6개 범위 개발 시험 PASS, 구조화 실근거 전달/전체 추출 정확도 BLOCKED. **실제 예약 자동 운영 정상화:** BLOCKED. **미래 병목 예측 성능 입증:** BLOCKED. 첫 실제 예약 신규 판독·검증·영속 저장 이후의 Q6 7일과 Q4 독립 선행성은 시작/완료 처리하지 않았다. 개발 코드 커밋은 `09cbdf297c7e3a7398cd9296d9d83483fc641e08`이다. 아래 GitHub 실제 반영 기록과 진행 원장으로 연결한다.


## 실제 GitHub 반영/배포 기록

`23a0615f → 09cbdf297c7e3a7398cd9296d9d83483fc641e08`을 `codex/bct-v4-integration`에 일반 fast-forward push했다. 병행 변경은 없었고 main `28d0b8c6` 및 운영 데이터 ref는 수정하지 않았다. 뒤따르는 기록 커밋은 이 결과와 기존 진행 원장만 반영하며 실행 코드는 바꾸지 않는다.

- [Stage0 전체 CI 42983011577](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42983011577): SUCCESS. 실제 로그 Python 1,828 PASS·1 SKIPPED; GitHub Node 결과 34 PASS·0 FAIL(로컬 Node는 5개 파일 PASS로 집계). 조건부 과거 fixed230 복원/QA는 해당 브랜치 조건 밖이라 SKIPPED이며 최신 원문 검증으로 세지 않는다.
- [대시보드 검증 42983011670](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42983011670): SUCCESS. Push용 verify job 통과; 수동 전용 readonly-release-revalidation job은 SKIPPED. 운영 Gates0~6 재검증 PASS가 아니다.
- [실제 Pages 연쇄 배포 42983201374](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42983201374): build/deploy SUCCESS. 배포 manifest의 코드 `09cbdf2`, 실제 dashboard JSON 해시 일치, 1,703 상세, 새 전체 진행 기록을 HTTP200으로 재조회했다. 기존 연구 `data_at=2026-10-14T23:16:13.592709+00:00`은 그대로다.

상세 SHA·job·manifest·HTTP/hash 근거: [GITHUB_DELIVERY.json](GITHUB_DELIVERY.json). 위 3회는 이번 push 후 새로 실행된 검증/정적 배포다. 앞의 259회/135회 집계는 수정 전 조사창의 자동 실행이며 이 3회를 중복 합산하지 않는다.
