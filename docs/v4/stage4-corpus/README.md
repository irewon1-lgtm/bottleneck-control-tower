# 4단계 동결 원문 50건

개발 30건과 평가 20건을 새 Groq 실행 전에 동결했다. manifest의 문서 ID·URL·공개일 근거·본문 및 원본 해시·분할·미판독 범위를 보존한다. 평가군은 확인한 기존 개발 URL 4,327개와 본문 해시 1,708개에 겹치지 않는다. 아래 첫 절은 원래 자료 준비 시점의 기록이며, 이번 수정·부분 평가 증거는 마지막 절에 구분한다.

| 구분 | FULL | PARTIAL | 합계 |
| --- | ---: | ---: | ---: |
| 개발 | 11 | 19 | 30 |
| 평가 | 19 | 1 | 20 |
| 전체 | 30 | 20 | 50 |

36건의 원본 HTML은 `native/*.html.gz`, 50건의 판독 대상 텍스트는 `text/*.txt`다. gzip을 해제한 원본 바이트 SHA-256을 manifest의 raw_sha256과 대조한다. 14건의 기존 NIST 텍스트는 Actions 아티팩트에서 해시를 검증해 복구했으며 네이티브 HTML이 없어 PARTIAL이다. FULL은 기존 파서가 판단한 접근 가능한 HTML 텍스트 범위이며 링크된 이미지·영상·첨부 파일까지 확보했다는 뜻은 아니다.

캡처 텍스트의 줄 끝 공백과 줄바꿈도 해시·좌표에 포함되므로 그대로 보존한다. 이 폴더의 `.gitattributes`는 원문 파일의 자동 줄바꿈 변환과 공백 서식 검사만 제외한다. 자료 무결성은 별도 해시 검사로 검증한다.

최종 50건에는 기존 V4·Actions에서 재사용한 16건과 새 네이티브 캡처 34건이 있다. 전체 조사에서 확보한 고유 원문은 118건(FULL37/PARTIAL81)이며, 동결군 밖의 68건은 보충 재고다. 보충 원문은 로컬 복구 디렉터리와 원래 GitHub 아티팩트에 있고 이 폴더의 평가 분모에 포함하지 않는다.

원문 공개일·출처·해시 근거와 제품·수요·공급·시간 정답은 별도다. `independent-gold-template.json`의 750개 필드는 모두 UNVERIFIED다. 모델 답이나 과거 판독을 정답으로 채우지 않았다. UNVERIFIED를 정보 부재 UNKNOWN으로 세거나 Precision/Recall 분모에 넣지 않는다. 새 50건의 모델 판독·정확도 평가는 NOT_RUN이다.

기존 전송 검증도 보존했다. 새로운 원문은 출처 검증·본문 연락처·query URL 등의 기존 조건에 걸리며, 조건을 피하려고 원문을 잘라 다른 문서로 위장하거나 검토 근거를 만들지 않았다. 과거 DOE 문서의 해시 결합 검토와 동일한 600자 입력은 재사용했다. 이번 작업의 API 호출은 0회다.

다음 작업은 모델 결과를 보지 않고 원문으로 독립 정답을 검증하는 것이다. 사실이 명시되지 않았다고 확인한 항목과 판단이 끝나지 않은 항목을 구분한다. 실제 계약·납품·생산, 계획·지원금·제휴, 물리 수량과 금액, 고객과 수혜자, 공급 준비 시점과 발표일을 각각 대조한다. 평가 결과를 보고 규칙을 수정하면 미사용 평가군 지위를 유지할 수 없다.

오프라인 자료 확인:

```bash
.venv/bin/python scripts/v4/verify_corpus.py
```

이 명령은 네트워크·모델·운영 DB를 사용하지 않는다. 자료·동결 무결성 PASS와 의미 정확도·CPU 개선·병목 선행 성능 판정을 분리한다. 전체 기능시험 반복, 5단계, 7일 Shadow는 수행하지 않았다.

## Repair evidence added after the original source freeze

The original manifest, source bytes, IDs/hashes and development30/evaluation20 split remain unchanged. Derived `safe-inputs-v1.json`, event gold/adjudication, raw responses, CPU baseline and evaluation scores record the separately approved repair. They are evidence, not another progress ledger. `PROGRESS.json` remains the resume ledger.

Gold is separate AI-session source review, not human verification. Original review sessions disclosed ancillary status-metadata exposure; their exact limits remain in adjudication records. The evaluation is partial and literal/alias scoped. Offline replay: `python -m scripts.v4.replay_repair_evidence`. No model/API calls are made by replay. Native NIST recovery matched frozen parsed text for13 documents; it does not prove historical HTML identity. One changed native/text version was not substituted. Do not reinterpret the original preparation-only zero-call fields as current repair usage.

`source-only-blind-evaluation-v1.json` and `source-only-audit-evaluation-v1.json` preserve an additional AI session's source-first draft and subsequent gold audit. It did not read evaluated model answers or query other session statuses. Of 83 PRESENT facts, 81 were source-supported and two field relationships remain unresolved in a document without a generation response; nine prior ambiguous facts remain unresolved. No gold labels, aliases or scoring rules were changed. Agreement is not model accuracy, and unreviewed ranges are not information absence.
