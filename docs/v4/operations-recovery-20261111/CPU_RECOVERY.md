# P0 CPU runtime·비공개 bridge 복구 — 2026-11-11

작업 `BCT_V4_OPERATIONS_RECOVERY_20261111`. 기존 `BCT-V4-Q-1.0`, Objective Lock, Q1/Q2 PARTIAL, 독립 평가/선행성 BLOCKED와 S gate를 유지한다.

**동일 승인 runtime과 비공개 CPU checkpoint/암호화 bridge의 실제 복구는 PASS다. 이후 현재 main의 source ZIP 전체 확장 문제가 확인돼 운영 활성화는 계속 BLOCKED다. 정기 CPU 신규 판독은 NOT_RUN이며 7일 NOT_STARTED다.** 새 모델/다른 revision/다른 실행 pin으로 대체하지 않았다. 복구 성공을 AI 채택·S2/S3·실제 선행 성능으로 올리지 않는다.

## 실제 실행 증거

| 실행 | 실제 결과 |
| --- | --- |
| [기존 설정 관측 42988176131](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42988176131) | 기존 토큰 전달/형식 유효, 전달 암호 정확히 64자. CODE=`da7cb9b…`, ENABLED=`false`. 값 미출력·설정 변경 없음 |
| [동일 승인 seed 재구성 42989488936](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42989488936) | 기존 immutable seed `6dea292`, Python 3.12.15, 같은 71개 lock/revision/모델 9개 SHA로 main 캐시 재구성 PASS |
| [복원 runtime 검증 42990702742](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990702742) | 개발 `bd9ee61`, 정확한 71개 distribution/version·추가 package 0·pip check PASS, 9개 SHA/크기, immutable `221fa92`의 offline load health PASS |
| [기존 영속 CPU bridge 복구 42990897783](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42990897783) | main의 기존 경로/실행 pin `221fa92`, 실제 비공개 복원·새 프로세스 8개 테이블·41개 완료 키 중복 방지·암호화 cache PASS. 신규 판독 0 |

초기에는 Actions cache 0개, 과거 seed/preflight artifact 0개였고 `/workspace`, `/tmp`, 기본 Hugging Face cache에도 기존 runtime binary가 없었다. 처음에는 재설치 금지를 넓게 해석해 seed까지 보류했다. 이후 사용자의 구체적인 “정상적인 과거 캐시·승인된 seed·영속 상태” 복구 지시를 검토해 **이미 승인된 동일 모델/고정 설정의 재구성**을 한 번 실행했다. 과거 venv/wheel 전체의 bit-identical 복원으로 표현하지 않는다.

모델은 `fastino/gliner2-base-v1`, revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`다. seed `6dea292`, 실행 pin `221fa92`, 현재 개발의 lock/manifest와 bootstrap·파일 검사·probe·CPUExtractor 로직은 같다. lock 71개는 모두 정확한 버전 고정이다. wheel 해시는 고정돼 있지 않으므로 실제 복원 후 전체 distribution과 의존성 검사를 추가했다. 실패 시 버전 완화나 다른 모델 fallback은 없다.

## 정확한 runtime·cache 수치

| 항목 | 실제 수치 |
| --- | --- |
| 고정 모델 파일 9개의 재다운로드 body 합계 | **845,067,152바이트** |
| 생성된 모델 manifest 포함 모델 tree | 845,068,741바이트 |
| runtime 전체 payload | **2,025,505,375바이트**; 3GiB 미만 |
| 새 main runtime cache | ID `10344400333`, **1,058,256,865바이트** |
| 새 암호화 CPU bridge cache | ID `10344798276`, **993,910바이트** |
| offline 모델 load health | 8.08초, CPU 4 threads, peak RSS 2,126,776KiB, 추론 0, 모델 다운로드 0 |
| pip 패키지 다운로드의 정확한 압축 body 바이트 | UNKNOWN: 기존 seed 로그가 정확한 전송 바이트를 보존하지 않음 |

기존과 같은 runtime cache key:

```text
v4-cpu-runtime-Linux-X64-3.12.15-fff880f684241e7320bcb1f19eecf3f5ad9a32f15f730cc2351aae63c13bda10
```

requirements SHA-256은 `99aa48b5c7381c3c451769f8fbb8b21ef4f745a8e7b7c5dbdb15deb0312a8bb9`, model manifest SHA-256은 `5588cb168c4dcdac419b2a1ea269c2d5bbcc94d18e760949d2ac48b2bc43384b`다. verifier는 cache miss에서 중단하고 설치하지 않는다. health step에는 Secret/token을 전달하지 않았고 원문·큐·DB·추론을 실행하지 않았다.

## 기존 DB·처리 이력 보존

CPU 비공개 ref는 `1ea13ed1ff81b75f8c6216177c34bb04c0e088b5`에서 `f42c11aefa357a271bd8a8726c4e6fddaa55366a`로 두 개의 checkpoint/ACK 메타데이터 commit만 추가했다. **checkpoint JSON과 압축 DB의 Git blob ID가 전후 동일**하다. SQL/사실/기존 원문을 고치지 않았다.

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

## 추가 확인: 현재 main CPU source transport 미해결

현재 main은 pinned CPU가 필요하지 않은 evaluations까지 precursor-private-cache ZIP 전체를 확장한다. 실제 저장 ZIP 4,598,165,007바이트에는 evaluations 49,054,341,364바이트가 포함돼 전체 확장이 약 51.46GB다. runtime/bridge 복구만으로 이 실행 경로가 준비됐다고 볼 수 없다.

CPU가 사용하는 documents/raw와 보존할 captures 전체는 합계 2,402,577,107바이트다. old pending·동일 ID 여러 버전·malformed/missing source 의미를 바꾸지 않도록 세 가족의 모든 파일을 그대로 보존하고 evaluations/requests/other만 제외하는 stdlib transport를 개발 중이다. 6GiB ZIP/3GiB 선택 확장/2GiB 실제 디스크 여유를 제한하고 전체 ZIP SHA를 검증하며, 부족하면 활성화를 보류한다. 새 helper는 별도 immutable orchestration checkout으로 전달하고 CPU 실행 pin/processor는 바꾸지 않는다. 현재 helper 시험은 기능 검증이며 실제 transport 및 main 반영/PR 검토 완료가 아니다.
