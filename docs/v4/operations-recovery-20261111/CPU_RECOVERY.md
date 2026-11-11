# P0 CPU 운영 재개 진단 — 2026-11-11

작업 `BCT_V4_OPERATIONS_RECOVERY_20261111`, 기준 개발 `42ee0a6`, main `28d0b8c6`. 기존 계획 `BCT-V4-Q-1.0`, Objective Lock, Q1/Q2 PARTIAL, 독립 평가/선행성 BLOCKED, S gate를 유지한다.

현재 결과는 **동일 승인 seed 재구성 성공, 복원 cache의 package/offline health 검증 대기, 변수 gate false**다. 실제 신규 CPU 판독 0창/0자, 운영 재개 NOT_RUN, 7일 NOT_STARTED다. 아래 초기 runtime 부재 조사와 판단을 보존하며, 마지막 절의 실제 seed 재구성 결과가 현재 복구 상태다. 설정/seed 성공을 CPU 실행 성공으로 세지 않는다.

## 실제 설정 관측

기존 main 수동 `V4 CPU private settings check`를 [run 42988176131](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988176131)로 한 번 실행했다. 설정 진단은 immutable `289c4e23` 코드를 사용하며, 실행 전 전체 동작을 검토했다. 입력은 `remote_roundtrip=false`, `auth_denials_only=true`다. 모델 설치/로드, 비공개 DB 접근/게시, 변수 변경은 없다. 공개 main/data의 이미 존재하는 ref 생성 요청만 각각 403으로 거부됐으며 기존 ref를 갱신하는 요청이 아니다. 기본 입력으로 실행하면 비공개 권한 probe blob을 만들 수 있으므로 기본 경로는 실행하지 않았다.

| 관측 항목 | 실제 결과 |
| --- | --- |
| 기존 비공개 토큰 | 전달됨, 형식 유효; 값 미출력 |
| 기존 전달 암호 | 전달됨, 정확히 64자; 값 미출력 |
| `BCT_V4_CPU_CODE_SHA` | `da7cb9bc1e6b99d5f4859aaeda4431dbacee03d6` |
| 현재 고정 실행 SHA | `221fa92b1cbff8950716ec373eac793ca340c873` |
| 현재 pin과 변수 일치 | **false** |
| `BCT_V4_CPU_RESEARCH_ENABLED` | **false** |

따라서 실제 research job 조건 중 `CODE_SHA == 221fa92…`와 `ENABLED == true` 두 항목이 모두 false다. 이전 7일의 CPU 43회 skipped와 함께, 현재 비실행 원인을 단순 추정에서 실제 변수 관측으로 좁혔다. 다른 조건인 main/workflow_run/성공한 main precursor도 계속 필요하다. 이 진단만으로 모든 다른 조건이 충족됐다고 주장하지 않는다.

기존 진단 출력의 `code_SHA_matches_tested_handoff=true`는 옛 `da7cb9b`와 비교하는 고정 필드다. **현재 실행 pin과 일치한다는 뜻이 아니다.** 새 증거에서는 현재 pin과 별도로 비교해 false를 기록했다. 기존 Variables API 403 증거를 재사용했고 읽기/쓰기 API 실패를 반복하지 않았다.

## 기존 runtime 복구본 확인

기존 main seed [run 38682772423](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38682772423)는 2026-10-15에 다음 runtime 캐시를 실제 저장했다.

```text
v4-cpu-runtime-Linux-X64-3.12.15-fff880f684241e7320bcb1f19eecf3f5ad9a32f15f730cc2351aae63c13bda10
```

당시 main 캐시 ID `8975651992`, 압축 크기 1,058,839,680바이트였다. 모델은 `fastino/gliner2-base-v1`, revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`, 검증된 모델 파일 9개/845,068,741바이트다. 원래 manifest의 파일별 SHA를 그대로 사용한다. requirements lock SHA-256은 `99aa48b5c7381c3c451769f8fbb8b21ef4f745a8e7b7c5dbdb15deb0312a8bb9`, model manifest SHA-256은 `5588cb168c4dcdac419b2a1ea269c2d5bbcc94d18e760949d2ac48b2bc43384b`다. seed 코드 `6dea292`, 기존 실행 pin `221fa92`, 개발 `42ee0a6`의 두 파일은 동일하다.

이번 실제 조회에서 Actions 전체 캐시는 **0개**, 과거 main seed 및 preflight run `38677679784`의 현재 artifact는 각각 **0개**다. `/workspace`, `/tmp`, 현재 사용자의 기본 Hugging Face cache를 조사했지만 `.v4-cpu-env`, `.v4-cpu-runtime`, 모델 가중치 복구본은 없었다. 현재 작업용 venv는 Python 3.12.14이며 gliner2/torch/transformers/safetensors/huggingface-hub도 없다. 비공개 CPU state tree의 파일은 checkpoint/DB/persistence receipt뿐이어서 runtime 사본이 아니다. 캐시가 사라진 정확한 시점/원인은 UNKNOWN이며 다른 소유자 기기의 백업 존재 여부도 UNKNOWN이다.

`V4 CPU main cache seed`와 `V4 CPU environment preflight`는 cache miss에서 venv 생성, pip 설치, 모델 9개 다운로드를 수행한다. 지금 실행하면 기존 runtime 복원이 아니라 재설치가 되므로 **둘 다 실행하지 않았다**. requirements/manifest 텍스트만으로 없어진 binary payload를 복구할 수 없다.

`purpose=bridge-recover`는 기존 비공개 CPU checkpoint를 읽은 후 CAS/ACK commit과 암호화 bridge cache를 다시 만든다. 모델 runtime을 복구하는 경로는 아니다. runtime이 없는 상태에서 DB/ACK를 불필요하게 갱신하지 않도록 실행하지 않았다. 공식 정량 generation6 원격 복원은 별도 저장 검증 경로이며 CPU runtime 복구를 대신하지 않는다.

## 소유자 화면과 재개 조건

현재는 기존 `ENABLED=false`를 유지한다. Secret 재설정이나 새 토큰은 필요하지 않다. 동일 승인 cache seed는 아래 기록처럼 이미 한 번 복구했으므로 반복하지 않는다. 다음 초기 재개 절차의 runtime 부재 부분은 승인된 seed 재구성 결과로 대체하며, package/offline health PASS 뒤에만 bridge/설정 단계를 진행한다.

1. 우선 이미 승인된 **기존** Linux-X64/Python 3.12.15 runtime 사본에 `.v4-cpu-env`와 `.v4-cpu-runtime`이 함께 있는지 확인해야 한다. 현재 접근 가능한 cache/artifact/로컬에는 없다. 복구본이 없으면 재설치를 허용하지 않는 현재 범위에서 재개할 수 없다.
2. 기존 사본을 확보한 경우만 같은 lock/9개 모델 SHA·Python/arch·3GiB payload 상한을 오프라인 검증하고 main 범위 runtime 캐시를 복원한다. 검증 없이 설치 fallback으로 대체하지 않는다.
3. runtime 복구 후 최신 비공개 CPU checkpoint와 CAS를 보존하는 bridge 복구/원격 새 프로세스 검증이 필요하다. 기존 [V4 CPU private research consumer](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/workflows/v4-cpu-private-research.yml) → **Run workflow → branch `main` → purpose `bridge-recover`**가 해당 경로다. 이번에는 실행하지 않았다.
4. 앞선 조건 충족 뒤에만 [Settings → Secrets and variables → Actions → Variables](https://github.com/irewon1-lgtm/bottleneck-control-tower/settings/variables/actions)에서 기존 `BCT_V4_CPU_CODE_SHA=221fa92b1cbff8950716ec373eac793ca340c873`, `BCT_V4_CPU_RESEARCH_ENABLED=true`로 맞춘다. 실행 코드 pin 자체를 문서/최신 개발 SHA로 바꾸지 않는다. 이번에는 두 변수를 바꾸지 않았다.
5. 실제 예약 RSS→precursor→신규 CPU 판독·정확 위치 검증→비공개 저장→새 프로세스 원격 복원/ACK가 성공한 첫 회차부터 7일을 센다. 진단/캐시/변수 변경만으로 시작하지 않는다.

안전한 설정 관측 버튼은 [V4 CPU private settings check](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/workflows/v4-cpu-private-settings-check.yml) → **Run workflow → main → remote_roundtrip=false, auth_denials_only=true**다. 이번 run에서 이미 관측했으므로 그대로 반복할 필요는 없다.

증거 정본은 [CPU_RECOVERY.json](CPU_RECOVERY.json)이다. 기존 검증된 전체 시험 1,828 PASS/독립 holdout 1 SKIP는 관련 파일 불변 범위에서 재사용했다. 이번에는 새로운 실제 설정 실행/캐시·artifact·로컬 runtime 조회와 파일 해시를 검증했다. 모델 설치/다운로드, 신규 API/AI 호출, 기존 DB 변경, pin 변경, 활성화는 모두 0이다.

## 승인된 동일 seed 복구 재검토 — 미실행

위 초기 판단은 binary 복구본 부재와 설치 금지를 넓게 적용해 승인된 seed의 재구성도 보류한 결과다. 사용자의 구체적인 “과거 캐시·승인된 seed·영속 상태에서 복구” 지시에 맞춰 동일 seed를 별도 검토했다. 기존 seed는 **새 모델 선택이 아니라 이미 승인된 동일 모델/고정 설정의 재구성 경로**다. `bootstrap_model`은 모델명/revision/Apache-2.0을 고정하고 9개 파일을 원래 SHA-256으로 검사한다. free/cache guard, bootstrap, 파일 검사, runtime probe와 CPUExtractor의 함수/클래스 AST는 seed `6dea292`, 실행 pin `221fa92`, 현재 코드에서 동일하다. requirements 71개도 전부 정확한 `==version` 고정이며 lock/manifest는 동일하다.

다만 이 경로를 **과거 venv와 바이트까지 같은 runtime 복원**으로 표현할 수는 없다. wheel 해시/`--require-hashes`가 없고 pip가 여전히 의존성을 해석한다. 플랫폼 wheel/sdist·build isolation·추가 전이 의존성, PyPI/PyTorch index, hosted runner 이미지와 Actions major tag는 고정 binary 증거가 아니다. 현재 seed는 모델 SHA와 3GiB 상한만 확인하며 설치 distribution 전체 일치/`pip check`/모델 load health는 검사하지 않는다.

따라서 동일 승인 seed 실행을 허용하는 경우에도 lock/model/revision/SHA를 바꾸지 않고 전체 설치 package/version·추가 distribution·의존성 일관성을 기록해야 한다. 실패 시 버전을 풀거나 다른 모델로 대체하지 않는다. 성공 표현은 “동일 승인 모델과 고정 설정 재구성”으로 한정하고, CPU 활성화 전에는 최신 비공개 checkpoint/bridge와 runtime 검증을 따로 충족한다. 이 재검토에서는 dispatch·설치·다운로드를 수행하지 않았다. 초기 문서의 seed 절대 금지 표현은 이 구체적 승인 범위의 기술 재검토로 한정된다.

## 동일 승인 seed 실제 재구성 성공 — runtime 검증 대기

구체적인 승인 seed 복구 지시에 따라 기존 main cache seed를 **한 번만** [run 42989488936](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989488936)로 실행했다. immutable `6dea292`, Python 3.12.15, 동일 lock/revision/9개 모델 SHA를 유지했고 성공했다. 모델 9개를 재다운로드했으며, 기존 probe의 검증 모델 tree는 생성된 manifest를 포함해 845,068,741바이트, runtime 전체 payload는 2,025,505,375바이트다. 새 main 캐시 ID는 `10344400333`, 압축 크기는 **1,058,256,865바이트**이며 기존과 같은 cache key다. pip 다운로드의 정확한 압축 body 바이트는 기존 seed 로그에 보존되지 않아 UNKNOWN으로 기록한다. 개별 모델 파일 바이트는 새 verifier의 실제 파일 크기 증거로 분리한다.

이를 `SAME_APPROVED_SEED_REMATERIALIZATION`으로 기록하며 과거 wheel/venv 전체 binary 일치를 주장하지 않는다. CPU/DB/변수/기존 실행 pin은 변경하지 않았다.

개발 전용 `runtime-verify` job과 도구를 준비했다. 이 job은 cache miss에서 중단하며 설치 fallback이 없다. Python/플랫폼을 확인하고 `pip freeze --all`이 lock의 71개 package/version과 정확히 같은지 및 `pip check`를 검사한다. 9개 모델 SHA/개별 크기/3GiB payload를 검증한 다음 별도 checkout한 immutable `221fa92` 코드로 offline 모델 load health만 수행한다. 원문·큐·DB·추론은 사용하지 않으며 health step에 Secret/token을 전달하지 않는다. 새 verifier 회귀 4개와 기존 CPU workflow 시험 1개는 PASS이며 실제 GitHub verifier 실행은 개발 반영 후 진행한다. health/package 검증 전에는 bridge/CAS 또는 CPU 활성화를 실행하지 않는다.
