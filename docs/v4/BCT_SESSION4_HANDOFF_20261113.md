# BCT V4 — 세션 4 독립 AI 참고정답 정확도 감사 및 인계 (2026-11-13 KST)

## 완료 상태

- 실데이터 실행: **PASS_EVALUATED_RETROSPECTIVE_AI_REFERENCE**, GitHub Actions [43337864700](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43337864700)
- 기준 입력: 고정된 세션 3 기사별 원본 분류 10,510건 / data `da7b17f34d58c69c72b5d067d6279ec98db8bb44`; sidecar `e8acd5e91f9f972974b5027a36056651098da71f`.
- 평가 정답: 기존 `docs/v33-quality-reference.json` 100건과 `docs/v33-regression-reference.json` 100건. **AI_REFERENCE_NOT_HUMAN_GOLD**, 전문가 정답 아님. 200건 모두 ID·원문 URL·출처 일치, 비교 불가 0건.
- 이 실행은 저장된 CPU 제목/RSS 요약 분류와 과거 독립 AI 참고 정답의 일치도 평가이다. **실제 12~36개월 미래 병목 예측 성능이 아님.**
- API 호출 / 새 원문 요청 / 운영 데이터 변경 / S1·S2·S3 승격: 각 0건.

## 정확도 (UNKNOWN 제외, 기사-신호 개별 평가)

| 신호 | TP | FP | FN | TN | UNKNOWN | 정밀도 | 재현율 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 수요 변화(DEMAND) | 39 | 7 | 89 | 28 | 37 | 84.8% | **30.5%** |
| 공급 관련(SUPPLY) | 7 | 3 | 35 | 100 | 55 | 70.0% | **16.7%** |
| 공급 완화(RELIEF) | 31 | 4 | 99 | 31 | 35 | 88.6% | **23.8%** |

- 237개 잘못 판정된 **기사×신호 쌍**(FP14, FN223). 고유 기사 141건.
- 공급 정밀도는 7/10에 기반한 것으로 95% Wilson 단순 이항 구간 약 39.7~89.2%. 넓어 성능 안정성이 확인되지 않는다.
- 관련 기사 ANY 평가(171건 측정 가능 / 29건 UNKNOWN): 제목만 TP60/FN92, 정밀도88.2%/재현율39.5%. 과거 본문 검토까지 통합 TP115/FN37, 정밀도88.5%/재현율75.7%.
- 과거 AI 평가군의 제목 P4 125건 중 AI 참조 ANY 양성 92건, 그중 51건은 과거 FULL 본문 단서를 활용해 Q1 검토 대상으로 복원, 41건은 Q1 미포함(그중 일부 다른 Q로 검토 가능).
- 이전 V3.3 평가 보고서의 정밀도/재현율은 **측정 경로·대상 분모가 다르므로 현 수치와 직접 개선률 비교 금지**.

## 독립 신규 평가군 동결

- 일반 블라인드 표본 **240건**: 과거 정답 200건과 ID 중복 0, 총 48개 출처, Q1~Q5 각 48건. 예측 등급·모델 판정 비노출.
- 메타데이터 P1 66건: 과거 정답 포함 3건, **신규 63건** 추가 고정. 일반 240건과 신규 P1이 1건 중복되므로 실제 신규 독립 판독 대상 **302개 고유 기사**.
- 신규 표본의 정답은 **전부 UNKNOWN**. 전문의/산업 전문가의 라벨 또는 신규 독립 원문 AI 판독이 이미 완료됐다고 기재하지 말 것.
- 정답의 본문 버전 해시 동등성은 미확인. 기존 AI 라벨 자체가 틀렸을 가능성, 산업 편향, 동일 사건 복수 보도를 구분해야 한다.

## 실제 코드와 재실행

- `tools/bct_session4_reference_eval.py`: 동결된 평가 JSON Git blob 검증 + 200건 TP/FP/FN/TN·정밀도/재현율 + P4 복구율 + 240 및 신규 P1 별도 블라인드 표본 동결
- `tests/test_bct_session4_reference_eval.py`: UNKNOWN/분모0 처리, 잘못된 URL·ID 차단, 본문 P4 복구, 신규 P1 중복 예방 규칙
- `.github/workflows/bct-session4-reference-eval.yml`: 실제 검증된 S3 결과 아티팩트 ID/해시/생산 run 바인딩, `contents:read`, `actions:read`, Python 회귀 및 신규 판독패킷 출력
- S4 실제 PASS: [43337864700](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43337864700).
- GitHub Actions 원본 산출물에는 `evaluation_summary.json`, `metadata_errors.csv`, `blind_reference_packet_240.csv`, `blind_new_P1_packet.csv`, `blind_sample_provenance.json`가 포함됨.
- 중복을 없앤 신규 **302건 통합 블라인드 평가 CSV**는 같은 ChatGPT 작업 산출물 `BCT_SESSION4_BLIND_REVIEW_302.csv`에 별도 제공.

## 운영 상태와 다음 작업

- 운영 main의 Gate 0~6 실행 [43330584731](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43330584731)은 실제 모든 필수 단계 PASS.
- 운영 `config/bct-operating-release.json`은 확인 시 구형 코드 SHA를 참조하고 있었으므로 **증명서 갱신/메인 자동 분석 정상화까지 PASS라고 주장하지 말 것**.
- 연구 결과는 독립 브랜치에 보존. 이전 세션3 PR #67 및 새 세션4 연구 PR은 실제 검증 증명서와 대조하기 전 `main`에 임의 병합 금지.

### 세션 5 권장 처리 방향

1. 신규 블라인드 302건의 원문·정규화 본문 SHA·출처/발행일·본문 완전성을 확보하고, 모델 결과를 보지 않은 상태에서 독립 AI 또는 전문가가 TRUE/FALSE/UNKNOWN을 기록(불확실성은 UNKNOWN).
2. 동일한 원문에 기존 규칙 CPU와 대안 CPU/무료 모델을 실행해 신호 정밀도·재현율·오류 원인·실행 비용을 비교. 이전 200건에 맞춘 임의 튜닝 금지.
3. 수요 제품·규격·지역·고객 필요기간과 적격 공급능력·반대 증거·독립 원문을 검증한 뒤에만 병목 단계 후보로 승격.
4. P4(제목 신호 없음)를 자동 영구 제외하지 말고, 본문 누락·접근 실패를 별도 대기열로 유지.

원문·비공개 인증정보·평가용 정답 추정치를 본 PR에 추가하지 않았음.
