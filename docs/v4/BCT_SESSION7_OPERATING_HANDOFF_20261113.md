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

## 추가 실증 체크포인트 (2026-11-13 11시 이후 KST)

### 기존 운영 CPU 실제 저장

- 운영 실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43347845889
- 이전 release guard 통과, 전체 단위회귀 통과, 실 RSS/연구 sidecar 조회 통과, CPU 본문 분류와 기존 CAS 기록 게시 실행 확인.
- 직전 `future-bottleneck-data` 실제 생성 HEAD: `229895ca2f4a4695b9bc8bf886ca2dedc7ffe749`
- canonical DB: RSS **10,510건**, 이전 sidecar **8,145건**, 최신 연결 **8,309건**, 미연결 **2,201건**.
- 이 실행 중 실제 연결 기사 +164건을 관측함. 신규 관측된 자료는 S1/S2/S3 확정 병목 근거가 아님.
- 확인된 실 데이터 `summary.pending_due=2201`, `full_active_total=4727`. 일시적인 제한 배치의 `pending_due=0`과 혼동하지 말 것.
- 이 문서 추가 시점 실제 실행은 **`Read FULL sources with pinned cost-zero CPU reader`** 처리 중. 최종 전체 SUCCESS와 atomic operating queue 저장은 아직 미확인.

### 읽기전용 전체 기사 적체·신규 우선순위 실증

- 검증된 전체 기사 상태표: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43349308307 (**PASS**).
- 10,510 기사 ID 전수 대조; 27개 연구 sidecar 분할 SHA256 검증, 기존 미연결 2,365 / 원문 획득·재검토 작업대기 3,007 / 재시도·접근 제약 등 보류 2,847 (시험 기준 불변 세대).
- 원문 작업 계획 120건 중 신규 48/기존 적체 72.
- 기존 엔진의 `--document-id` 인터페이스와 연계한 공정성 있는 ID 선별: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43350411695 (**PASS**, 실제 선정만, 본문 다운로드 0).
- 단계 7 연구용 Draft PR #71: https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/71
  - 새 CPU 선택기 `src/bct/future_fair_queue.py`, 기존 `src/bct/future_bottleneck.py`의 명시적 `BCT_FAIR_QUEUE_MODE=balanced-v1` 플래그, 기존 workflow의 후보 작업에만 옵트인.
  - 40% 최근 기사(48시간), 60% 오래된 적체, 원문 호스트당 최대 6, 실제 기존 source retry/hold filter를 통과한 입력만 선택.
  - 연구 브랜치 테스트 PASS. **아직 main 병합 안 됨**; 새 코드에 대한 실 Gate 0–6, 전체 배포 승인 기록·복구 원본 요청의 동일 세대 검증 전에는 실 운영 성공이라고 주장하지 않음.
- 기존 RUN의 +164건은 **기존 기본 FIFO 처리의 실제 성과**이며 PR #71을 사용한 결과가 아님.

## 다음 시작 지점 (절대 이전 감사 반복하지 않음)

1. #43347845889 완료 판정 확인: `Read FULL sources`, `Publish atomic operating queue`, artifact 저장 각 단계의 PASS/FAIL을 검증한다.
2. 최종 sidecar HEAD와 `summary.active_processed_total`, `active_unprocessed_total`, `full_active_total`, `pending_due` 재검증; 확인되지 않은 처리 건은 합산하지 않는다.
3. 연구 PR #71 안전성 검토/배포: Gate 재검증까지 하고 나서, 다음 운영 자동화 회차가 신규/기존 기사 혼합 처리하고 실제 감소량이 나오는지 실증한다.
4. 이 연구용 선별은 원문 분석 후보이며 병목섹터 증거 순위표나 S단계 자동 승격 자료가 아니다.
