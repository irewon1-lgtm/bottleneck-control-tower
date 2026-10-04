# BCT Objective Lock

objective_version: bct-objective-1
objective_sha256: 0b2de0186c92fa0c5466539b42cdf5a4fba164a7c9fb62092e396cb4ebe0cff7

<!-- objective:start -->
병목이라는 말이 나오기 전에, 여러 독립적인 선행 신호를 합쳐서 앞으로 수요가 공급을 추월할 TARGET을 미리 후보화한다.
<!-- objective:end -->

SHA-256은 위 문장만의 UTF-8 바이트에 계산한다. 따옴표·개행은 제외한다.
변경은 별도 objective version과 명시적인 목표 변경 검토가 필요하다.
코드에 고정한 version/hash와 이 파일이 다르면 작업은 BLOCKED다.

## 운영 계약

- 기존 단일 문서 `candidate`, 자동 hypothesis와 quick/deep/S1/S2/S3는
  confirmation 자료이며 forecast discovery 성공으로 집계하지 않는다.
- Discovery는 `python -m bct.forecast_discovery`로 실행한다. 입력은 본문
  스냅샷과 locator, 검증된 최종 원출처·발행자·공개일·확보일을 갖춘
  명시적 precursor fact다. 출처 불명·재인용은 독립 근거로 세지 않는다.
- 부족을 공개 확인한 문서는 최초 forecast 근거에서 제외한다. 같은 TARGET의
  최초 공개 확인 T가 후보 최초 발견일보다 빠르거나 같으면
  MISSED_EARLY_DETECTION이다. T가 미확인이면 성공도 미확인이다.
- 후보에는 최소 두 독립 원출처의 미래 demand와 supply/ramp 근거가 필요하다.
  같은 범위의 수량 격차 또는 필요일보다 늦은 적격 공급 가용일을 기록한다.
  없는 수량은 UNKNOWN이다. 이를 S3·투자점수로 치환하지 않는다.
- 새로운 forecast/review batch와 export는 objective_version/objective_sha256을
  포함한다. 입력 batch의 누락·불일치는 BLOCKED로 처리한다. 과거 파일을
  소급 수정하지 않는다. 과거 판독·hypothesis·prediction ledger는 보존한다.
- 수동 deep/S3 요청 batch도 `bct.objective_lock.stamp_export` 또는 기존
  `_private_write`를 사용한다. 직접 JSON 출력으로 계약을 우회하지 않는다.
- 시간 재생은 BACKFILL이다. 당시 available_at 이후 자료, 미래 공개 확인 본문은
  discovery 입력에 넣지 않는다. T는 평가 정답으로만 별도 고정한다.
- lead_time_days = T - candidate_first_detected_at. 양수만 선행탐지 성공이다.
  기능시험 PASS와 독립 실제 pre-public holdout 성능 PASS는 별도 보고한다.
  실제 holdout·동결 정답·당시 원문이 없으면 성능은 BLOCKED다.

최소 설계와 실행 형식: [docs/forecast-discovery.md](docs/forecast-discovery.md).
