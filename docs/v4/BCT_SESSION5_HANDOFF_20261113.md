# BCT V4 — 세션 5 의미 분석 개선·302개 원문 실증 인계

- 작업일: **2026-11-13 KST**
- 범위: 세션 4에서 미리 동결한 **302건 신규 블라인드 기사**. 과거 AI 정답 200건은 정답 생성·모델 조정에 재사용하지 않았음.
- 기준 브랜치: `research/bct-session4-ai-reference-eval-20261113`; 연구/운영 데이터 원본 미수정
- 원래 RSS 전체 기사 10,510건을 세션 3에서 제목·요약 기준 전수 분류했지만, **세션 5 신규 본문 실사 302건과 혼동하지 말 것.**

## 1. 실제 신규 원문 302건 검수 — 1차

실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43340338148

- 인터넷 원문 시도 **302/302**, 48개 출처. 사용자 로그인/페이월 우회, 유료 AI API, 기존 DB 변경 각 **0**.
- 초기 판독: 출처 검증 FULL 45, 본문은 FULL이지만 출처 증명 실패 58, PARTIAL 113, 본문 불가 34, 접속/추출 오류 52.
- 원문 확보 및 출처 증명은 별개: FULL 58건이 증명 실패한 주요 원인은 `original_publication`, `attribution_consistent`, `original_identity`, `publisher_observed`. 원문 날짜를 RSS에서 대신 가져와 PASS로 바꾸지 않음.
- 초기 탐색 단서가 있는 기사: DEMAND 32 / SUPPLY 69 / RELIEF 92. 중복 가능하며 **독립 정답 대비 정확도 수치가 아님**. 수정된 의미 규칙으로 초기 293건을 다시 분석하지 않았으므로 최종 신호 수치로 오용 금지.

## 2. HTTP 원본 주소 처리 오류 발견 및 복구

- 초기 '접속·추출 오류' 52건에서 **9건은 실제 URL이 `http://`인 오래된 원본**을 HTTPS 전용 의미 분석 검사가 거부한 내부 `ValueError`였음. 본문은 확보돼 있었으므로 접속 실패로 오분류된 것.
- 별도 브랜치의 `future_semantic_shadow.py`가 HTTP 원본 문자열을 그대로 수용하되, *실제 네트워크 수집*은 기존 공개 IP/redirect 제약을 변경하지 않음.
- 공급 부족 증가 문장이 공급 완화로 오분류되는 경로 수정. 자격 인증 완료/자격 인증 지연도 다른 상태로 유지. 이는 합성 테스트 및 실데이터 일부 재시험에 근거하며 **전체 302건의 새 정밀도 향상을 입증하는 증거가 아님**.
- **기존 302건 재실행 금지**: 앞선 오류 9건만 다시 원문 시도, 기존 293건 원기록 보존.
- 재실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43341520709 — **PASS**
- 재실행 9건: FULL but provenance blocked **4**, PARTIAL **5**. 출처 검증 FULL 승격 **0**. (정상 재분류이며 근거 확인 완료와 다름.)

### 재대조한 302건의 상호배타적 상태

| 상태 | 건수 |
|---|---:|
| 원문 전체 및 출처 검증 **PASS** | **45** |
| 본문 FULL, 출처 검증 보류 | 62 |
| 본문 PARTIAL | 118 |
| 본문 UNAVAILABLE | 34 |
| 실제 접속·처리 ERROR | 43 |
| **합계** | **302** |

- 실제 오류 43건의 초기 원인은 HTTP_403 **27**, HTTP_404 **1**, TIMEOUT **15**. 이것은 현 API 오류 유형이며, 검증 없는 우회는 금지.
- 신규 P1 63건: VERIFIED_FULL 15, FULL_UNVERIFIED 9, PARTIAL 14, UNAVAILABLE 15, ERROR 10. P1 검증 원문 확보 **15/63**.
- 보고된 본문 해시는 내부 저장 확인 용도. 인증정보, 민감 원문 텍스트, 비공개 캐시/원본 HTML을 GitHub 공개 자료에 추가하지 않았음.

## 3. 실제 개발한 분석 경로

- `src/bct/future_semantic_shadow.py`: 문장 단위 DEMAND/SUPPLY/RELIEF 탐지, 실물 제품 인용 위치를 `precursor_scope_reader`의 기존 검증 규칙으로 추출, 원문 SHA256과 본문 오프셋 유지.
- 연관 항목: 제품명, 규격, 지역, 고객군, 적격 공급주체, 원시 기간, 직접 수량, 고객 필요일, 공급 준비일. 원문에 없으면 **UNKNOWN**. 자본투자 금액을 생산 수량으로 환산하지 않음.
- 공급자 명칭만 보고 *적격 생산능력*을 확정하지 않음. 독립 출처의 수요·공급 능력을 연결하지 않으며 S1/S2/S3 승격은 항상 **false**.
- 논문/산업/제품 사전이나 단순 키워드로 상품을 확대 추정하지 않음. `source_scope.read_scopes`의 문장별 물리제품 연결 규칙을 재사용.
- `tools/bct_session5_source_probe.py`: 기존 고정된 302 URL을 정상 HTTPS/HTTP 원본 경로로 단 한 번씩 읽고, 본문·출처 검증 상태와 의미분석 집계만 저장.
- `tools/bct_session5_http_recheck.py`: 기존 302건 로그에서 정확히 9개의 HTTP URI 입력 오류만 선택해 재검증. 293개 이전 결과 및 정확한 원본 ID/URL 불변.
- `tests/test_bct_session5_semantic_shadow.py`, `tests/test_bct_session5_source_probe.py`, `tests/test_bct_session5_http_recheck.py`: 광고/헤드라인, 조건부·부정 표현, 실물 제품/수치 오연결, 출처 위조·해시/URL 불일치, 접근거부 재시도 금지, 302건 보존 등의 회귀 시험.

최종 코드 전체 GitHub Actions 테스트: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43341520740 — **Python 1,210 PASS / 1 SKIP, JavaScript 34 PASS**.

## 4. 판정 안전장치와 미검증 항목

- **원문 탐색 302건 시도**: PASS.
- **전문가 독립 정답/의미 정확도**: **NOT_RUN/NOT_MEASURED**. 현재 302개 독립 참고 라벨은 전부 `UNKNOWN`. 이번 실증을 정확도 개선이나 미래 병목 성능 향상으로 주장하지 말 것.
- 엄격한 출처 확인으로 VERIFIED_FULL 45건만 현재 원본 검증 통과. 사용 가능한 기간/규격/수요 대비 적격 공급능력 정보는 별도로 부족.
- 생산 main의 원본 `future_bottleneck`, `future_hypothesis`, `data`, `future-bottleneck-data`는 변경하지 않았음. 신규 코드는 독립 연구 브랜치에만 추가됐음.
- 302건 중 이미 읽은 293건의 **새 버전 의미 규칙 재분석은 하지 않음**(원문 공개 캐시가 영속적으로 확인되지 않아 동일 SHA 스냅샷 재현이 제한됨). 원문 재확보 시 원문 SHA 대조.
- 기존 release receipt가 현재 main 코드를 가리키지 않아 운영 분석 자동 갱신은 별도 검증 필요. 이전 Gate 0~6 전수 성공이 자동으로 최신 UI와 연구 발표를 보장하지 않음.

## 5. 다음 세션 인계

1. 세션 6: VERIFIED_FULL 45건에서 실제로 의미가 있는 TARGET·독립 공급주체·고객 필요시점이 연결된 문서만 조사, 서로 다른 원문/회사 2곳 이상 및 날짜/규격/수량 동일성 확인. 조건 미충족 시 `UNKNOWN` 기록.
2. FULL 미검증 62건은 원문 정체·발행일·출처 기여 관계부터 확인, PARTIAL 118건은 누락 본문 보완. HTTP 403/페이월은 우회하지 말고 공식 대체 원문 검색.
3. 302건 원문 독립 AI/전문가 라벨 생성은 기존 예측을 가린 상태로 진행. 이후 같은 문서를 이전 엔진/새 연구 엔진으로 비교하여 Precision/Recall 실측.
4. 레거시 10,510건 전체 및 신규 RSS의 자동화/대시보드 연결은 후속 세션 7~9에서 구현·실증. **세션 5만으로 전체 기사 원문 분석이나 대시보드 자동갱신이 끝났다고 주장 금지**.

**검증 근거**
- 본문 302건 1차: [GitHub 43340338148](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43340338148)
- 9건 정확히 재시험: [GitHub 43341520709](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43341520709)
- 전체 자동 테스트: [GitHub 43341520740](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43341520740)
