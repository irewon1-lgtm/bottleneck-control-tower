# P0 CPU runtime·비공개 bridge 복구 — 2026-11-11

작업 `BCT_V4_OPERATIONS_RECOVERY_20261111`. 기존 `BCT-V4-Q-1.0`, Objective Lock, Q1/Q2 PARTIAL, 독립 평가/선행성 BLOCKED와 S gate를 유지한다.

**동일 승인 runtime·비공개 checkpoint/bridge 복구와 제한된 source 입력 전송의 실제 검증은 PASS다. 전체 ZIP 확장 문제를 고친 PR44는 사용자 승인 후 main `e31743a`에 반영했다. 소유자의 기존 변수 설정과 최초 실제 예약 판독은 아직 미완료다. 정기 CPU 신규 판독은 NOT_RUN이며 7일 NOT_STARTED다.** 새 모델/다른 revision/다른 실행 pin으로 대체하지 않았다. 복구 성공을 AI 채택·S2/S3·실제 선행 성능으로 올리지 않는다.

## 실제 실행 증거

| 실행 | 실제 결과 |
| --- | --- |
| [기존 설정 관측 42988176131](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988176131) | 기존 토큰 전달/형식 유효, 전달 암호 정확히 64자. CODE=`da7cb9b…`, ENABLED=`false`. 값 미출력·설정 변경 없음 |
| [동일 승인 seed 재구성 42989488936](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989488936) | 기존 immutable seed `6dea292`, Python 3.12.15, 같은 71개 lock/revision/모델 9개 SHA로 main 캐시 재구성 PASS |
| [복원 runtime 검증 42990702742](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990702742) | 개발 `bd9ee61`, 정확한 71개 distribution/version·추가 package 0·pip check PASS, 9개 SHA/크기, immutable `221fa92`의 offline load health PASS |
| [기존 영속 CPU bridge 복구 42990897783](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990897783) | main의 기존 경로/실행 pin `221fa92`, 실제 비공개 복원·새 프로세스 8개 테이블·41개 완료 키 중복 방지·암호화 cache PASS. 신규 판독 0 |
| [최종 bridge freshness 갱신 42997763985](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42997763985) | 마지막 source 검증 이후 실제 선행 run 일치를 다시 확보. DB/완료 키 동일, 새 ACK/cache PASS. 09:45:21Z 완료 시점의 준비 증거이며 미래 영구 준비 보장은 아님 |

초기에는 Actions cache 0개, 과거 seed/preflight artifact 0개였고 `/workspace`, `/tmp`, 기본 Hugging Face cache에도 기존 runtime binary가 없었다. 처음에는 재설치 금지를 넓게 해석해 seed까지 보류했다. 이후 사용자의 구체적인 “정상적인 과거 캐시·승인된 seed·영속 상태” 복구 지시를 검토해 **이미 승인된 동일 모델/고정 설정의 재구성**을 한 번 실행했다. 과거 venv/wheel 전체의 bit-identical 복원으로 표현하지 않는다.

모델은 `fastino/gliner2-base-v1`, revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`다. seed `6dea292`, 실행 pin `221fa92`, 현재 개발의 lock/manifest와 bootstrap·파일 검사·probe·CPUExtractor 로직은 같다. lock 71개는 모두 정확한 버전 고정이다. wheel 해시는 고정돼 있지 않으므로 실제 복원 후 전체 distribution과 의존성 검사를 추가했다. 실패 시 버전 완화나 다른 모델 fallback은 없다.

## 정확한 runtime·cache 수치

| 항목 | 실제 수치 |
| --- | --- |
| 고정 모델 파일 9개의 재다운로드 body 합계 | **845,067,152바이트** |
| 생성된 모델 manifest 포함 모델 tree | 845,068,741바이트 |
| runtime 전체 payload | **2,025,505,375바이트**; 3GiB 미만 |
| 새 main runtime cache | ID `10344400333`, **1,058,256,865바이트** |
| 최신 암호화 CPU bridge cache | ID `10346946351`, **993,916바이트**, producer run `42997763985` |
| offline 모델 load health | 8.08초, CPU 4 threads, peak RSS 2,126,776KiB, 추론 0, 모델 다운로드 0 |
| pip 패키지 다운로드의 정확한 압축 body 바이트 | UNKNOWN: 기존 seed 로그가 정확한 전송 바이트를 보존하지 않음 |

기존과 같은 runtime cache key:

```text
v4-cpu-runtime-Linux-X64-3.12.15-fff880f684241e7320bcb1f19eecf3f5ad9a32f15f730cc2351aae63c13bda10
```

requirements SHA-256은 `99aa48b5c7381c3c451769f8fbb8b21ef4f745a8e7b7c5dbdb15deb0312a8bb9`, model manifest SHA-256은 `5588cb168c4dcdac419b2a1ea269c2d5bbcc94d18e760949d2ac48b2bc43384b`다. verifier는 cache miss에서 중단하고 설치하지 않는다. health step에는 Secret/token을 전달하지 않았고 원문·큐·DB·추론을 실행하지 않았다.

## 기존 DB·처리 이력 보존

CPU 비공개 ref는 첫 복구에서 `1ea13ed1ff81b75f8c6216177c34bb04c0e088b5`→`f42c11aefa357a271bd8a8726c4e6fddaa55366a`, 최종 freshness 갱신에서 →`b20f3e4ecd3e2b9f2bf0222d5f56199d1965decc`로 이동했다. 각 두 개씩 총 네 개의 checkpoint/ACK 메타데이터 commit만 추가했다. **checkpoint JSON과 압축 DB의 Git blob ID가 모든 갱신 전후 동일**하다. SQL/사실/기존 원문을 고치지 않았다.

SQLite SHA-256은 전후 `dc2434510ec58e247c838353ad7c8d95f7f127161431ec55e4db1849f80fa7db`이며 새 프로세스에서 8개 테이블을 검증했다. 기존 1,277창·4,905표기·1,326제품 제안·20과거 검토·41완료 키를 보존했다. 원문 0, 새 source 복제 0, 새 CPU 창 0, 자동 승격 0이다. 공식 정량 monthly generation6과 CPU state ref는 서로 다른 상태이며 섞지 않았다.

## 남은 실제 조건과 소유자 조치

bridge 복구에서도 다음 기존 변수 값을 다시 관측했다.

| 기존 변수 | 현재 | 필요한 값 |
| --- | --- | --- |
| `BCT_V4_CPU_CODE_SHA` | `da7cb9bc1e6b99d5f4859aaeda4431dbacee03d6` | `221fa92b1cbff8950716ec373eac793ca340c873` |
| `BCT_V4_CPU_RESEARCH_ENABLED` | `false` | `true` |

따라서 research job의 두 변수 조건은 아직 false다. 기존 Variables API 403 증거를 재사용했으며 실패한 읽기/쓰기를 반복하지 않았다. 정상 Secret과 실행 pin은 변경하지 않았다. source transport 수정/실제 검증/PR44 검토 전에는 변수를 활성화하지 않는다. 그 조건을 충족한 후 소유자는 [Settings → Secrets and variables → Actions → Variables](https://github.com/irewon1-lgtm/bottleneck-control-tower/settings/variables/actions)에서 **기존 변수 두 개만** 위 필요한 값으로 편집할 수 있다. runtime/영속 상태 복구 전제는 위 실제 실행으로 충족했다. 문서/최신 개발 SHA를 실행 CODE에 넣지 않는다.

이것은 승인된 CPU 연구 복구 범위이며 S gate·AI 채택·선행 성능 승인과 다르다. 실제 현재 입력 적격성과 RSS 예약→성공한 precursor→CPU의 검증된 chain은 이번 복구에서 실행하지 않았다. 변수 변경만으로 신규 판독이나 7일 시작을 선언하지 않는다. 실제 예약에서 신규 판독·정확 좌표 검증·비공개 저장·새 프로세스 원격 복원/ACK가 성공한 첫 회차부터 7일을 센다. 수동 process/publish나 가짜 schedule context로 조건을 우회하지 않았다.

bridge 확인 이후 다른 consumer 실행 때문에 선행 게시 확인이 오래되면 CPU는 안전하게 멈춘다. 실제 stale 조건이 확인된 때에만 기존 [V4 CPU private research consumer](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/workflows/v4-cpu-private-research.yml) → **Run workflow → branch main → purpose bridge-recover**로 영속 상태에서 복구한다. 현재 성공한 seed/runtime/bridge를 무조건 반복하지 않는다.

증거 정본은 [CPU_RECOVERY.json](CPU_RECOVERY.json)이다. verifier 신규 4개와 기존 CPU/restore 관련 시험을 포함해 9 PASS, root 통합 관련 시험 19 PASS를 확인했다. 실제 네 번의 실행을 증거로 보존하며 새 API/AI 제공자·새 키·유료 호출·다른 모델·자동 S2/S3/LIVE는 0이다.

## 실제 source transport 검증 완료·main 반영 대기

현재 main은 pinned CPU가 필요하지 않은 evaluations까지 precursor-private-cache ZIP 전체를 확장한다. 실제 저장 ZIP 4,598,165,007바이트에는 evaluations 49,054,341,364바이트가 포함돼 전체 확장이 약 51.46GB다. runtime/bridge 복구만으로 이 실행 경로가 준비됐다고 볼 수 없다.

CPU가 사용하는 documents/raw와 보존할 captures 전체는 합계 2,402,577,107바이트다. old pending·동일 ID 여러 버전·malformed/missing source 의미를 바꾸지 않도록 세 가족의 모든 파일을 그대로 보존하고 evaluations/requests/other만 제외하는 stdlib transport를 추가했다. 6GiB ZIP/3GiB 선택 확장/2GiB 실제 디스크 여유를 제한하고 전체 ZIP SHA를 검증하며, 부족하면 중단한다. 새 helper는 immutable `7d91886`의 별도 sparse orchestration checkout으로 전달하며 CPU 실행 pin/processor는 바꾸지 않는다. 또한 기존 동일 step에서 `GITHUB_ENV`에 쓴 RSS_RUN을 바로 읽던 오류를 고쳐, 변경하지 않은 `verified_schedule`이 기록한 ID를 다음 step에서 사용한다.

[실제 검증 run42995363348](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42995363348)은 개발 `fbbc4d0`에서 성공했다. runtime을 복원한 상태에서 ZIP 4,598,165,007바이트와 전체 digest를 확인하고 원본 세 가족 2,402,577,107바이트를 98초에 전송했다. captures8,008/documents2,948/raw7,046개가 모두 보존됐다. 다운로드 전 여유89,208,590,336바이트, 확장 전84,610,408,448바이트, 임시 ZIP 정리 후86,765,174,784바이트였다. source 300초/전체 job10분 한도를 지켰고 전체 job은223초였다. evaluations49GB는 확장하지 않았다.

같은 실행에서 추가 원본 다운로드 없이 고정230개 문서/230개 raw 해시와 `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec` fingerprint를 확인하고 literal41,784,646바이트를 복사했다. main 후보 `018f`의 기존 `precursor_operating_qa.py`는230개 원본을 사용해94초에 PASS했다. 원본 cache 불변, HTTP0/LIVE0/모델 추론0이다. 이는 Gate6의 원문 QA 부품 증거이며 Gates0~6 전체 PASS나 독립 선행 성능이 아니다. 숫자/해시 receipt만 artifact에 보관했다. 작은 artifact의 로컬 signed redirect403 때문에 상세 파일 다운로드는 보류했지만 transport/고정230/operating wrapper의 명시적 성공 receipt는 job 로그에서 회수했다. 같은 대형 ZIP 실행을 반복하지 않았다.

PR44용 로컬 후보 commit은 `164019bed86c2e5db660911813ab428c061c768a`이며 `018f`의 정상 FF 후속이다. production research step, stdlib receiver, portable test의 세 파일만 추가/수정했다. V4 package/개발 job/기존 publisher/전역 CPU pin은 바꾸지 않았다. 후보 전체 Python시험1,013 PASS·기존 독립 holdout1 SKIP, JS34 PASS다. 원문 QA와 source core7개 파일은 실제 검증한 `018f`와 바이트가 같아 같은 부품 증거를 재사용할 수 있다. main push/merge는 수행하지 않았다.

최신 수동 source 검증 run42995363348이 이전 bridge producer42990897783보다 뒤이므로, 이전 bridge는 고정 `verify_predecessor` 조건에 맞지 않게 됐다. 이 실제 조건 변화 때문에 마지막 수동 증거 실행 후 기존 main의 `bridge-recover`를 **한 번만** run42997763985로 실행했다. 정상 key/model/설정 진단의 반복이 아니다. DB 두 파일의 Git blob ID와 SQL SHA가 그대로이고 41완료 키·8개 테이블을 재확인했으며, 새 ACK/cache producer는 현재 관측한 최신 consumer run과 일치한다.

최종 갱신은 2026-11-11T09:45:21Z에 완료했다. 이후 자연 발생한 skipped consumer나 다른 수동 consumer가 있으면 bridge freshness가 다시 깨질 수 있다. 다음 실행에서 stale이면 조건을 우회하지 않고 기존 main `purpose=bridge-recover` 버튼으로 해당 조건만 복구한다. 미래에도 영구히 준비됐다고 주장하지 않는다. 현재는 **사용자의 PR44 main 승인·merge 전까지 ENABLED=false**를 유지한다. 승인/반영과 최신 bridge 조건 확인 후에만 소유자가 기존 Variables를 CODE_SHA=`221fa92b1cbff8950716ec373eac793ca340c873`, ENABLED=`true`로 맞춘다. 이번에는 변수/실행 pin/S gate를 바꾸지 않았다. 실제 예약 신규 판독과 7일 시작은 계속 NOT_RUN/NOT_STARTED다. 상세 증거는 [CPU_INPUT_TRANSPORT.json](CPU_INPUT_TRANSPORT.json), 최종 refresh는 [CPU_FINAL_BRIDGE.json](CPU_FINAL_BRIDGE.json)이다.


최종 상세 영수증 재조회: 부모 작업이 연결 GitHub 다운로드 도구로 작은3JSON artifact13843583056을 확보했다. ZIP3,449바이트의 SHA256 `ea8269cd39629aca2ff6283b676a6dbeb506fcbf1135117a45d32747fd234c9f`가 실제 API digest와 일치하고 CRC도 통과했다. 위 직접 redirect403은 그 경로의 과거 실패로 보존하며, 현재 상세 receipt 접근은 PASS다. source/QA 실행을 반복하지 않았다.
