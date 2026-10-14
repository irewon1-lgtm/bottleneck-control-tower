# V4 자동 배포 인계 상태

## 현재 판정: BLOCKED

기존 `https://bct-v4-dashboard.ire-won1.chatgpt.site` 비공개 사이트는 보존했다.
이 문서는 자동 배포가 작동한다는 완료 보고가 아니다.

## 준비한 구체적 구성

- 개발: `codex/bct-v4-integration` (기존 개발·연구 보존).
- 배포: `deploy/bct-v4-dashboard` (검토를 마친 대시보드 변경만 Codex가 통합해 push).
- GitHub push → GitHub release gate 및 Netlify 동일 build gate → 성공 시 Netlify atomic deploy.
- 미완성 개발 push는 배포 대상이 아니다. 배포 브랜치의 시험 실패도 Netlify publication을 차단한다.
- Netlify production branch는 배포 전용 브랜치 하나로 제한하고 preview·branch deploy는 활성화하지 않는다.
- Netlify 원본 Function은 서버 비밀 헤더 없으면 화면·API·download 전부 403.
- 기존 Sites는 본인 인증을 유지하는 고정 gateway가 되어 보호된 Netlify 원본을 읽는다. 사용자 URL은 동일하다.
- gateway에는 목적지 pinning, 경로 allowlist, 읽기 전용, redirect 거부, cookie·identity 전달 금지를 적용했다.
- 원본 보호 확인 전에는 기존 Sites를 gateway로 바꾸지 않는다.

## 데이터와 코드

코드 버전은 Netlify `COMMIT_REF`로 `/api/health`와 응답 헤더에 기록한다.
연구 데이터 버전은 SQLite SHA256·`data_at`로 별도 기록한다.
코드만 바뀌면 동일한 검증된 연구 백업을 그대로 사용한다.
새 운영 DB를 직접 읽거나 변경하지 않으며 collector·AI를 활성화하지 않는다.

연구 갱신은 source snapshot·verification·analysis·원문/공식 표 근거를 일관된
묶음으로 배포 브랜치에 반영할 때만 가능하다. 백업 해시·DB 형식·인용·표
일치를 다시 검증한다. 현재 회귀시험은 동결된 549/23/295/0 범위를 기준으로
하므로 다른 corpus를 승격하려면 해당 corpus의 독립 검증과 시험 기준 갱신이
먼저 필요하다. 운영 연구 DB를 무검증으로 자동 동기화하는 경로는 없다.

## 비용·자원

Netlify team `ire-won1`: Free, $0/month, 300 credits/month,
설정 확인 당시 잔여 300/300, 화면에 no overage charges ever 명시.
유료 플랜·추가 결제·Agent Runner·AI Gateway는 사용하지 않았다.
무료 한도 소진 시 정상 운영을 무한 보장하지 않는다.

새 Netlify project: `bct-v4-ci-origin`, ID `def4b8b3-4d62-4eb6-9813-b2332f1e1b17`.
아직 Git 저장소 미연결·배포 없음·private 상태다.
원본 인증 비밀은 Netlify Functions secret으로만 생성했으며 파일·GitHub에 넣지 않았다.
`.netlify/`는 gitignore에 추가했다.

## 현재 실행 증거

- 로컬 Node 기존 UI 회귀 8 PASS.
- 실제 검증된 DB로 포장·549 상세 근거·조회/다운로드/경로 boundary PASS.
- 원본 인증 누락·틀린/다중 바이트 키 거부, gateway 목적지·redirect·쓰기 제한 PASS.
- 로컬 pytest: BLOCKED (현재 환경에 pytest 없음). GitHub/Netlify는 build 시작 시 pytest를 설치한다.
- GitHub push와 원격 CI: 이 문서 게시 후 실제 결과를 확인한다.
- 첫 실제 push CI `38593853498`는 공통 conftest가 요구하는 PyYAML 누락으로 FAIL.
  기존 project 의존성을 함께 설치하도록 최소 수정 후 새 commit으로 재시험한다.
- GitHub push → Netlify 자동 배포 → 기존 URL readback: NOT_RUN.
- 실제 실패 커밋의 이전 정상 버전 보존: NOT_RUN.

## 차단 원인 및 최소 재개 조건

Netlify의 GitHub 연결 UI가 `Authorize Netlify`를 요구했다.
GitHub 화면은 identity 확인·resource 범위 확인·사용자를 대신한 작업 및 email read 권한을 표시했다.
자동 승인 검토가 이 클릭을 거부했다. stated reason:
"The click would grant Netlify a consequential GitHub OAuth authorization with broad
act on your behalf and resource-access permissions, but the user did not explicitly
approve this exact account-wide scope; inspect or obtain narrower authorization first."

권한 연결을 다른 경로로 우회하지 않았다. 이 계정 연결 권한의 명시 승인 후,
가능하면 BCT 저장소만 설치 범위로 선택한다. 다른 민감한 권한 확장 요청이
표시되면 그 실제 범위를 따로 확인한다.

다음 순서: 승인된 GitHub 연결 → BCT 저장소·배포 브랜치 지정 → 동일 gate
Netlify 실제 실행 → 원본 인증 확인 → 기존 Sites gateway 최초 배포 →
성공 test commit 자동 배포 확인 → 실패 test commit 차단·기존 version 유지
확인 → 실패 변경 revert 및 마지막 정상 branch 상태 확인.

최종 검증 전에 자동 배포 완료라고 보고하지 않는다.
