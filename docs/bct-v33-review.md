# BCT 미래병목 v3.3 요청형 검토 안내

이 안내는 확정 설계 v3.3의 기존 JSON·GitHub Pages·알림 경로를 사용하는 운영 절차다. 자동화는 후보 수집·보존·재검토 알림만 수행한다. 사용자가 검토를 요청했을 때 ChatGPT가 원문을 읽고 판단을 저장한다. 유료 AI 자동호출, 새 DB·서버, Core·투자점수 변경은 없다.

## 읽을 파일과 고정 참조

저장소는 `irewon1-lgtm/bottleneck-control-tower`, 운영 자료 브랜치는 `future-bottleneck-data`다.

| 경로 | 용도·쓰기 소유자 |
| --- | --- |
| `future-candidates.json` | 문서·본문 버전·선별·재확보는 `collection`; 고정 `bundles`·`events`는 `bundle`; `notifications`는 `notification` |
| `future-tracking.json` | `reviews`·`progress`·`prediction_ledger`·`targets`·`runs`·`updated_at`은 `review` |
| `src/bct/future_review.py` | 실제 검토 형식·대기열·고정 묶음·알림 상태 검증 |
| `src/bct/future_store.py`, `src/bct/future_github.py` | 소유 필드 병합·SHA 조건부 저장·재조회 |
| `src/bct/future_body.py` | 본문 추출·SHA-256·비공개 실행환경 캐시 |

직접 읽기: [후보·묶음](https://raw.githubusercontent.com/irewon1-lgtm/bottleneck-control-tower/future-bottleneck-data/future-candidates.json), [판독·예측 원장](https://raw.githubusercontent.com/irewon1-lgtm/bottleneck-control-tower/future-bottleneck-data/future-tracking.json). 쓰기 직전에는 GitHub Contents API에서 최신 내용과 **Git blob SHA**를 다시 읽는다. 본문 `body_sha256`과 파일 저장용 SHA를 혼동하지 않는다. Pages의 대기 현황·원문 링크는 진입점이며, 실패 경고가 있으면 마지막 조회 자료임을 확인한다.

사용자 요청 예: “미래병목 대기 묶음을 빠르게 검토하고, 필요한 후보만 심화분석해. 결과를 저장하고 못 끝낸 자료는 남겨둬.” 기사별 복사·입력을 요구하지 않는다.

## 실제 본문과 읽은 범위

1. 후보 파일·판독 파일을 읽고 기존 미완료 `bundles`의 `id`, 각 `document_id`, `body_sha256`, `reader_version`, `start`, `end`, `url`을 고정한다. 묶음은 최대 10문서·12,000문자이며 긴 문서는 이어서 읽는다. 미리보기 최대 5개는 후보 상한이 아니다.
2. 원문 URL에 직접 접근한다. 캐시가 있으면 `read_cached_body(cache_dir, expected_sha256)`로 해당 버전을 읽는다. 캐시는 `<sha256>.txt`의 **추출된 UTF-8 본문**이며, SHA-256은 그 본문 바이트에 계산한다. 원시 HTML·웹 도구의 요약·줄 번호·다른 본문 표현의 해시는 같은 버전의 증명이 아니다.
3. 재접근한 HTML은 `future_body.extract_document(html, http_status=..., content_type=...)`의 동일 추출 규칙을 적용한다. 실제 얻은 본문 SHA와 길이가 고정 참조와 일치하는지 확인한 뒤 해당 본문을 읽는다. `read_start`·`read_end`는 Python 문자열 기준 **0부터 시작하는 문자 범위 `[start, end)`**다. 실제 읽은 위치만 저장한다. 중간 범위를 건너뛰지 않는다.
4. `FULL`은 접근 가능한 구조의 추출 상태다. 길이만으로 FULL을 판정하거나 핵심 표·영상·첨부를 읽었다고 가정하지 않는다. FULL 문서도 일부 범위만 읽었다면 전체 판독 완료가 아니다. `PARTIAL`의 확인 가능한 신호는 보존하며 PARTIAL·UNAVAILABLE은 자료확인 대기에 남는다.

일치하는 과거 본문을 얻지 못했다면 `kind: "access"`, `access_status: "BLOCKED"`, 구체적인 `reason`을 저장한다. 실제로 다른 **동일 추출 규칙의** 본문 해시를 관측했다면 `SOURCE_CHANGED`와 `observed_body_sha256`을 기록한다. 복구한 기존 해시가 일치할 때만 `AVAILABLE`을 기록한다. access 기록에는 읽기 범위·완료 필드를 넣지 않는다. 웹 표현이 다르다는 이유만으로 SOURCE_CHANGED나 기존 버전 판독 완료를 꾸미지 않는다.

새 본문은 수집 소유자의 변경분으로 새 버전에 등록한 뒤 그 해시를 실제로 읽고 검토한다. 과거 묶음 참조·판독·이력은 유지한다. 실행환경 캐시는 공개 업로드하지 않으며 다음 실행까지 보존된다고 보장하지 않는다. 재접근·과거 버전 복구가 불가능하면 재현성 한계를 명시한다. 차단·유료벽을 우회하지 않고 기사 전문·개인자료·비밀정보를 공개 파일에 저장하지 않는다.

일시 오류는 동일 문서 버전에서 총 3회까지만 자동 재시도한다. 시간 경과로 초기화하지 않는다. 사용자 재확인·지정 일정은 기존 수집 CLI의 `--trigger USER` 또는 `--trigger SCHEDULED`, **동일 요청에 재사용하는** `--trigger-id`, `--document-id`로 지정한다. 예를 들어 `--trigger SCHEDULED --trigger-id check-target-2027-01-01 --document-id 실제문서ID`다. 새 일정·새 요청은 새 ID를 사용한다. 필터 변경은 확보한 본문을 재사용한다.

## 빠른검토·심화검토 형식

`reader_version`은 현재 `bct-v33-reader-1`이다. 빠른검토 `kind`는 `quick`, 판정 `disposition`은 `CHANGE`, `RELIEF`, `DEEP_NEEDED`, `IRRELEVANT`, `DATA_INSUFFICIENT`, 중단 시 `INCOMPLETE`다. 빠른검토에는 S 단계를 부여하지 않는다. 완전히 읽었으나 후보의 공급량 등이 미공개라면 `DATA_INSUFFICIENT`·`candidate_state: "DATA_WAIT"`로 남긴다. 문서 판독 완료와 후보 자료 대기는 별개이며 같은 기사를 반복해서 읽지 않는다.

다음 JSON 두 개는 **형식 검증용 가상 예시이며 실제 판독 결과가 아니다**. `fixture-doc`, 해시, 범위·날짜·근거를 실제 고정 묶음과 읽은 내용으로 바꾼다. `review_id`는 문서·본문 해시·판독 버전·범위·판단 회차를 포함해 안정적으로 만든다. 동일 저장 재시도에는 같은 ID와 같은 내용을 사용하고, 판단 변경은 새 ID로 추가한다.

```json
{
  "review_id": "quick-fixture-doc-aaaaaaaa-0-100-r1",
  "document_id": "fixture-doc",
  "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reader_version": "bct-v33-reader-1",
  "kind": "quick",
  "read_start": 0,
  "read_end": 100,
  "reviewed_at": "2026-10-01T00:00:00+00:00",
  "disposition": "DEEP_NEEDED",
  "reason": "가상 예시: 공급 중단의 미래 영향을 추가 확인해야 한다."
}
```

심화 `kind`는 `deep`, `discovery_path`는 `DEMAND` 또는 `SUPPLY`다. gate는 `value: TRUE/FALSE/UNKNOWN`과 `evidence`로 기록한다. TRUE/FALSE 근거에는 실제 위치 `locator`가 필요하며 URL을 넣을 때는 접근한 정확한 HTTP(S) 출처를 사용한다.

```json
{
  "review_id": "deep-fixture-doc-aaaaaaaa-0-100-r1",
  "document_id": "fixture-doc",
  "body_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reader_version": "bct-v33-reader-1",
  "kind": "deep",
  "read_start": 0,
  "read_end": 100,
  "reviewed_at": "2026-10-01T00:10:00+00:00",
  "disposition": "DATA_INSUFFICIENT",
  "candidate_state": "DATA_WAIT",
  "analysis_complete": true,
  "discovery_path": "SUPPLY",
  "target": "가상 TARGET",
  "temporal_status": "UNRESOLVED",
  "s_stage": "S2",
  "gates": {
    "change": {"value": "TRUE", "evidence": [{"locator": "가상 본문 문자 0–40: 생산 중단 발표"}]},
    "target_relation": {"value": "TRUE", "evidence": [{"locator": "가상 본문 문자 40–100: 영향받는 적격 제품"}]},
    "remaining_demand": {"value": "UNKNOWN", "evidence": []},
    "supply_gap": {"value": "UNKNOWN", "evidence": []},
    "future_period": {"value": "UNKNOWN", "evidence": []},
    "relief_reviewed": {"value": "UNKNOWN", "evidence": []}
  },
  "unconfirmed": ["가상 예시: 남아 있는 수요·필요 기간·대체 공급 자료 부족"]
}
```

`read_complete`는 저장된 해당 해시·판독 버전의 연속 판독 범위로 계산한다. 전체 본문 끝까지 읽고 최종 disposition을 저장해야 문서 완료다. `analysis_complete: true`는 실제로 끝낸 심화검토만 표시하며 미래 부족 확정이나 자료 충분을 뜻하지 않는다. 중단·미독·저장 실패를 완료로 처리하지 않는다.

| 단계 | DEMAND 경로 | SUPPLY 경로 |
| --- | --- | --- |
| S1 | `change` TRUE: 구체적 수요 변화 | `change` TRUE: 구체적 공급 감소·중단·지연 |
| S2 | S1 + 구체 `target` + `target_relation` TRUE: 필요 관계 | S1 + 구체 `target` + `target_relation` TRUE: 적격 공급 영향 관계 |
| S3 | S2 + `future_demand`, `supply_constraint`, `future_period`, `relief_reviewed` TRUE | S2 + `remaining_demand`, `supply_gap`, `future_period`, `relief_reviewed` TRUE |

S3는 기본 12~36개월 미래 범위에서 `period.start`·`period.end`를 쓰고, `as_of < start <= end`, `temporal_status: "FUTURE"`를 확인한다. 실적·계획·전망·조건을 구분한다. `relief`에는 적용 가능한 증설·신규 공급·대체재·효율/단위당 사용량·수요 둔화·재고를 범주별로 기록한다. 각 항목은 `status: FOUND/NOT_FOUND_IN_SCOPE/INACCESSIBLE/NOT_APPLICABLE`과 `reason`을 포함한다. 중요한 항목은 `important: true`; 근거로 해소한 경우에만 `resolved: true`다. 검색 미발견은 Relief 부재가 아니며 중요한 반증·완화 가능성 미해결은 S3를 보류한다.

UNKNOWN은 해당 승격을 보류하고 FALSE는 해당 연결만 반박한다. 다른 경로·후보를 일괄 삭제하지 않는다. 수요 증가 없이 공급 감소도 진입하지만 공장 폐쇄만으로 S3가 되지 않는다. 자동 수집은 재검토 필요를 알릴 뿐 S 승격·강등을 판단하지 않는다. S3는 구조적 후보이며 Q/T 부족 확정·투자 추천이 아니다. 기존 Q/T는 변경하지 않고 비교 자료가 없으면 UNKNOWN이다. Track X의 실제 구현 범위는 별도 확인 대상이며 재무·주가 CSV로 생산능력·납기를 대신하지 않는다.

예측을 저장할 때 deep 기록에 `prediction`을 덧붙인다. 최소 필드는 안정적 `target_id`와 `hypothesis`; 함께 `sector`, `subsector`, `target`, 대상 `period`, `support_conditions`, `refutation_conditions`, `sources`, `unconfirmed`, `next_check_at`을 기록한다. 분류 근거가 없으면 미분류다. 최초 원장 `initial`은 고정되고 이후 판단은 `entries`에 추가된다. `next_check_dates`를 별도로 지정하지 않으면 검토일 기준 3개월·6개월 날짜가 생성된다. 확인된 실적·인증·가동 일정도 다음 확인 조건으로 남기고, 자료 대기는 새 자료나 지정 조건이 생겼을 때 재개한다.

## 저장·검증 명령

아래는 저장소의 설치된 `bct` 모듈을 사용하는 명령이다. 후보·판독 JSON은 실행 직전 최신 운영 파일을 작업 디렉터리로 읽는다. `review.json`은 실제 판독 결과이며 공개 전문을 포함하지 않는다.

```bash
python -m bct.future_review summary --candidates future-candidates.json --tracking future-tracking.json
python -m bct.future_review bundle --candidates future-candidates.json --tracking future-tracking.json --output bundle-change.json
python -m bct.future_review review-patch --candidates future-candidates.json --tracking future-tracking.json --review review.json --output review-change.json
python -m bct.future_github --repository irewon1-lgtm/bottleneck-control-tower --branch future-bottleneck-data --path future-tracking.json --change review-change.json --candidates future-candidates.json --pending pending-review.json
```

`bundle`·`review-patch`는 변경분을 생성할 뿐 운영 저장을 완료하지 않는다. 묶음 변경분은 같은 GitHub 저장 명령에서 `--path future-candidates.json --change bundle-change.json`으로 저장한다. `save-review`는 로컬 시험 파일용이며 운영 GitHub 저장의 대체가 아니다. GitHub CLI는 기존 권한의 `GITHUB_TOKEN`을 환경에서 사용한다; 비밀을 출력·공개 파일에 저장하지 않는다.

모든 쓰기는 최신 파일·SHA 읽기 → 자기 소유 변경분만 병합 → 참조·형식·버전 검증 → SHA 조건부 저장 → 재조회 확인 순서다. 문서 객체 전체·파일 전체를 새 결과로 대체하지 않는다. 알려지지 않은 필드와 다른 쓰기 경로의 기록도 유지한다. `operation_id`는 review helper가 `review-<review_id>`로 만든 안정적 값이며 생성한 변경분 파일을 그대로 재사용한다. 같은 ID에 다른 payload를 넣지 않는다. 충돌 시 최신본에 해당 변경분만 한 번 재병합·재시도하며 같은 판단 충돌이나 계속된 실패는 반영 대기로 남긴다. `APPLIED` 또는 `ALREADY_APPLIED`와 재조회된 operation 기록·판독 내용·진행 위치를 확인한 뒤 저장 완료를 알린다.

변경분 파일의 `prepared_document`는 변경을 준비할 때 읽은 문서다. 저장 직전 최신 파일을 다시 읽더라도 이 기준을 바꾸지 않는다. GitHub MCP로 저장할 때도 `apply_owned_patch(latest, ..., prepared_document=change["prepared_document"])`로 병합하며, SHA 충돌 후 한 번 재시도할 때 같은 기준을 전달한다. 같은 항목의 판단·현재 본문·알림 상태가 준비 이후 바뀌면 `SAME_ITEM_CONFLICT`로 반영 대기에 남긴다. 독립 필드는 최신본에 보존하여 병합한다. 이 기준 문서는 임시 변경분에만 있으며 운영 sidecar에 추가하지 않는다. 의도적인 새 판단은 최신본을 읽은 뒤 새로운 변경분으로 준비한다.

동일 계약·발표가 확실할 때만 `event_confirmation_patch(candidates, event_id, document_refs, event_key=..., change_kind="ORIGINAL", evidence=...)`로 사건을 묶고 원문 목록을 유지한다. 반환된 `events` 변경분은 `bundle` 소유자로 `future-candidates.json`에 동일 SHA 조건부 저장·재조회 절차를 적용한다. 애매하면 합치지 않는다. 정정·취소·증액·축소는 `CORRECTION/CANCELLATION/INCREASE/DECREASE` 변경으로 분리한다. 다른 본문을 같은 사건이라는 이유로 판독 완료 처리하거나 중복 증거로 세지 않는다.

## 알림과 시험 상태

알림 메타데이터의 정본은 **`future-candidates.json.notifications`**다. `future-tracking.json.notifications`에 별도 저장하지 않는다.

```bash
python -m bct.future_review notification --candidates future-candidates.json --tracking future-tracking.json --output notification-change.json
```

`suppressed: true`면 새 자료·중요 변화·확인 일정에 따른 새 요약이 없거나 제한에 걸린 것이다. 변경분이 있으면 notification 소유자로 후보 파일에 SHA 조건부 저장한다. 초기 요약은 한국 시간 하루 최대 2회이며 동일 fingerprint를 반복 발송하지 않는다. 요약은 신규 후보, 빠른검토·심화·자료확인 대기, 중요 반증, 최장 대기시간, 최대 5개 대표, 고정 묶음·이어 볼 위치, 실제 수집 완료·자료 갱신 시각을 포함한다.

`READY`는 요약 생성, `SENT`는 실제 발송, `ACCEPTED`는 전달 경로 접수, `RECEIVED`는 사용자 실제 수신 증거다. 발송·접수·수신을 혼동하지 않는다. 실제 경로의 상태를 `delivery_patch(candidates, notification_id, state=..., receipt=...)`로 만들고 notification 소유자의 동일 병합·조건부 저장·재조회 절차를 적용한다. RECEIVED에는 실제 수신 증거가 필수다. 알림·링크 열람은 문서 완료를 만들지 않는다.

1건 실제 알림 수신 → 사용자 검토 요청 → 직접 원문 판독 → 분석 저장 → 재조회 왕복은 기존 시험 기록상 PASS다. 이 문서 자체는 다른 시험의 통과 보고서가 아니다. 전체 기능시험·새 표본의 문서/사건 품질 채택·7일 지속 운영 최종 판정은 해당 단계 기록이 완료될 때까지 PENDING이다. 실제 7일 동안 유입·완료·재시도·자료 대기·최장 대기시간과 사용자 미검토/시스템 지연을 구분한다. 적체가 지속 증가하면 운영 PASS·출처 확대를 보류한다. 실행하지 않은 기간·예측 성능을 PASS라고 표시하지 않는다.
