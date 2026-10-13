# BCT V4 CPU Shadow

V3.3/main/운영 DB/Actions를 보존하는 별도 실행 경로다. 투자 예측과 유료 API는 없다.
원문·실패·AI span·실행·최초 발견 기록은 `var/v4/runtime/v4.sqlite3` 하나에 저장한다.
모델은 하나이며 CPU 4 threads에서 필요할 때만 로드한다.

## 설치·실행

```bash
cd /workspace/bottleneck-control-tower
bash scripts/v4/setup.sh
.venv/bin/python -m bct.v4 --root var/v4/runtime cycle
.venv/bin/python -m bct.v4 --root var/v4/runtime status
.venv/bin/python -m bct.v4 --root var/v4/runtime export
.venv/bin/python -m bct.v4 --root var/v4/runtime backup --output var/v4/backups/first.sqlite3
```

SEC는 환경 설정의 `BCT_SEC_USER_AGENT`에 실제 프로젝트/연락처를 요구한다.
설치에는 TLS 검증과 고정 모델 revision의 공식 LFS 체크섬을 사용한다.
GPU, 모델 API credential, 운영 마이그레이션은 필요하지 않다.
새 DB 경로에 기존 비-V4 DB가 있으면 쓰기 전에 거절한다.
backup은 목적지가 이미 있으면 거절한다. 복원은 실행 중 worker를 중단하고,
비어 있는 별도 root의 `v4.sqlite3`로 검증된 backup을 복사한 뒤 `status`로 확인한다.
기존 root/원장에 덮어쓰지 않는다.

공식 source 설정은 `config/v4-sources.json`이다. 직접 URL, RSS와 CIK를 함께 사용한다.
최대 10문서의 직렬 1회 실행이며 자동 무한 재시도/상주 서버는 없다.
SEC listing/본문은 기존 fair-access transport와 provenance verifier를 재사용한다.
RSS 공개일은 탐색 힌트이며 원문 공개일 검증을 대신하지 않는다.

## 해석과 제한

- `EXPLORATION_LEAD`: CPU 모델이 찾은 제품의 원문 span. 신규 산업/적격 TARGET 확정이 아니다.
- `EARLY_FORECAST_CANDIDATE`: 기존 엄격 엔진의 검토후보. 전체 적격 공급이나 선행성 성공을 의미하지 않는다.
- S1/S2/S3는 기존 의미와 기록을 유지한다. V4는 새로운 후보에 `UNKNOWN`을 표시한다.
- AI는 문서마다 최대 4개(설정상 1~16개)의 선행신호 window를 판독한다.
  미판독 window 수를 기록한다. 문서 전체/표/OCR의 완전 recall은 UNKNOWN이다.
- Trafilatura는 같은 native HTML 비교 경로다. 기존 parser가 정본이며
  비교 정확도가 입증되지 않은 자동 교체나 PARTIAL→FULL 승격은 없다.
- 원출처·공개일·TARGET 범위가 불명확한 문서와 후보도 삭제하지 않는다.
- 새 CLI는 BACKFILL 입력을 LIVE로 가져오지 못한다. SYNTHETIC는 기능 시험이다.
- 기존 계약을 그대로 사용하므로 문서의 다른 부분에 shortage 표현이 있으면
  그 문서 전체가 초기 근거에서 제외될 수 있다. 이 보수적 누락은 별도 한계다.

```bash
.venv/bin/python -m pytest -q tests/test_v4_integration.py
.venv/bin/python scripts/v4/cpu_smoke.py
.venv/bin/python scripts/v4/actual_trial.py
.venv/bin/python scripts/v4/benchmark.py
```

benchmark는 이번에 실제 수집한 `var/v4/native-trial`이 필요하다. 원문이 없으면
BLOCKED다. 연구 ZIP이 없어도 새 원문 수집은 가능하지만 과거 시험 재현으로 표시하지 않는다.
실제 성능은 공개일이 검증된 당시 corpus와 미사용 HOLDOUT이 있어야 평가할 수 있다.
7일 Shadow는 실제 기간 기록이 쌓인 후 평가한다. 이번 세션이 7일을 대신하지 않는다.

환경 설정에 저장한 설치/시작 지침은 재사용용 초안이다. 저장은 환경 게시나
새 작업에서의 복원을 증명하지 않는다. 환경 설정에서 검토·저장 후 환경을 게시한다.


## Fixed plan and optional free API annotations

Resume from [EXECUTION_PLAN.md](EXECUTION_PLAN.md) and [PROGRESS.json](PROGRESS.json). The optional API path remains disabled by default. See [FREE_AI_SETUP.md](FREE_AI_SETUP.md) for secure Gemini/GroqCloud setup and live prerequisites, and [API_TEST_RESULTS.json](API_TEST_RESULTS.json) for separate mock/live evidence. The original CPU path and operating boundaries stay in place.
