# BCT V4 — 세션 7 자동 수집·원문 분석 연결 복구 (2026-11-13 KST)

## 마지막 검증된 스냅샷

- RSS `data` HEAD `da7b17f34d58c69c72b5d067d6279ec98db8bb44`, canonical DB SHA-256 `39d6d562d398a60ce1345ec6a6d84a512a56d5c3994593fa25a4be2b25337b06`
- 전체 RSS 10,510건, 기존 `future-bottleneck-data` 레코드 8,145건, 최초 미연결 2,365건.
- 구분: 기사 제목·요약 전수 분류는 10,510/10,510 완료지만 본문 FULL 확보와 독립 수요·공급 적격쌍 검증은 별개이다.
- 연구 S6의 45건 엄격 교차검증은 독립 적격 수요·공급쌍 0건이며, 전체 산업에 병목이 없다는 뜻은 아니다.

## 실제 운영 장애 2개를 복구

1. 운영 `config/bct-operating-release.json`이 옛 Gate #43160725360을 가리켜 현재 main의 코드와 맞지 않았다.
2. 최신 성공한 운영 Gate #43330584731 (head SHA `a897e80d392911c4ea9dc4dc3a44908aa83dab3a`)에 대한 8개 필수 단계, JOB 및 보관 아티팩트 SHA-256을 직접 검증:
   - Gate artifact `13997366989` / `f3c1108864301c34cdf8415914acb124db73d11673c89d82f5275bfa6a86876e`
   - `config/bct-operating-release.json` 갱신 커밋 `7a2b87d9867debaf46aee5f9a229c62eba50f95d`.
3. 첫 테스트는 기존 `.github/bct-recovery-request.json`이 옛 아티팩트 원문을 참조해 실패했음.
4. 새 Gate의 실제 ZIP을 확인해 21개 필수 root 파일 SHA-256, 3,700개 보관 캐시 원문 SHA-256, 목록 인벤토리 digest `d70e243113c5cb199d510cf5bb4dd477eee4037d478c0cb829afc3de8f116045`를 검증함.
5. 복구 요청 파일의 실행 ID·아티팩트·21개 파일 해시·보존 캐시 목록을 같은 실제 성공 Gate로 바인딩. 파일 SHA 64자리 오타 1건까지 수정.
6. 최종 Stage 0 전체 자동 검증 **PASS**: [GitHub #43347645753](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43347645753).

## 기존 무료 CPU 자동화 재실행

- 본문 분석 코드를 새로 작성하거나 고정된 병목 판정 조건을 완화하지 않음.
- RSS 수집: 기존 `rss-live-check.yml` 주기 실행 유지.
- 새 원문 수집: 기존 `precursor-acquisition.yml`이 RSS 성공 후 신규 기사 대상을 처리.
- 과거 적체와 신규 RSS: 기존 `future-bottleneck.yml`의 매일 07:45 / 19:45 KST와 RSS 완료 트리거 유지.
- 본문 분석 작업의 기존 한도는 300개씩 최대 3회 + 조건부 복구. 실 데이터 저장은 기존 `future-bottleneck-data` CAS writer가 소유.
- Gate 승인과 복구 요청 동결을 완료한 뒤 main `docs/v33-quality-session7-operating-resume.json`을 업데이트해 기존 CPU 본문 분석을 즉시 실행:
  [실제 실행 #43347845889](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43347845889)
  - Gate 승인 단계 **PASS**.
  - 회귀 테스트 **PASS**.
  - DB/sidecar 실 입력 로드와 300×3 처리·발행의 최종 성공 여부는 실행 완료 후 확인해야 함. 완료 전에는 완료로 기재 금지.

## 세션 7에 남은 운영 확인

- 최초 성공한 전체 `future-bottleneck` 실행에서 `processed_this_run`, `db_news_articles`, `active_unprocessed_total`, `full_active_total`, `pending_due` 값을 현재 sidecar와 비교한다.
- 자동화 예정 주기를 정상 실행했다고 주장하지 않는다. 일회성 push 실행과 매일 2회 일정은 구분한다.
- 403, 404, 접근제한, 출처 검증 미통과는 자동 성공으로 승격하지 않는다.
- 예전 10,510건의 상태표는 모든 article_id를 보존하고, 새로운 RSS는 추가 ID로 수집되게 한다.
- 통합 DSR·종목 분석 등 다른 프로젝트 DB와 섞지 않는다.

## 안전 경계

- 기존 `main` source/engine, `data` canonical SQLite, `future-bottleneck-data` 기존 evidence 및 `live-state`를 이번 수리로 초기화하지 않았다.
- 기존 Gate 검증 정책과 candidate 승격 조건 수정 없음.
- 신규 유료 모델 API 및 별도 결제/키 설정 없음.
- 전용 GitHub Pages/dashboard 디자인은 별도 세션 8이며 이번 운영 연결 복구만으로 화면 배포 완료로 표현하지 말 것.
