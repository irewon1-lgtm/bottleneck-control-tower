# 최근 7일 실패·SKIPPED 원인 분류

기준은 `/tmp/bct-final-7day-actions.json`의 고정 창 **2026-11-04 17:15:22 UTC ~ 2026-11-11 17:15:22 UTC**다. main의 자동 이벤트(`schedule`, `workflow_run`, `repository_dispatch`)만 포함했다. 실제 60 FAIL 및 53 SKIPPED의 해당 시도 job/step 메타데이터를 모두 조회했고 누락은 0이다. 원문·모델·artifact 재다운로드와 원격/DB/Git 쓰기는 0이다.

| 실패 그룹 | 실행 수 | 실제 첫 실패 단계와 확인된 원인 |
|---|---:|---|
| Future bottleneck body candidates | 56 | 전부 `Verify actual code release gates before automatic candidates`. head28d0b8c6 54회,7ab99db 1회,933a296 1회. 각 코드 head의 대표 로그 1개씩은 `ValueError: validated code/test file set changed or missing`를 확인했다. 나머지 53개의 예외 문자열까지 전수 조회했다는 주장은 하지 않는다. |
| RSS live environment check | 1 | run42128685872의 DB 게시 Git push에서 원격이 `fatal error in commit_refs_rules`로 거부. 수집/파싱 실패가 아니다. GitHub 참조/규칙 처리의 더 세부 원인은 UNKNOWN이며 권한·규칙 설정 오류로 단정하지 않는다. |
| REVIEW input receive | 1 | run42502046388에서 `evaluations/<hash>.json`까지 ZIP을 풀다가 `no space left on device`. |
| REVIEW public catch-up | 2 | run43033762121 및43033773972의 동일 public catch-up 단계에서 `ValueError: PUBLIC_DATA_GIT_FAILED`. 두 실제 로그 모두 확인했다. 자세한 stderr는 helper가 숨기므로 HTTP400/중복 인증의 근거는 별도 복구 재현·수정 증거와 연결해야 한다. |

| SKIPPED 그룹 | 실행 수 | 확인 가능한 정확한 범위 |
|---|---:|---|
| CPU automatic | 43 | 실제 모든 job이 SKIPPED. 해당 head의 연구 job 조건에는 고정 CODE_SHA 일치, enabled=true, main 및 상위 성공이 필요하다. 과거 개별 실행의 Variables 값이나 상위 이벤트 payload는 이 메타데이터에 없어 추정하지 않는다. 현재는 실제 publisher 문맥에서 옛 CODE/false와 설정 PATCH403을 별도로 확인했다. |
| Future | 1 | `workflow_run` 자동 경로의 상위 성공 조건이 충족되지 않아 candidates job이 SKIPPED; backlog job은 수동 전용이라 SKIPPED. |
| Acquisition | 1 | 상위 RSS의 성공/main/비PR 조건이 충족되지 않아 acquire job SKIPPED. |
| REVIEW | 2 | 실제 shadow job guard가 false. 활성화/main/동일 저장소/비PR 조건을 해당 역사 head에서 읽어 보존했다. 개별 false predicate는 저장된 upstream payload가 없으므로 만들어내지 않는다. |
| Pages | 6 | source/build 진입 조건이 false여서 하위 needs job도 SKIPPED. 검증된 개발 push 또는 허용된 main 이벤트 조건에 따른 진입 차단이며 실제 배포 실행 실패로 세지 않는다. |

상위 RSS 실패와 Future/Acquisition 각 1회 skip은 동일 시간대지만, 직접 연결되는 upstream ID는 API 메타데이터에 없으므로 임의 지정하지 않았다. **53 = CPU43 + 비CPU10**이다.

이 표는 과거 실패를 삭제하거나 현재 수정 후 PASS로 바꾸지 않는다. wrapper SUCCESS와 실제 판독 완료 역시 별개다. 세부 run IDs, 실제 job/step, 정확한 역사 workflow guard와 대표 오류 7개는 JSON에 있다. 오프라인 합계 검산 PASS.
