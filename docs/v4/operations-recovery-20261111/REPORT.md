# BCT V4 운영 복구 결과

작업 ID `BCT_V4_OPERATIONS_RECOVERY_20261111`. 인계 `42ee0a6ee6b0ed21228a0409aa64e973359bf65f`에서 이어 진행했다. 계획 `BCT-V4-Q-1.0`, Objective Lock, Q1~Q7 기준, HOLDOUT·정답·최초 발견·승격 기준은 보존했다. 이전 여섯 수정의 실행 파일 해시와 유효한 시험을 재사용했고, 이번에는 미실행 운영 복원·전달 경로에 실제 Actions를 실행했다.

**최신 암호화 DB, 승인 CPU runtime/bridge, 제한 REVIEW 전달, 고정230 원문 QA는 실제 실행으로 확인했다. 사용자 승인에 따라 [PR #44](https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/44)를 일반 병합했고 실제 main은 `e31743a91ab3604421ec7c35796dfda8f63dd51f`다.** 병합 시각은 2026-11-11 18:54:46 KST이며 [새 main CI](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42999153532)도 PASS다. 새 main의 전체 Gates0~6·소유자 변수 활성화·최초 신규 예약 판독/저장은 아직 완료하지 않았다.

| 기능 | 기존 상태 | 복구 결과 | 실제 운영 검증 |
|---|---|---|---|
| 운영 릴리스 Gate0~6 | FAIL | BLOCKED | 복원 요청의 잘못된 run/누락 해시를 수정. 과거 증거 ZIP 무결성 보존, 현재 후보 품질·230원문 QA PASS. 전체 새 Gate 실행/새 영수증은 미완료 |
| CPU 자동 실행 | SKIPPED | BLOCKED | 기존 승인 seed·runtime·bridge 복원 PASS. 현재 두 변수는 옛 SHA/false; 예약 신규 판독 0. 입력 캐시·RSS_RUN 전달 결함 수정은 승인된 main에 반영 |
| 최신 연구 DB 복원 | BLOCKED | PASS | 실제 generation6 암호/해시/8테이블/새 프로세스 복원·generation5 보존·원격 무변경 검증 |
| RSS 수집 | PARTIAL | PASS / BLOCKED | 공식 대체 RSS2개 수정, 임시 최신 DB에 신규20→재처리 중복20. 나머지12개 개별 BLOCKED; 수정2개는 main 반영 |
| 공식 원문 확보 | PARTIAL | PASS / BLOCKED | 저장 실제 창의 출처검증2·보류3, 고정230 원본 확인/QA. 모든 공식 출처의 최신 갱신 완료가 아님 |
| 제품·사건 판독 | PARTIAL | PASS / NOT_RUN | 기존 일반 장비·주문 추출 보수 보존, 230원문 결정론적 QA 실행. 신규 CPU 문서 판독은 NOT_RUN |
| 수요·공급 연결 | BLOCKED | BLOCKED | 실제 적격 독립쌍0 유지. scalar→source-bound 계약 부재 및 공급풀 미확인을 억지 보충하지 않음 |
| REVIEW_LEAD | 운영 미검증 | PASS / NOT_RUN | 실제 Actions 제한 복원·과거 상태 복사본 HOLD2·중복2·새 프로세스·기존 파일 보존 PASS. 의미 검토 완료0, 변경 후 운영 쓰기는 NOT_RUN |
| 연구 결과 저장·복원 | PARTIAL | PASS / NOT_RUN | 실제 기존 연구/CPU 상태 복원·동일 DB bridge 회복 PASS. 신규 CPU 연구 결과의 영속 저장은 NOT_RUN |
| 대시보드 데이터 갱신 | BLOCKED | PASS / BLOCKED | 새 코드·진행 영수증의 기존 Pages 연쇄 export 검증. 본문 연구 스냅샷10월14일은 그대로이며 최신 연구 데이터 갱신 PASS로 세지 않음 |
| 실제 전체 왕복 | NOT_RUN | BLOCKED | 수동/REPLAY 단계별 실증은 완료. 신규 자동 수집→CPU→새 비공개 결과→검토의 한 LIVE 왕복은 미실행 |

## 실제로 복구한 항목과 근거

### 최신 generation6

기존 Secret이 전달되는 기존 `official-state-read` Actions 문맥을 사용했다. 새 암호·토큰을 만들거나 값을 출력하지 않았다. 초기 실제 복원 [42988130440](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988130440)에 이어, 읽기 전용 새 프로세스/이전 세대 검증을 보강한 [42989791426](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989791426)을 정확한 개발 SHA `ab2cc04a13af13903fe980e2532a073f2a4ad7aa`에서 실행했다.

- 실제 최신 월별 generation6, 14자산/38,084,522바이트의 암호문·평문/manifest 해시 확인.
- SQLite **8테이블**, **42,601 정량 버전 / 38,046 숫자 관측 / 21,916 물리량 관측** 재계수. 숫자 행을 수급 사건으로 세지 않았다.
- 새 Python PID2262에서 계정 자격증명을 제거하고 동일 SQLite 해시로 재복원.
- generation5의 **60,049 사건 행과 metadata 전체가 generation6의 60,071행에 보존**됨을 검증.
- 복원 조회의 전후 원격 head·14자산·기존 DB 무변경. 읽기72초/검증62초, 각각120초 이내.

이는 사실 전용 capsule 복원이다. 원래 본문·인용 전체가 복원됐다는 뜻이 아니다. 이후 별도 승인 CPU bridge 회복은 동일 DB bytes를 유지한 metadata/ACK append이며, 위 읽기 전용 시험과 분리한다. 상세: [DB_RESTORE.md](DB_RESTORE.md), [DB_RESTORE.json](DB_RESTORE.json).

### 승인 CPU 실행환경과 bridge

[설정 진단42988176131](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988176131)에서 실제로 `BCT_V4_CPU_CODE_SHA=da7cb9bc1e6b99d5f4859aaeda4431dbacee03d6`, `BCT_V4_CPU_RESEARCH_ENABLED=false`를 확인했다. 따라서 현재 pin 비교와 활성화 조건이 모두 false다. 기존 Secret/전용 토큰 전달은 유효했다. 진단의 옛 `code_SHA_matches_tested_handoff=true`는 da7과 비교하는 필드여서 현재221fa 일치로 오해하지 않았다.

이번 지시가 승인 seed 복구를 포함하므로, 기존 `6dea292` seed와 동일한 모델/revision/9파일 해시/71개 고정 의존성을 확인한 뒤 [42989488936](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989488936)에서 **동일 승인 seed를 재구성**했다. 다른 모델 선택이나 실행 pin 변경은 없다. 패키지 wheel 전체의 과거 bit identity는 주장하지 않는다.

[runtime 검증42990702742](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990702742): Python3.12.15/Linux-X64, 정확한71개 버전/추가 패키지0/pip check, 모델9파일 **845,067,152바이트**·고정 SHA, payload **2,025,505,375바이트<3GiB**, immutable 실행 코드 `221fa92b1cbff8950716ec373eac793ca340c873`의 오프라인 로드 PASS. 로드8.08초·peak2,126,776KiB·신규 추론0이다.

[bridge 회복42990897783](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990897783)은 기존 private checkpoint를 읽어 같은 DB/완료 키를 CAS·ACK와 암호화 전달 캐시로 회복했다. DB/압축 checkpoint Git blob IDs와 SQLite `dc243451…`가 전후 동일하고 **1,277창/41완료 키/20검토**를 보존했다. metadata/ACK 두 커밋은 새 연구 사실로 세지 않는다. runtime cache `10344400333`의 압축 크기는1,058,256,865바이트다.

최종 [bridge freshness 회복42997763985](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42997763985)은09:45:21UTC에 완료됐다. 기존 checkpoint blob/SQLite/41완료 키를 그대로 유지하면서 ACK/history 두 커밋을 추가했고 최신 bridge cache10346946351(993,916바이트)을 생성했다. 그 관측 시점에 latest consumer와 producer가 일치했다. [CPU_FINAL_BRIDGE.json](CPU_FINAL_BRIDGE.json)에 근거를 남겼다.

후속 수동 consumer 검증이 predecessor 문맥을 바꾸므로, 활성화 전 마지막 bridge freshness 회복이 별도로 필요하다. 성공한 키·모델·인증을 무작정 다시 시험하는 것이 아니라 기존 `verify_predecessor` 계약을 유지하는 절차다. 현재 변수는 변경하지 않았고 신규 CPU 문서/문자/창은 모두0, 첫 예약 성공·7일 시작은 미완료다. 상세: [CPU_RECOVERY.md](CPU_RECOVERY.md), [CPU_RECOVERY.json](CPU_RECOVERY.json).

### 발견한 CPU 입력 결함의 최소 보수

원래 workflow는 `GITHUB_ENV`에 쓴 `RSS_RUN`을 같은 step에서 읽었다. 다음 step에서만 적용되는 값을 읽으므로 전달이 성립하지 않았다. 검증 Python과 다운로드를 이웃 step으로 분리했고, 기존 `verified_schedule`과 실행 pin은 유지했다.

또한 전체 캐시의 실제 확장 크기는 **51,460,031,534바이트**, 그중 evaluations가 **49,054,341,364바이트**였다. 원래 CPU가 불필요한 이력까지 풀었다. 새 stdlib helper는 기존 문서·raw·capture 버전 **2,402,577,107바이트**만 그대로 복원하고, ZIP digest·경로·중복·symlink·디스크·3GiB 입력/6GiB ZIP/2GiB reserve를 검증한다. 과거 미완료 source와 malformed/missing/ambiguous 처리는 기존221fa 처리기가 계속 판단한다. 날짜 필터로 과거 미완료 입력을 버리지 않는다. 전용 helper는 검토된 immutable `7d9188608a66520115727ff5daa30d13190f4958`에서 별도 sparse checkout하고 CPU 코드에는 섞지 않는다.

실제 [42995363348](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42995363348)에서 runtime을 복원한 상태로 **4,598,165,007바이트 ZIP→2.40GB 입력**을98초에 복원했다. 전후 free disk를 기록했고, 시작89,208,590,336바이트·정리 후86,765,174,784바이트였다. source 의미/DB 쓰기/추론은0이다. 상세: [CPU_INPUT_TRANSPORT.json](CPU_INPUT_TRANSPORT.json), [cpu-source-transport.json](cpu-source-transport.json).

### 실제 REVIEW 및 고정230 원문 QA

[REVIEW42990692268](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990692268): 같은 실제 ZIP에서5capture+5raw **1,074,585바이트**만 복원했다. 출처검증 문서2건/보류3건이었다. 현재 상태 복사본은 중복2건, 정확한 직전 상태 `76ba081f…`의 별도 **PRE_INTAKE_REPLAY**는 새 HOLD2건→재실행 중복2건이었다. 의미 검토 완료0·alerts0이다. 원래 파일6,046/6,040개와 두 새 프로세스 복원을 확인했으며 운영 review ref는 바뀌지 않았다. 복사본 재생을 운영 신규 검토로 세지 않았다.

동시에 사라진 옛 artifact 대신 최신 캐시 안에서 **정확한 고정230**을 찾았다. fingerprint `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec`,230본문/230raw 해시가 일치했다. 새 [42995363348](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42995363348)은 literal460파일 **41,784,646바이트**를 복사해 기존 운영 QA를 후보018f에서94초 실행했다. 후보164019b와 해당 QA/수집/추출/그래프7파일 해시가 같아 이 구성요소의 결과를 재사용한다. 원문 수정·HTTP·LIVE 쓰기는0이다.

QA는230문서→682보존 사건, 제품 필드74·규격8·지역19·고객6·공급풀0으로, 완성 TARGET/독립쌍/후보는0이었다. 이는 TP/FP/FN 정확도 시험이 아니다. 기존 6문서·25제품 점수1/4/24는 개선됐다고 보고하지 않는다. 원래 raw/hash를 보존한3건의 기존 허용 derived-view 교정도 QA 보고서에 그대로 남겼다. 이전 FOX-XP/Sonoma의 두 사례 보수와 과거 정답/HOLDOUT은 변경하지 않았다.

원문 QA 구성요소 PASS를 새로운 전체 Gates0~6 PASS로 바꾸지 않는다. 상세: [REVIEW_RECOVERY.md](REVIEW_RECOVERY.md), [REVIEW_ACTIONS_RECEIPT.json](REVIEW_ACTIONS_RECEIPT.json), [fixed230-copy.json](fixed230-copy.json), [cpu-source-gate6-qa.json](cpu-source-gate6-qa.json).

### RSS 및 실제 처리량의 단위

14개 실패 피드를 각각 점검했다. ESA7개404, DOE6개는 현재 HTML로 이동, USGS1개는 유효 RSS지만0항목이었다. 공식 페이지가 명시한 DOE techlines/blog RSS2개만 수정했다. 나머지12개는 공식 대체 XML을 확인하지 못해 BLOCKED로 보존했다.125개 이름/순서와 기존 정상111개 URL은 그대로다. 최신 실제 canonical DB의 임시 복사본9,921행에서 신규20행을 저장해9,941행이 됐고 같은 캡처를 재처리한20건은 모두 중복이었다. 발표일도 원래20항목과 일치한다. 운영 DB는 쓰지 않았다. 상세: [RSS_RECOVERY.md](RSS_RECOVERY.md), [RSS_RECOVERY.json](RSS_RECOVERY.json).

| 별도 시험/자료군 | 입력 | 다음 단계/보류 | 성격 |
|---|---|---|---|
| 고친 RSS2개 | 실제 응답20항목 | 임시 DB 신규20→재처리 중복20 | 개발의 실제 요청/저장 시험; 자동 운영 갱신 아님 |
| 저장된 운영 창 | capture5/raw5 | 출처검증2/보류3→복사본 HOLD2→중복2 | Actions REPLAY, 의미 완료0 |
| 고정230 | 원본 metadata230/raw230 | 결정론적 사건682→완성 TARGET0→독립쌍0→후보0 | BACKFILL/소스 QA |
| CPU runtime/bridge | 승인9파일/기존 checkpoint | 환경·8테이블·41완료 키 보존 | 실제 새 문서 판독0/새 결과 영속 저장0 |
| 최신 월별 DB | generation6/14자산 |8테이블·새 프로세스·generation5 이력 보존 | 실제 읽기 전용 복원 |

서로 다른 자료군을20→2→230처럼 합쳐 하나의 LIVE 왕복으로 계산하지 않는다. 실제 신규 자동 CPU 판독/저장0, 실제 검증 가능한 적격 독립 수급쌍0, 신규 적격 S2/S3 각각0이다.

## Gates0~6와 운영 승인 경계

현재 전체 Gate 상태는 **BLOCKED**다. 실제 새 operating SHA/run/artifact/digest의 일치 영수증은 아직 없으며 guard/파일 제외 규칙/기존 release receipt를 바꾸지 않았다.

| Gate | 현재 후보 전체 Gate 판정 | 확인한 부분/남은 의존성 |
|---|---|---|
|0 | NOT_RUN | 과거 checkpoint19파일/3,280cache 파일의 진짜 해시 복원은 PASS. 승인 후 새 main의 paired authoritative roots 검사는 별도 |
|1 | BLOCKED | 원격 fault probe·보존 복구·운영 projection 쓰기를 포함. 정확한 대상 diff·CAS/원복 범위 검토 후 실행 |
|2 | NOT_RUN | 이번14피드 접근 및 고정 원문 검증과 전체 Gate 실행을 구분. 같은 실패를 조건 변화 없이 반복하지 않음 |
|3 | NOT_RUN | 실제 보존 inventory 복원은 PASS; 새 전체 Gate 문맥의 source 관측/상태 검증은 미실행 |
|4 | NOT_RUN | 기존74개 source-version 보강/검색의 새 실행은 미실행; 과거 증거 소급 PASS 금지 |
|5 | BLOCKED | 기존 Stage5 Qwen runtime·최대50개 신규 native 호출·candidate/tracking 원자 게시를 포함. 복원한 GLiNER runtime으로 대체하지 않음 |
|6 | BLOCKED / PASS | 후보 회귀·품질·고정230 source 구성요소 PASS. 앞 Gate와 묶인 새 전체 Gate6·영수증은 미완료 |

기존 artifact11783493914는 **2026-11-12 01:47:21 UTC(10:47:21 KST)** 만료다. 원본45,073,105바이트/SHA256 `00ac5d87109c6c365f9d2a19fe2f15a83919012ed012222f9b4932fd5d70243a`·CRC·inventory를 검증해 `/tmp` 및 Git-ignored `var/v4/operations-recovery-20261111/preserved/`에 보존했다. 로컬 사본은 새 원격 릴리스 영수증이 아니며 원문을 새 공개 저장소에 복제하지 않았다.

운영 후보17파일은 새 raw DB/schema/모델을 main에 넣지 않는다. [MAIN_CANDIDATE.json](MAIN_CANDIDATE.json)에1,013Python PASS·기존 독립 holdout1SKIP·JS34PASS와 source QA 재사용 해시가 있다. [후보 PR CI](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42996830589)도 PASS다. 개발 `ab2cc04`(읽기 전용 DB proof), `bd9ee61`(피드/검증), `7d91886`(immutable helper), `fbbc4d0`(CPU 입력 전달)까지 단계별 push했다.

main 반영은 사용자 승인 후 일반 merge만 사용한다. 승인된 새 main SHA를 확정한 뒤 Gates를 실행하고 진짜 run/artifact/digest를 연결한다. Gate1/5 쓰기 전에는 해당 시점의 paired root SHA와 영향 ID/필드를 고정하고 원복을 검토한다. 코드 원복은 PR의 일반 revert이며 force push/빈 DB 초기화가 아니다. 데이터 보상 게시에는 기존 CAS·보존 병합으로 동시 추가/원본/최초 발견/검토 이력을 유지해야 한다. PR44는 명시적 사용자 승인 후 일반 병합했다. main 강제 push·검증 우회·가짜 새 release receipt는0이다.

## 소유자가 해야 하는 항목

1. **운영 코드 승인 완료:** 사용자가 “PR #44 main 반영 승인”을 전달했고 일반 병합 완료. 새 main `e31743a`에서 Gate workflow가 만료된 고정230 artifact run37790294699를 여전히 참조하는 후속 차단을 발견했다. 이미 검증한 동일 원문의 복원 경로만 별도 PR로 보수하고 승인받을 예정이다. 이를 알면서 운영 쓰기 Gate를 먼저 실행하지 않았다. 승인 없는 merge는 실행하지 않는다.
2. **CPU 변수:** PR 적용과 마지막 유효 bridge 확인 뒤, GitHub 저장소 **Settings → Secrets and variables → Actions → Variables**에서 기존 항목의 연필/Edit를 눌러 `BCT_V4_CPU_CODE_SHA=221fa92b1cbff8950716ec373eac793ca340c873`, `BCT_V4_CPU_RESEARCH_ENABLED=true`를 저장한다. 현재 앱의 Variables 권한은403이므로 대신 변경하지 못했다. 실행 pin 자체·Secret은 변경하지 않는다. 승인/최신 bridge 조건 전에는false를 유지한다.
3. 수동 consumer 진단 또는 미게시/생략 consumer 실행으로 predecessor가 달라지면, 기존 **Actions → V4 CPU private research consumer → Run workflow → main → purpose=bridge-recover**의 유효 회복이 먼저 필요하다. 다른 모델 설치나 새 키는 필요하지 않다. 첫 실제 예약의 신규 판독·검증·비공개 ACK·복원이 성공하기 전까지 운영 PASS/7일 시작으로 세지 않는다.

**개발 코드 정상화:** 확인된 범위 PASS, 개발 push/PR44 승인·main 일반 병합 완료. **운영 자동화 정상화:** BLOCKED(고정230 복원 경로·조건부 변수·새 main Gate·실제 신규 예약 왕복 대기). **미래 병목 예측 성능:** BLOCKED(적격 독립 수급 근거/독립 선행 평가 부재). 실패/대기 중에도 원래 DB·원본·완료 키·검토 이력은 유지했고 빈 상태로 성공 처리하지 않았다.
