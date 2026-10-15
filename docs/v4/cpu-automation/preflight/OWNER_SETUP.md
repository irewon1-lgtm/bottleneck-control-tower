# 소유자 1회 설정 — 비공개 CPU 연구 저장

현재 전용 저장소 조회는404, 생성은403(`Resource not accessible by integration`)이다. 현재 Codex 인증으로 저장소/Actions Secret 설정을 완료할 수 없다. 기존 Groq 키는 변경하지 않는다. 이 안내는 GitHub 소유자 계정에서 한 번 수행한다. **토큰이나 암호화 비밀값을 채팅·이슈·로그에 보내지 않는다.**

## 1. 비공개 저장소

[GitHub 새 저장소](https://github.com/new)에서 다음과 같이 만든다. 이미 동일 저장소가 있다면 새로 만들지 않고 해당 저장소의 비공개 여부와 접근을 확인한다.

| 항목 | 값 |
|---|---|
| Owner | `irewon1-lgtm` |
| Repository name | `bct-v4-private-state` |
| Visibility | **Private** |
| README / .gitignore / License 초기화 | 모두 선택하지 않음 |
| 유료 서비스·요금제 | 변경 없음 |

이 저장소는 DB/복원 증거만 보관한다. Actions·수집기·모델 설치·화면 배포는 추가하지 않는다. 다른 비공개 프로젝트에는 데이터를 섞지 않는다.

## 2. 해당 저장소만 쓰는 인증정보

GitHub 오른쪽 프로필 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.

| 항목 | 값 |
|---|---|
| Token name | `BCT V4 private state writer` |
| Resource owner | `irewon1-lgtm` |
| Expiration | 30일 등 관측기간을 포함하는 제한된 기간 |
| Repository access | **Only select repositories** |
| Selected repositories | **`bct-v4-private-state` 하나만** |
| Repository permissions → Contents | **Read and write** |
| Metadata | Read-only(자동 부여) |
| 그 외 권한 | No access |

`All repositories`, classic PAT, 공개 `bottleneck-control-tower` 선택은 사용하지 않는다. 기존 RSS 인증/브랜치 보호는 바꾸지 않는다. 이 토큰으로 공개 main/data 쓰기를 시도했을 때403/404가 나오는지 게시 작업이 별도로 확인한다. 기존 ref 생성이422로 거절된 것은 쓰기 권한 거부로 인정하지 않는다. 기존 ref 생성 요청은 해당 ref를 갱신하지 않는다.

## 3. 공개 저장소의 Actions Secret 두 개

[공개 저장소 Actions 설정](https://github.com/irewon1-lgtm/bottleneck-control-tower/settings/secrets/actions) → **Secrets → New repository secret**.

| 이름 | 값 |
|---|---|
| `BCT_V4_PRIVATE_STATE_TOKEN` | 위에서 만든 비공개 저장소 전용 fine-grained token |
| `BCT_V4_STATE_PASSPHRASE` | 새 무작위 64자 수준의 암호화 비밀값(40~256자, 줄바꿈 없음) |

두 Secret이 이미 있다면 덮어쓰지 않고 기존 설정을 확인한다. 두 번째 값은 GitHub 쓰기 권한이 없는 DB 전달용 암호다. CPU와 게시 실행기 사이의 공개 Actions 캐시에 **평문 DB를 올리지 않기 위해** 사용한다. 처음 생성할 때만 기존 도구로 값을 출력하지 않고 Secret에 넣으려면, 소유자 본인의 인증된 로컬 터미널에서 다음 한 줄을 사용할 수 있다. Codex 채팅에 값을 붙여넣지 않는다.

```bash
openssl rand -base64 48 | tr -d '\r\n' | gh secret set BCT_V4_STATE_PASSPHRASE --repo irewon1-lgtm/bottleneck-control-tower
```

기존 `GROQ_API_KEY`·RSS Secret·Actions 기본 쓰기 권한은 변경하지 않는다. 전용 토큰은 CPU job에서 참조하지 않으며, 모델/수집 아티팩트를 실행하지 않는 별도 게시 job의 권한 확인·게시 step에만 제공한다. 토큰은 Git remote URL·인자·설정 파일에 저장하지 않는다.

## 4. 같은 화면의 Variables 탭

**Variables → New repository variable**에 다음을 등록한다.

| 이름 | 값 |
|---|---|
| `BCT_V4_CPU_CODE_SHA` | 이 작업 최종 보고의 CI 성공 개발 커밋 **전체40자 SHA** |
| `BCT_V4_CPU_RESEARCH_ENABLED` | **`false`** |

지금은 `true`로 바꾸지 않는다. 권한 실제 거부, 원문 비공개 보관 범위와 원격 DB 복원 검증이 남아 있다. main/data 보호를 새로 설정할 필요는 없다. 현재의 연구 적용안은 모든 GitHub 기본 권한이 `contents:read/actions:read`이며, 별도 토큰만 비공개 저장소에 쓴다.

## 설정 후 이어서 실행할 검증

소유자 설정 후에는 추가 키를 요청하거나 캐시/CPU를 다시 설치할 필요가 없다. 기존 승인 범위에서 다음을 이어간다.

1. 검증된 `activation-change.yml.proposed`를 최소 main workflow로 적용하고, 수동 `purpose=verify-scope`로 **비공개 쓰기201 및 공개 main/data403/404**를 실제 확인한다. 이 실행은 CPU 정기 실행이 아니다.
2. 기존 원문3건의 정확한 raw/body 버전에 대한 **비공개 보관 범위**를 확인한다. Defense News의 개인·비상업적1부 다운로드 허용만으로 Git 다중 백업까지 승인하지 않았으며, Electrek의 연결된 개인정보 정책은 보관 허가가 아니다. 소유자 설정만으로 이 항목이 해제되지는 않는다. 원본을 삭제/교체하거나 사용자에게 임의 권리 승인을 입력하도록 요구하지 않는다. 허가·이용 조건이 확인된 버전만 정책에 반영한다.
3. 허용된 기존 DB를 `purpose=seed`로 비공개 저장 → 원격 재조회 → SHA/8개 테이블 복원까지 확인한다. 캐시에는 암호화한 전달본만 저장한다. 없어지거나 손상되면 중단하며 빈 DB로 초기화하지 않는다.
4. 보호 조건이 모두 통과한 뒤에만 적용안의 잠금을 해제하고 enabled를 `true`로 설정한다. 기존 RSS/precursor 성공 후 후속 CPU만 연결한다. 추가 RSS 예약은 없다.
5. 실제 예약에서 신규 원문 판독/정확 위치 검증/비공개 영속 저장·복원/게시 확인 기록이 처음 성공한 시점부터7일을 기록한다. 수동 seed, 빈 큐, 로컬 합성 시험은 시작으로 세지 않는다.

현재 main용 CPU 캐시는 이미 준비됐으므로 재다운로드/재설치하지 않는다. DB 압축16MiB·연구 Git 전체 고유 객체64MiB·캐시8GiB 안전선과4스레드/24창/45초/명령120초를 유지한다. 외부 AI0, 자동S2/S3/LIVE0이다. 공개 UI에는 원문/DB/인용을 직접 보내지 않으며 현재 UI는 변경하지 않았다. 향후 공개 전달은 검토된 요약 수치·상태·허용된 원문 링크로 한정한다.

오래된 암호문 캐시로 재판독하지 않도록 모델 로드 전에 이전 게시 작업의 성공·실행 ID/attempt 일치도 확인한다. 이전 저장 실패, 오래된 캐시, 캐시 소실 시에는 CPU만 멈추고 비공개 원본에서 기존 DB를 복원해 암호화 전달본을 다시 발행한다. RSS는 유지하며 빈 DB 초기화나 같은 실패의 자동 재시도는 하지 않는다.
