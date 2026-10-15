# V4 연구 자료와 배포 연결 복구

## 실제 출처 확인

- 사용자 비공개 URL: https://bct-v4-dashboard.ire-won1.chatgpt.site
- 최초 배포 Sites source commit: `9c3af39bfc548991113e374d1c998aa6db4ba2b1`.
- 복구 전 실제 HTTPS API: 본문40, 근거549, 검토23, 대기295,
  데이터 기준 `2026-10-14T13:46:34.942618+00:00`, 코드/동기화 metadata 없음.
- 기존 GitHub Pages는 `.github/workflows/ui-pages.yml`에서 main 코드와
  data의 `canonical.sqlite3/state.json`을 사용한다. V4 개발 브랜치 자료를 읽지 않는다.
- 이번 수정의 원격 기준: 개발 브랜치 `codex/bct-v4-integration`,
  SHA `5bb8d2d1d4496a27a253dd6a9ffe7d63b7d4457b`.
- 최신 post-ui 백업은 기존 Reader의 PROGRESS 포인터로 복원한다.
  cpu-recovery는 별도 DB였으므로 읽기 전용 projection을 추가했다.

## 실제 데이터 연결

post-ui: 본문235, 전 산업 근거511(원본549 보존), 기존 검토23, 대기2.
cpu-recovery: 별도 판독38문서,230111/231283자, 표기 제안1186,
공식1차 확인 전 보도 검토6, 공식1차 검증0, 엔진 최종 채택0.
새 S1/S2/S3는0/0/0. 표기 제안·기존 근거·새 보도 검토를 합쳐 후보로 세지 않는다.

CPU 백업의 압축파일 SHA256,8개 표 전체 내용 해시,문서 본문 해시,
각 표기와 검토 인용의 정확한 위치를 실제 대조한다. 불일치 시 실패한다.
DB는 메모리의 query_only 복사본으로 읽고,연구 DB writer·모델·수집기를 호출하지 않는다.
현재 조회 가능한 상세는511+1186+6=1703개이며 의미 정확도와는 별개다.

화면은 기존 네 화면을 유지한다. 한눈에 보기에 최신 별도 CPU 연구 범위를
추가하고 판단 근거에 자료 범위별 탭·기존 검색/필터/상세를 재사용한다.
코드 SHA·데이터 기준 시각·마지막 동기화 시각·자동 배포 연결 대기를 표시한다.

## 코드와 데이터의 자동 처리 계약

지정 개발 브랜치 `codex/bct-v4-integration`의 push/PR을 release gate가 감지한다.
Netlify도 연결 후 이 브랜치를 production으로 지정하고 동일한 build gate를 실행한다.
main·data·기존 Pages workflow는 수정하지 않는다.

매 build는 해당 commit의 PROGRESS 포인터·post-ui 백업·CPU 백업과 검증
보고서를 함께 읽어 화면용 자료만 생성한다. 코드만 바뀌면 원문 DB를 변경하지 않는다.
새 연구 bundle이 commit되면 같은 검증 후 자료를 재생성한다. 운영 DB의 쓰기·
수집/AI 분석·미검증 후보 승격은 자동화하지 않는다.
현재 235/511/2와1186/6을 고정하는 회귀시험은 이 corpus의 사실 계약이다.
다른 corpus를 반영할 때는 해당 corpus의 독립 검증과 기대 결과도 함께 갱신해야 한다.
수치가 다르면 그 자체를 통과시키기 위해 검증을 생략하지 않는다.

## 검증 상태와 제한

- 로컬 Python22 PASS,기존 Node UI8 PASS.
- 실제 DB로1703개 상세 인용·해시 대조 PASS,조회·download·쓰기/파일 경계 검사 PASS.
- 압축 백업·표 해시·집계 불일치 반례3종은 실제 거부했다.
- 첫 전체 CI는1428 PASS/1 skip와 과거 UI byte 고정 검사1 FAIL이었다.
  이번 요청의 명시된 UI 변경과 충돌한 과거 기준이다. 당시 app.js/style.css
  원본을 frozen-assets에 그대로 보존해 초기 seal과 대조하고,현행 UI는 새
  기능·release gate로 검사한다. 연구/원문/DB 보존 기준은 변경하지 않는다.
- 최종 개발 SHA `f78126fc492a8cbe883a68910f54591380cab92e`를 실제 push했다.
  전체 CI: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38658099871
  Python 1429 PASS / 1 SKIP, Node 34 PASS.
  배포 gate: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38658100128
  Python 22 PASS, Node UI 8 PASS, 1703 상세 검증 및 접근제어 검사 PASS.
- 두 CI 성공 이후 Sites의 기존 소유자 전용 URL에 수동으로 저장·배포했다.
  Sites source SHA `36f5c2508b9a2eb93b57e66ba3222129d6d776ff`,
  배포 ID `appgdep_6ad019a9db5881918cd4c2f2159bf724`, status succeeded.
- 실제 HTTPS API 대조 결과는 SYNC_AFTER.json에 기록했다.
  코드 SHA·235/511/23/2·CPU 1186/6·미래 후보 0 일치,
  CPU/보도 상세 인용·download JSON 일치 PASS.
  비인증 화면/API/export/detail 모두 403, 서버 소스/DB 경로 404 PASS.
- 실제 PC 브라우저에서 네 화면 전환, 최신 CPU/보도 탭, PrSM 검색(2건),
  공급 감소 필터(3건), 원문 상세, 후보0, AI 자동 판독 중단 표시,
  새로고침 및 재접속 후 최신 코드·자료 표시를 확인했다.
- 브라우저 파일 저장은 일반 클릭과 downloadMedia 모두 실패했다.
  HTTPS export의 200/attachment/JSON 동일성 검사는 통과했지만
  실제 브라우저 저장은 PASS로 처리하지 않는다. 브라우저는 실패 원인을
  제공하지 않았다. 사용자 PC에서의 저장 가능 여부도 미확인이다.
- 모바일 시뮬레이션 및 실제 휴대폰: NOT_RUN.
- GitHub push→자동 테스트는 PASS. 이후 자동 배포·자동 연구 갱신·실패 시
  이전 배포 유지의 실제 전체 과정은 BLOCKED/NOT_RUN이다.
  이번 Sites 반영은 수동 배포이며 지속 CI/CD 성공으로 세지 않는다.

Netlify project `def4b8b3-4d62-4eb6-9813-b2332f1e1b17`은 현재 미배포이며
Git 미연결이다. 앞선 GitHub `Authorize Netlify` 클릭은 자동 승인 검토에서
계정 범위의 "act on your behalf" 및 resource 접근에 대한 명시 승인이 없어 거부됐다.
이번 요청에는 그 계정 범위 권한의 별도 승인이 없으므로 이를 우회하지 않았다.
소유자 한 명만 허용하는 기존 Sites 인증은 유지한다.

지속 자동 배포가 연결되기 전에는 최신 자료의 검증된 최초 반영만 수행하고,
push→자동 배포→동기화 전체를 PASS 또는 완료라고 쓰지 않는다.
최소 재개 조건은 명시적으로 승인된 GitHub–Netlify 계정 연결 후 BCT 저장소와
위 개발 브랜치를 지정하는 것이다. 이어서 성공·실패 commit 자동 publish/차단과
기존 URL 보호를 실제 확인해야 한다. 비용·유료 플랜 변경은 허용하지 않는다.
