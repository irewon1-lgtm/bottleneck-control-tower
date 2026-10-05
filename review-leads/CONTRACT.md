# REVIEW_LEAD 1차 검토 계약

규칙 `BCT_REVIEW_LEAD_RULES_1`, 계약 `BCT_REVIEW_LEAD_CONTRACT_1`.
적용 시작시각은 구현 전에 작성한 `contract.json.applies_from`이다.

목적은 사람이 2차 조사를 시작할 수 있는, 원문 근거가 붙은 초기 조사
기록을 만드는 것이다. 원문에서 식별되는 대상·범위와 사실/명시적 계획,
그 대상에 적용되는 구체적인 수요·공급 가설, 가정·반박조건·조사 질문을
요구한다. 독립 출처 두 개, 배정량, 적격 준비일, 완성된 시간·수량 비교는
일괄 진입 요건이 아니다. 부족한 정보는 UNKNOWN으로 그대로 둔다.

일반 성장·증설만 있고 대상별 연결을 설명할 수 없으면 HOLD.
대상 관계가 미확인이거나 같은 TARGET의 prior confirmation 적용이
불확실하면 HOLD. 명백히 다른 모델/공정/시설을 합친 경우, 수사적 표현을
실제 변화로 해석한 경우, 무효 원문 근거는 EXCLUDED/입력 오류로 남긴다.
같은 TARGET의 명시적 병목은 CONFIRMATION으로 기록하며 선행 조사대상으로
세지 않는다. 관련 없는 확인 내용과 불확실한 적용 범위는 구분한다.

Objective Lock `bct-objective-1` 및 기존 hash/export binding을 유지한다.
REVIEW_LEAD는 EARLY_FORECAST_CANDIDATE, strict/S3나 공식 TARGET을 대체하지
않으며 그 성공 집계에도 들어가지 않는다. 검토 규칙은 별도 version과
hash로 기록한다. v2 코드/추출/판정, 원래 실험, main/LIVE는 변경하지 않는다.

수동 판독 주석은 판독 주체·시각·원문 위치와 함께 입력한다. 이번 4원문
주석은 assistant가 원문을 읽어 작성한 개발 예시이며 사용자/독립 판독자
확인 전이다. 자동 추출이나 독립 성능 평가로 표시하지 않는다. 시스템은
근거 위치와 규칙 경계를 검증하여 상태를 계산하고 같은 근거/가설을 묶는다.

공개시각, 자료 확보시각, 검토 최초 기록시각, 엄격 후보 최초 충족시각을
분리한다. 현재 과거 문서를 검토하면 BACKFILL이다. UNKNOWN 기간은 원문
표현만 보존하며 임의 날짜로 바꾸지 않는다. T/T_scope는 확인 없으면 UNKNOWN.
최초 검토 기록은 불변이며 후속 근거·검토·확인·반증은 append-only다.
EARLY lead time은 기존 정의 그대로이며 REVIEW_LEAD 시각으로 대체하지 않는다.
