# BCT V4 자동화 전체 복구 — 최신 결과

작업 `BCT_V4_AUTOMATION_FULL_RECOVERY_20261111`, 계획 `BCT-V4-Q-1.0`. Objective Lock, Q1~Q7, 원문·최초 발견·정답·HOLDOUT·승격 기준을 유지했다. 새 모델·유료 API·새 토큰은 사용하지 않았다. 확인된 운영 결함을 수정·시험·개발 브랜치에 push했고 PR45~53을 일반 병합했다. 최신 main의 실제 Gate와 릴리스 영수증도 연결했다. 원문·기존 DB를 초기화하거나 검증 조건을 완화하지 않았다.

최종 보고서 관측: **2026-11-12T03:14:27.975891+09:00**. 최종 증거 커밋: **2571a1375d00a98d19304b4492d1dcdaf5f7f689 (실행 증거 커밋; 최종 보고서 HEAD와 실제 실행 pin은 구분)**.

## A. 운영 자동화 판정과 기능별 상태

**전체 판정은 PARTIAL이다. 실제 신규 문서 1개의 수동 수집→CPU 완독→비공개 저장·새 프로세스 복원→REVIEW 전달→공개 Pages 반영은 PASS다.** 최신 main `5082723`의 Gate0~6·릴리스 영수증·262파일 guard·CI는 PASS다. 예약 CPU 변수 쓰기는 실제 GitHub403으로 거부되어 기존 설정/false가 남았다. 최신 예약 수집은79신규 기사→40검증 본문까지 진행됐지만 CPU는 SKIPPED다. 앞선 수동 자료군의 나머지5문서는 부분 판독 상태다. 의미 검토 완료·독립 수급쌍·예측 성능·7일 연속 운영은 입증되지 않았다.

| 기능 | 이전 상태 | 최신 판정 | 실제 실행 근거와 남은 범위 |
|---|---|---|---|
| 운영 릴리스 Gate0~6 | FAIL | PASS | 최신 I43067179780 필수8단계 전부 실제 PASS. PR53 일반 병합 뒤 main5082723의 unchanged guard262파일·CI43072919702 PASS |
| CPU 자동 실행 | SKIPPED | 수동 PASS / 예약 BLOCKED | C6 수동 신규 판독·저장·복원 성공. 자동 CPU44회는 최신 7일 창에서 모두 SKIPPED. 기존 CODE_SHA/ENABLED=false와 실제 변수 PATCH403이 남음 |
| 최신 연구 DB 복원 | BLOCKED | PASS | generation6 암호·manifest·14자산·8테이블·새 프로세스 복원 PASS. 사실 전용 capsule이며 원래 전체 본문 DB 복원으로 주장하지 않음 |
| RSS 수집 | PARTIAL | PARTIAL | 최신 실제 예약79신규/1026중복,125피드 중114성공·11실패. 수동18/1085 및 이전 legacy79/1024와 구분. 정상 빈 USGS는 NO_NEW_INPUT |
| 공식 원문 확보 | PARTIAL | PARTIAL | 최신 예약79 seed 중40 CAPTURED·31출처보류·6 HTTP403·2 TIMEOUT. 수동 자료군의 검증6본문과 별도 집계. HTTP transaction 총수/pending은 UNKNOWN |
| 제품·사건 판독 | PARTIAL | PARTIAL | 고유6문서 중1완독·5부분,72성공창. 제품 제안163개와 span417개는 확인된 제품·완성 사건 수가 아님 |
| 수요·공급 연결 | BLOCKED | BLOCKED | 완독 사례에서 적격 독립쌍0. 미완독 문서 전체는 UNKNOWN/public null. 신규 적격 S2/S3각0, TARGET 필드 보충·승격 없음 |
| REVIEW_LEAD | 전달 미검증 | 전달 PASS / 의미 검토 PENDING | 실제 REVIEW43064438463 PASS,18버전별 판독 영수증/고유6문서 복원·해시 확인. 의미 검토 전부 PENDING·완료0 |
| 연구 결과 저장·복원 | PARTIAL | 수동 PASS | 비공개 ACK20·SQLite cc9ba416… 새 프로세스8테이블 복원. 기존41완료 키를 보존하고 신규 완독 키1개 추가→42. 실패 후 암호화된24창도 재판독0으로 회복 |
| 대시보드 데이터 갱신 | BLOCKED | PASS | 실제 Pages43064438487 배포, 공개 generation20·snapshot·dashboard 해시 일치. 동일 PC/모바일 V5 문맥에서 이전 ACK14→새 ACK20 전환 관찰 |
| 실제 전체 왕복 | NOT_RUN | 수동 신규1건 PASS / 예약 미입증 | 정확한 문서·본문 버전·CPU 창·private ACK·REVIEW·실제 화면이 연결됨. 예약 전체 왕복과 7일 시작은 NOT_STARTED |

판독이 완료된 문서도 근거가 부족하면 HOLD로 남는다. 이번 완독은 `READ_COMPLETE`이면서 `READ_EVIDENCE_HOLD`다. 이를 의미 검토 완료, 완성 TARGET 또는 예측 성공으로 바꾸지 않았다.

## B. 실제 신규 문서 1개의 전체 왕복

추적 문서는 `270bbad5-f286-4b2a-8947-7894ee0b2cb1`이다. RSS43032161571(실제 수동)→acquisition43032565649(실제 workflow_run)의 신규6개 원문 중 하나이며, producer main은 `933a29638c06d72d4cf4c17d843cfec2978066d2`다.

| 연결 항목 | 실제 값 |
|---|---|
| Body SHA256·source version |`3515cd52456dbeff0cc3bd7445019527b2be17be7fa80a1dd504ec3112bc3d6e` |
| Native raw SHA256 |`7b55987303f90028af724ada5682588652f1696c09d79cf89c387ab298106542` |
| 원문·창 |본문2381자, 실제 계획·판독 창2372자.10/10창 성공, 실패0·미판독0. 빠진9자는 문단 개행 |
| 실행 코드 |C6 `6e788d18cf85fdb834b451bb35585a8b58925301`; workflow main I `5c66cd8ef5ec47046024027d52e0e8b755d1f012` |
| 실제 신규 CPU 실행 |43063708462,43064155117 모두 SUCCESS. 앞선 C5의24창은43063536538에서 정확히 회복했고 새 판독으로 다시 세지 않음 |
| 판독 결과 |`READ_COMPLETE / READ_EVIDENCE_HOLD`, 이유 `TARGET_FIELDS_UNKNOWN`. product/specification/region/customer_group/supply_pool 다섯 필드 모두 확인되지 않아 HOLD |
| 창·분석 바인딩 |window SHA256 `433a9a588de4a04c6bdbf12d767da6a344072152391c54f47eb2781e6a756a35`; analysis SHA256 `6a057ee478e8140f42d2f6946180efbe7da9602536ae48c3fe6e22c24a94706d` |
| 비공개 저장 |ACK20, private commit `20db8addf53958b38ec2f5a44ee41d1abfca1c4d`, checkpoint `bc4585c54d8da30a0635fb609a2a6ea927c0765f` |
| SQLite 새 프로세스 복원 |SHA256 `cc9ba41642bc8d010c9795c0b9dd724202bb33ad4121f4bbae848c901d19656b`,8테이블. 기존41완료 키 보존·중복 제외, 신규1추가→42완료 키 |
| 실제 REVIEW |43064438463 PASS. REVIEW branch `ffbd019e4794650d6d58e3beecba41877baa58dc`에서18영수증을 새 프로세스로 복원·해시 확인. 대상의 정확한 원문·창·queue 버전·HOLD 포인터 연결; 의미 검토는 PENDING |
| 실제 공개 버전 |generation20, snapshot SHA256 `be43e03166f5bed707a404175a4ae475f41b606564f346b68b31ad16f5edb8e3` |
| 실제 Pages·화면 |Pages43064438487 PASS. dashboard SHA256 `2cc5e97633ddc5df8226b74fc7e95db91ba83fdb9ea478041810b5d8ebfc646f`; manifest·snapshot·research generation 일치. V5의 지속 PC/모바일 문맥에서 이전 ACK14→generation20 전환과 대상10/10 HOLD를 관찰 |

공개 generation의 RSS_run_id/acquisition_run_id는 실제 schema에서 null인 채 보존했다. 위 수집 계보는 실제 acquisition/원문 해시·CPU 입력 증거로 연결하며, null 필드를 임의로 채워 같은 연결로 꾸미지 않았다. 중간 generation18 화면은 관찰하지 않았고, 실제로 관찰한20에 누적72창이 포함됨을 검증했다. dashboard SHA2cc5…는 V5가 완독/HOLD 전환을 관찰한 시점의 고정 증거다. 이후 code·collection 갱신으로 dashboard byte 해시는 달라지므로, 최신 상태는 LATEST_SCHEDULED_SOURCE_WAVE의8개 해시·generation 대조로 연구20/be43… 유지까지 확인했다.

모델은 기존 승인 `fastino/gliner2-base-v1`, revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`다. 승인된9파일 해시·71개 의존성을 재사용했고 신규 설치·유료 API 호출0이다. 상세: [C6_ACTUAL_NEW_DOCUMENT_ROUND_TRIP.json](C6_ACTUAL_NEW_DOCUMENT_ROUND_TRIP.json), [C6_REVIEW_PAGES_ACTUAL.json](C6_REVIEW_PAGES_ACTUAL.json), [C6_BROWSER_SAME_CONTEXT.json](C6_BROWSER_SAME_CONTEXT.json).

## C. 실제 처리량 — 자료군과 단위를 분리한 집계

| 단계·단위 | 실제 수치 | 해석 |
|---|---:|---|
| 이전 예약 수집 자료군 |RSS79신규/1024중복→17신규 검증 원문 |43025401279→43025842520, 이전 legacy producer. 현재18/6 계보와 합산하지 않음 |
| 현재 실제 수동 RSS |18신규 기사·18고유URL/1085중복 |43032161571, canonical10047→10065. 수동 event이며 예약으로 바꾸지 않음 |
| 수집→seed 제외 |기존 완료 corpus URL2개 |동결 필터와 literal RSS manifest의 정확한 재생으로18−2=16을 설명. 제외된 원문의 현재 버전은 재요청·재검증하지 않음 |
| 신규 seed 결과 |16=CAPTURED6+PROVENANCE_BLOCKED10 |지속된 seed 처리 결과 수. HTTP transaction 수가 아님 |
| 신규 원문·출처 검증 |6문서 |native/body/version 해시 정확히 확인. 별도 acquisition unverified_source_holds1은 다른 범위이므로10과 합산하지 않음 |
| 실제 본문 HTTP 요청 /본문 pending |UNKNOWN /UNKNOWN |공개 receipt null.18URL·16seed·6capture 또는 retry 설정으로 추정하지 않음 |
| 별도 추가 원문 경로 |추가본문0/추가 유효 primary0 |6seed capture와 다른 단계 |
| 신규 CPU 고유 문서 |6개 참여:완독1·부분5 |각 실행의6 touched를 합산해18문서로 세지 않음 |
| 신규 CPU 고유 성공 창 |72 |C5회복24+C6신규24+24. 같은24창의 회복·복원·REVIEW 전달을 새 판독으로 중복 계산하지 않음 |
| 실제 신규 판독 문자 |21,463자 |고유 성공창의 실제 판독 누적. 원문 전체 길이나 제안 수와 다른 단위 |
| 아직 미판독 |60창/공백 제외10,274자 |새 프로세스 복원 상태의 실제 잔여 수치.5부분 문서를 완료로 처리하지 않음 |
| CPU span /제품 제안 |417 /163 |원문 연결 span과 **제품 제안** 수. 확인된 제품·독립 사건 수가 아님 |
| CPU 판독·분석 영수증 |18버전별 기록/고유6문서 |서로 다른 판독 버전 기록.18개의 고유 문서나 의미 검토 완료가 아님 |
| 의미 검토 완료 |0 |전부 semantic PENDING.완독 대상의 evidence HOLD는 정확히 보존 |
| 완독 대상 적격 독립쌍 |0 |대상에 근거 없는 TARGET 필드를 보충하지 않음 |
| 부분·미판독 전체 독립쌍 |UNKNOWN/public null |공개 null을0으로 덮지 않음 |
| 신규 적격 S2/S3 |0 /0 |승격·독립 선행 성공 주장 없음 |

실행별 신규 창/문자는 원 C5연구43060982183의24/4114, C6신규43063708462의24/8020,43064155117의24/9329다. 합계는72/21,463이며, 마지막 공개 배치의 `new_CPU_windows=24`/`new_CPU_characters=9329`와 구분한다. 공개 보존 창은 기존1277+신규72=1349이고, 완료 본문 키는41→42다.

첫 C4실패43057947172는 source export 전에 모델을 로드했지만 최종 관측·암호화 결과를 남기지 못했다. 그때의 추론·성공 창 수는 **UNKNOWN**이며0으로 쓰거나 보존된 판독으로 더하지 않는다. 실제 C5연구43060982183은24창을 암호화했지만 publisher가 yaml import로 실패했다. 정확한 ciphertext cache10365971981을43063536538에서 회복해 ACK·새 프로세스 복원 PASS를 얻었고, 회복의 신규 판독·모델 로드0을 확인했다. 실패 이력을 지우지 않았다.

현재 수동 자료군 입력의 transport는1,310,662바이트 ZIP/4,384,278바이트 확장으로6개 native source를 전달했다. 전체 source/control cache는500,746,000바이트 압축으로 줄었으며 원래4.69GB archive 참조와 source/control 이력을 보존했다. 이를 모델 추론량으로 세지 않았다.

### 실제 최근 7일 Actions 수치

정확한 생성 시각 창은 **2026-11-04 18:00:41 UTC~2026-11-11 18:00:41 UTC**, KST **11월5일03:00:41~11월12일03:00:41**다. 5페이지·499고유 run을 읽었으며 GitHub total499와 같아 잘림이 없다. 고정 시점 metadata 통계이며 이후 실행의 미래 결과를 추정하지 않는다.

| 범위 | 전체 | SUCCESS | FAILURE | SKIPPED | CANCELLED | 대기 중 |
|---|---:|---:|---:|---:|---:|---:|
| 모든 branch/event |499|345|83|54|16|1|
| main 모든 event |371|240|64|54|12|1|
| main 자동 event |339|213|60|54|11|1|
| main schedule만 |85|69|15|0|0|1|
| main 수동 workflow_dispatch |17|14|3|0|0|0|

자동 event는 schedule/workflow_run/repository_dispatch다. 성공한 자동 workflow 이름은 **7종**, 녹색 SUCCESS는213회다. CI/PR 시험 성공을 기능 성공으로 더하지 않았고, **7종 녹색을7기능의 실제 분석 성공으로 바꾸지 않는다.** AI annotation14SUCCESS는 실제 유료 API 판독이 아니며, preservation-only recovery와 read-only observer도 분석 성공과 다르다.

| main 자동 workflow | 전체 | 성공/실패/SKIPPED/CANCELLED/대기 |
|---|---:|---|
| RSS live environment check |42|41/1/0/0/0|
| New precursor evidence acquisition |43|41/0/1/1/0|
| REVIEW_LEAD SHADOW intake |55|50/3/2/0/0|
| Read-only BCT Pages |64|48/0/6/10/0|
| V4 CPU private research consumer |44|0/0/44/0/0|
| Future bottleneck body candidates |57|0/56/1/0/0|
| RSS AI annotation |15|14/0/0/0/1|
| BCT read-only evaluation observer |14|14/0/0/0/0|
| BCT recovery storage gates |5|5/0/0/0/0|

대기1회는 RSS AI annotation43072823646이며 RSS live 신규 수집 실행과 다르다. 최신 실제 RSS 예약은43069839035(17:36:44UTC 생성)다. 수동 Future G의 성공과 I Gate 성공은 자동 성공 수에 소급 합산하지 않았다.

자동60FAIL·54SKIPPED의 정확한 해당 시도 job/step을 확인했다. 기존112건의 분류를 재사용하고 새2건만 추가 조회했으며, 기간 밖으로 나간 과거1건은 제외했다.

| 실패/보류 분류 | 건수 | 확인한 원인과 범위 |
|---|---:|---|
| Future 릴리스 검증 실패 |56|56건 모두 첫 guard 단계 실패를 확인했다. 세 역사 head의 대표 로그는 `validated code/test file set changed or missing`, 새 I43070231522의 실제 로그는 `main operating code differs from actually validated code`였다. 선별 대표 로그를 근거로 모든56개 예외 문자열을 전수 조회했다고 주장하지 않는다. 새 I 실패는 PR53 영수증 연결 전 기록이며 현재 J guard PASS와 구분 |
| RSS 원격 게시 실패 |1|42128685872 Git push에서 GitHub가 `fatal error in commit_refs_rules`로 거부. 수집기/파서 실패가 아니며 세부 서버 원인은 UNKNOWN |
| REVIEW 디스크 부족 |1|42502046388에서 불필요한 evaluations 이력까지 ZIP 확장하다 디스크 고갈 |
| REVIEW public Git 실패 |2|43033762121/43033773972의 `PUBLIC_DATA_GIT_FAILED`; 별도 중복 인증 재현·수정과 실제 복구 성공 증거 연결 |
| CPU 자동 SKIPPED |44|모든 실제 job SKIPPED. 고정 코드·enabled/main/상위 성공 guard를 확인. 현재 실행 문맥의 옛 CODE/false·PATCH403은 실제 확인했으나 과거44회 변수값을 모두 관찰했다고 주장하지 않음 |
| 기타 자동 SKIPPED |10|Future1·Acquisition1·REVIEW2·Pages6의 진입 guard/needs 차단. 저장되지 않은 upstream payload나 개별 false predicate를 만들어내지 않음 |

정본: [FINAL_SEVEN_DAY_ACTIONS.json](FINAL_SEVEN_DAY_ACTIONS.json), [FINAL_FAILURE_CLASSIFICATION.json](FINAL_FAILURE_CLASSIFICATION.json). 앞선02:15:22KST 통계·분류도 HISTORICAL_021522_KST 파일들에 보존했다. 7일 통계 창이 있다는 사실은 C6로7일 연속 운영했다는 뜻이 아니다.

### 최신 예약 수집 자료군 — 수동 완독 자료군과 분리

실제 예약 RSS43069839035는 **신규79/중복1026**,125피드 중114성공·11실패였고 canonical은10065→10144다. 실제 acquisition43070231555는 **40 CAPTURED /31 PROVENANCE_BLOCKED /6 HTTP403 /2 TIMEOUT**으로79 seed 결과를 구분했다. 별도 unverified_source_hold1은 다른 단위로 합산하지 않는다. 이40검증 본문은 CPU43071173782가 SKIPPED여서 새 CPU 판독0이다. 본문 HTTP transaction 수와 pending은 UNKNOWN으로 유지한다.

최신 실제 사이트는 collection43070231555의79URL/40본문을 표시하면서 기존 연구 generation20·snapshot be43…을 유지한다. JSON·manifest·해시 대조8개가 PASS다. 이40본문을 수동 자료군의6본문·72창·완독1건에 더해 판독 실적으로 부풀리지 않았다. 이 예약 수집→원문 확보→CPU SKIP은 현재 자동 운영 차단을 직접 보여준다. [LATEST_SCHEDULED_SOURCE_WAVE.json](LATEST_SCHEDULED_SOURCE_WAVE.json).

## D. 실제 사이트·main·Gates·운영·저장·배포 증거

실제 사이트는 [Bottleneck Control Tower](https://irewon1-lgtm.github.io/bottleneck-control-tower/)다. 공개 generation20의 data_at은 `2026-11-11T17:03:11.149991+00:00`, 실제 build 생성은17:04:44.833363UTC다. 원래 역사 데이터 시각 `2026-10-14T23:16:13.592709+00:00`은 historical_data_at으로 보존했다. collection generation, 최신 연구 generation, 과거 이력 시각을 섞지 않았다. V5 실제 PC·모바일 동일 문맥에서 이전 ACK14→새 ACK20과 완독/HOLD를 관찰했고, 공개 snapshot·manifest·dashboard bytes 해시가 일치했다. 별도 수동 코드 push가 있어야만 연구 결과가 갱신되는 경로가 아님을 실제 workflow_run Pages로 확인했다.

운영 main은 일반 병합으로 관련 PR45~53을 반영했다. 최종 main J는 `5082723f515382a962184b36a31e34af17a7e07a`, 실제 검증 코드 I는 `5c66cd8ef5ec47046024027d52e0e8b755d1f012`, CPU immutable C6는 `6e788d18cf85fdb834b451bb35585a8b58925301`이다. C6 CI43062798371은 Python2210PASS·기존 독립 실자료 HOLDOUT부재1SKIP·JS34PASS, main I CI43063509313 및 최종 J CI43072919702는 SUCCESS다. 이 숫자는 코드 회귀 근거이며 예측 정확도가 아니다.

이전 main F `66b790f…`의 실제 Gate43045049058은 Gate0~6 전부 PASS다. artifact13870728991은58,714,110바이트/SHA256 `d926c9ffa9ed462d0ef4936ea01c97f352c977ab46451e8746d9076c0a539635`이며 실제 bytes/digest 검증을 통과했다. 그 진짜 영수증을 PR50으로 일반 병합한 G `07c525118a141f5d96cb56e30b8b9779809682ec`에서 원래 release guard가262파일을 PASS했다. guard·검증 제외·golden/HOLDOUT을 완화하지 않았다. F와 I의 `full_clean_status=BLOCKED`는 추가 FULL/독립 예측 완료 조건이며, 필수 Gate0~6 PASS와 구분한다. F 증거를 I 실행으로 날짜만 바꿔 재사용하지 않았다.

### 실제 Future G 운영과 최신 I Gate

수동 Future43057867924는 **G에서 실제 SUCCESS**다. 같은 고정 Qwen의 native 반환5호출·완료5·유료 fallback0을 확인했다. 실제 게시 commit은 `1aad7a036182e252670085b510581f4fcf6d2af4`이고 worker lock은 IDLE로 해제됐다. 실행별 처리955는 처리 시도, body_ok455는 해당 처리 결과이며 실제 HTTP 요청 총수는 UNKNOWN이다. 최초 `new_documents_this_run=6073`은 기존 canonical backlog를 이 sidecar가 처음 발견한 수치다. 신규 RSS18 또는 신규 검증6원문에 더하지 않았다.

보존 검증은 F의646완료 버전·1836review·3992문서를 모두 유지했고, 현재651완료·1841review·4795문서로 늘었음을 확인했다. 판단·review·failure·target 유실/변경 drift0이며 F의 이미 완료된50Qwen결과도50/50보존됐다. 이5신규 Qwen은 C6의72GLiNER창과 별도다. Future G는 수동이며 F에서 통과한 guard를 사용했으므로 최신 I 릴리스 증거가 아니다. 상세: [ACTUAL_FUTURE_G_OPERATING_RUN.json](ACTUAL_FUTURE_G_OPERATING_RUN.json), [I_PRE_GATE_PRODUCTION_PRESERVATION.json](I_PRE_GATE_PRODUCTION_PRESERVATION.json).

안전한 terminal·불변 head·IDLE lock·F seal 보존 확인 뒤 최신 I의 실제 Gate43067179780을 시작했다. Gate0~6의 필수8단계가 모두 실제 SUCCESS다. 입력 root21개·전체 cache·고정230원문460파일 복원도 PASS다. reader_batch_limit1은 기존 지원 실행량 제한이며 qualification1/10/50 기준을 그대로 유지했다. I에서 새 Qwen1호출을 했고, F의 이미 완료된50자료는 재판독하지 않았다.

| 최신 릴리스 필드 | 최종 실제 검증 값 |
|---|---|
| I Gate43067179780 terminal·Gate0~6 |**SUCCESS,2026-11-12 02:20:21~02:49:09KST. Gate0/1·2·3·4·Stage5·Gate5·고정230복원·Gate6 전부 실제 SUCCESS** |
| 실제 I artifact ID·크기·SHA256 |**13877912797 /60,268,206바이트 /4dae80ee05be92ef6d7987c10817067c223a7f0e62eb9b03b46f3e5c582f6afe. 실제 ZIP 바이트 독립 검증 PASS. 만료2026-12-12 02:48:59KST** |
| 진짜 영수증 PR53·일반 병합 |**PR53, headceebce742d5b31c89c863cfad5bdbea59121a79f, CI43072575819 SUCCESS 뒤 일반 병합. 기존 metadata2파일만 변경** |
| 최종 main J·CI·unchanged guard |**5082723f515382a962184b36a31e34af17a7e07a /CI43072919702 SUCCESS /02:57:29KST unchanged guard PASS262파일. 검증 코드 I와 관측 코드 J는 기존 규칙상 제외된 영수증 metadata2파일만 다름** |

실제 I ZIP과 API run·job·artifact·tree를 기존 검증기로 대조했고, 원래28d0b8c6의 guard bytes·파일 제외 규칙은 변경하지 않았다. `prepare-receipts`는 PASS262파일·21root pins·모든 cache·compact460파일을 확인했다. 최신 J의 live API guard도 PASS다. [FINAL_GATES_I.json](FINAL_GATES_I.json), [RELEASED_MAIN_J_GUARD.json](RELEASED_MAIN_J_GUARD.json). 실제 [I Gate](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43067179780), [PR53](https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/53), [J CI](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43072919702).

### DB·원문·실패 후 회복의 보존

월별 generation6는 실제 읽기 전용 복원42989791426에서14자산/8테이블,42,601정량 버전·38,046숫자 관측·21,916물리량 관측과 새 프로세스 복원을 확인했다. generation5의60,049사건 행이 generation6의60,071행에 보존됐고 원격 head·asset·원래 DB는 바뀌지 않았다. 이는 사실 전용 capsule 복원이며 전체 원문·인용 복원이 아니다.

CPU 새 결과는 ACK20의 실제 SQLite8테이블·42완료 키로 새 프로세스 복원했고 기존41완료 키를 전부 포함했다. 보존 창1277→1349, span4905→5322, 제품 제안1326→1489, 과거 review20을 유지했다. 원 C5실패에서 암호화된24창은 정확한 run/attempt/cache/parent 바인딩을 확인해 재판독0으로 회복했다. 오래된 bridge ACK를 새 연구 결과로 세거나 실패한 runner의 미저장 작업을 복원했다고 주장하지 않았다. [DB_RESTORE.json](DB_RESTORE.json), [C6_ACTUAL_SEALED_RESULT_RECOVERY.json](C6_ACTUAL_SEALED_RESULT_RECOVERY.json)에 근거가 있다.

### 확인된 운영 결함과 수정의 범위

운영 원인군은 이 작업 범위에서10종이다. 이전에 보존한 별도6개 제품/추출 수정과 중복 합산하지 않았다. 초기8종에 이번 실제 실패로 확인한 URL export·stdlib import2종이 추가됐다. 시험 개수나 commit 개수로 결함 수를 늘리지 않았다.

| 원인군 | 수정·실행 근거 |
|---|---|
|1.잘못된 resume run·누락 pins/inventory·고정된 옛 origin 선택 |018f5bb1(PR44), 후속 be232a25/a3043227(PR48). 인증된 실제 archive/pins 복원과 F Gate PASS |
|2.DOE 공식 RSS2개 이전 |bd9ee610/018f5bb1. 공식 대체2개만 반영, 실제 운영 정상 응답·기존 기사 중복 확인 |
|3.같은 step에서 GITHUB_ENV RSS_RUN 재사용 |164019bed(PR44). 검증 ID 생성/소비 step 분리, 실제 신규 RSS→acquisition 바인딩 PASS |
|4.CPU 평가 이력 무제한 확장·거대 입력 |7d918860/164019bed와 PR48 compact/delta. 원래49GB evaluations를 제외하고 source/control 보존, 실제 bounded transport PASS |
|5.만료된 fixed230 artifact 참조 |8ae9fb871(PR45). 같은 fingerprint·230body/230raw 원본을 실제 F Gate에서 복원·QA PASS |
|6.정상 빈 RSS/Atom의 malformed 오분류 |7594788f/30d678757(PR46). 저장된 USGS원문 검증·실제 NO_NEW_INPUT 정상 처리 |
|7.REVIEW의 중복 Git authorization |6deb4f5/4f564d520(PR49). 실제 실패43033773972를 보존하고 수정 후 실제 REVIEW PASS |
|8.무해한 자동 all-skipped CPU run의 predecessor 오염 |ef97984c/606b0f4b/C4(PR49). API로 입증된 자동 inert skip만 허용, manual/failed/unknown 차단 유지 |
|9.원문 origin fragment와 strict export 충돌 |실제43057947172 RESUME_URL_NOT_CLEAN, C5 58817b1(PR51). strict sanitizer를 유지하면서 안전하지 않은 locator를 정확한 hash로 보존; 실제 후속 신규 판독 PASS |
|10.stdlib publisher가 무거운 분석 의존성 yaml을 import |실제43060982183 publishFAIL, ff29b9a를 포함한 C6 6e788d18(PR52). 분석 import 분리, 정확한 ciphertext 회복·후속 실제 publish/새 프로세스 복원 PASS |

PR47 보존 수명·compact corpus, PR48 upload-before-publication·attempt 이름·공개 receipt·Pages 연결은 복구 능력과 무결성 보강으로 기록했다. 이전 실제 artifact 유실 사고가 입증되지 않은 부분을 별도 운영 사고로 꾸미지 않았다. fixture timing·동결 자산 매핑·host/interpreter·lint·반복 시험 수정도 추가 운영 결함으로 세지 않았다.

기존 SEC·Census·EIA·USGS·TED·USAspending Q1/Q2 연결기와 원래 수동 운영 경로는 보존했다. 이번 후속 복구에서 이들 전체를 새로 실수집하거나 정기 활성화하지 않았다(NOT_RUN). generation6 검산 PASS는 새 수집 PASS나 수급 사건 수가 아니며, 실제 새 판독은 위 RSS 공식 원문 계보로 별도 입증했다.

## E. 남은 한계와 소유자 조치

RSS는 여전히11개 upstream에서 막힌다.7개 ESA404와4개 DOE transport(1network-unreachable·3TLS-EOF)이며 정확한 source 이름·ID·마지막 저장 예외는 [CURRENT_RSS_SOURCE_BLOCKERS.json](CURRENT_RSS_SOURCE_BLOCKERS.json)에 있다.4개 URLError의 HTTP status·궁극 원인을 추정하지 않았고 확인되지 않은 대체 URL을 만들지 않았다. USGS정상 빈 피드는 파싱 복구이며 새로운 광물 근거 확보는 아니다.

제품 제안163개를 검증된 제품163개로 보고하지 않는다. 완독한1문서는 다섯 TARGET 필드가 없어 evidence HOLD이며, 미완독5문서/60창/공백 제외10,274자가 남아 있다. 완독 사례 적격 독립쌍0, 부분 문서 전체는 UNKNOWN/public null이다. 신규 적격 S2/S3각0, 기존 개발 TP1/FP4/FN24는 개선됐다고 보고하지 않는다. 독립 실자료 HOLDOUT이 없어 예측 성능은 BLOCKED다. 의미 검토18버전 영수증은 전부 PENDING이며 완료0이다.

예약 CPU 변수 쓰기를 기존 정상 권한 경로로 실제 시도했으나 `BCT_V4_CPU_CODE_SHA` PATCH가403 `Resource not accessible by integration`으로 거절됐다. ENABLED쓰기 시도는 하지 않았으며 최근 실제 실행 로그의 설정은 옛 `da7cb9bc…`/false다. 권한을 우회하거나 새 키·토큰을 요구하지 않았다. [C6_REPOSITORY_VARIABLE_WRITE.json](C6_REPOSITORY_VARIABLE_WRITE.json)에 정확한 응답을 보존했다.

**소유자가 해야 하는 설정은 한 번이다.** 최신 I Gate·진짜 릴리스 영수증·최종 main J guard가 모두 PASS이며(D), 저장소 **Settings → Secrets and variables → Actions → Variables**에서 기존 항목을 편집한다.

- `BCT_V4_CPU_CODE_SHA = 6e788d18cf85fdb834b451bb35585a8b58925301`
- `BCT_V4_CPU_RESEARCH_ENABLED = true`

개발 브랜치 최신 문서 SHA나 main J SHA를 CODE 변수에 넣지 않는다. 위 C6는 실제 버그 수정·회귀시험·신규 원문 왕복을 통과한 실행 코드이며 기존 승인 모델/seed/weights는 유지했다. 다른 모델·Secret·API key·새 토큰 변경은 필요하지 않다. RSS AI API 설정 부재로 해당 의미 판독이 SKIP된 상태도 별도로 유지하며 유료 키 추가를 소유자 조치에 포함하지 않는다.

설정만으로 예약 성공이나7일 운영 PASS를 선언하지 않는다. 첫 실제 예약 수집→CPU→private ACK·새 프로세스 복원→REVIEW/Pages가 기준을 만족한 시점의 실제 run/시각부터7일을 센다. 현재 수동 전체 왕복 성공은 입증됐지만 예약7일 시작은 NOT_STARTED다. 입력 보존·compact cache가 있어도 진짜 Gate-proof 갱신은 동일 최신 코드의 실제 Gates·진실한 receipt PR이 필요하다. 오래된 증거 사본이나 partial checkpoint로 자동 갱신됐다고 보고하지 않는다.


최종 완료 판정은 **개발 코드 정상화 PASS(확인된 운영 결함과 릴리스 범위)**, **실제 예약 전체 운영 BLOCKED(설정403/CPU44SKIP)**, **미래 병목 예측 성능 BLOCKED(실제 독립쌍·HOLDOUT·Q6 미입증)**로 분리한다. 배포·수동 판독 성공을 예측 성능 또는 예약 성공으로 바꾸지 않는다.

정상본 보존: 기존 CPU41완료 키·1,277창·20검토·원래 monthly generation5/6와 frozen 평가를 유지했다. 첫 실패는 이전 private ACK를 변경하지 않았고, 이후 암호화된24창은 원래 producer/부모 CAS를 유지해 재판독 없이 회복했다. main 강제 push·기존 DB 초기화·검증 우회0이다. 현재 새 CPU 상태는42완료 키/1,349창이며 원래41키를 정확히 포함한다.

릴리스 artifact 만료2026-12-12 02:48:59KST 이후에는 실제 최신 코드 Gate와 진짜 영수증 갱신이 필요하다. 자동 input 보존은 가능하지만 과거 proof의 날짜만 갱신하거나 자동 PASS시키지 않는다.

기존 운영 보고서는 [증거 커밋2571a13의 원본 REPORT](https://github.com/irewon1-lgtm/bottleneck-control-tower/blob/2571a1375d00a98d19304b4492d1dcdaf5f7f689/docs/v4/operations-recovery-20261111/REPORT.md)에 보존했고, 최초 full-pipeline-debug 보고서·원래 평가·정답도 수정하지 않았다. 진행 정본은 기존 [PROGRESS.json](../PROGRESS.json)의 동일 quantitative_plan 하위다.

실행 증거 링크: [C6 CI](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43062798371), [신규 CPU 완독](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43064155117), [REVIEW](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43064438463), [데이터 연쇄 Pages](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43064438487), [최신 예약 RSS](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43069839035), [원문 확보](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43070231555), [CPU 자동 SKIP](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43071173782).
