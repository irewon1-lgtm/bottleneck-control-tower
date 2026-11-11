# 최근 7일 실패·SKIPPED 최신 분류

고정 창: **2026-11-04 18:00:41 UTC ~ 2026-11-11 18:00:41 UTC**. 기준 메타데이터 `/tmp/bct-final-7day-actions-LATEST.json`의 main 자동 이벤트만 포함한다. 현재 자동 339회는 **SUCCESS213 / FAIL60 / SKIPPED54 / CANCELLED11 / QUEUED1**이다. SUCCESS는 실제 판독 완료 수와 별개다.

기존 분류 중 112건을 조건이 같은 실행·시도로 재사용했다. 오래된 Future 실패41881922653은 창 밖으로 빠졌다. 새 Future43070231522와 CPU43071173782의 해당 시도 job만 각각 추가 조회했고, 새 Future 오류 로그 1개만 확인했다. 합계 **60 FAIL +54 SKIPPED =114건**을 모두 확인했다. 이전 JSON·MD는 변경하지 않았다.

| 실패 그룹 | 수 | 실제 첫 실패 단계·오류 |
|---|---:|---|
| Future 릴리스 검증 | 56 | 전부 `Verify actual code release gates before automatic candidates`. 옛28d0b8c6 53회/7ab99db 1회/933a296 1회는 각 head 대표 로그에서 파일 집합 불일치를 확인. 새 I5c66cd8의43070231522는 아래처럼 **파일 내용 불일치**였다. |
| RSS 게시 | 1 |42128685872의 Git push가 원격 `fatal error in commit_refs_rules`로 거부. 세부 GitHub 내부/규칙 원인은 UNKNOWN이며 피드 수집 오류로 세지 않는다. |
| REVIEW 입력 | 1 |42502046388에서 evaluations 이력까지 ZIP을 풀다가 `no space left on device`. |
| REVIEW public catch-up | 2 |43033762121·43033773972의 `PUBLIC_DATA_GIT_FAILED`; 자세한 중복 인증 진단·복구는 별도 실증과 연결한다. |

새 I 실패 **43070231522 / job130695807185**, 2026-11-11 17:39:28 UTC의 실제 오류는 다음과 같다.

`ValueError: main operating code differs from actually validated code`

이는 I의 감시 파일 목록이 F와 같은 262개여도 workflow 파일 내용이 당시 연결된 F 증거와 달라 보호 장치가 중단시킨 것이다. **PR53의 새 실제 I Gate 영수증이 연결되기 전의 역사적 실패**다. root가 별도 실제 증거로 확인한 현재 J `5082723…`의 Guard262 PASS 및 CI43072919702 SUCCESS를 이 과거 I 실패로 덮어쓰지 않는다. 본 분류 작업이 J 검증을 새로 실행한 것은 아니다.

| SKIPPED 그룹 | 수 | 확인 범위 |
|---|---:|---|
| CPU 자동 |44|모든 job이 실제 SKIPPED. 고정 CODE_SHA 일치·enabled=true·상위 main/성공 조건이 필요하다. 새 I의 CODE 기대값은 검증된 C6 `6e788d18cf85fdb834b451bb35585a8b58925301`. 현재 옛 CODE/false와 PATCH403은 별도 실제 publisher 문맥에서 확인됐으며, 과거 각 skip의 Variables 값이나 특정 상위 실행 ID는 만들어내지 않는다.|
| Future|1|상위 성공 조건 불충족으로 자동 candidates 경로 SKIPPED. 수동 backlog 경로도 해당 이벤트에서 SKIPPED.|
| Acquisition|1|상위 성공/main/비PR 진입 조건 불충족.|
| REVIEW|2|활성화/main/동일 저장소/비PR job guard가 false; 정확한 당시 표현식을 보존.|
| Pages|6|source/build 진입 조건이 false여서 하위 needs job도 SKIPPED. 실제 배포를 실행하다 실패한 것으로 세지 않는다.|

**54 = CPU44 + 기타10**. 새 예약 RSS43069839035 및 acquisition43070231555의 성공은 별도 실행 증거이며, 이 분류에 없는 upstream payload를 근거 없이 연결하지 않는다. 현재 J의 운영 상태와 수동 LIVE 성공, 예약 CPU 설정 차단, 예측 성능 미증명은 각각 구분한다.

오프라인 검산 PASS. 신규 조회는 job 메타데이터 2개·대표 로그 1개뿐이며, 원문·모델·artifact 다운로드와 원격/DB/Git 쓰기는 0이다. 상세: `/tmp/bct-final-failure-classification-LATEST.json`.
