# 공식 출처 인증 설정 — BCT-V4-Q-1.0

이번 연결은 개발 브랜치의 수동 `official-sources` 작업이다. 새 정기 실행, 외부 AI 호출, 운영 적용은 없다. 실제 수집·차단·잔여 범위의 정본은 같은 디렉터리의 `source-registry.json`과 `OFFICIAL_SOURCE_RESULTS.json`이다.

키가 없는 출처는 `NEEDS_USER_KEY`다. 요청 생성 코드와 Secret 전달 위치를 준비한 것이 인증·본문 파싱 성공은 아니다. 새 인증 출처의 실제 응답 스키마와 세부 수량 파서는 키 등록 후 검증이 필요하다. 기존 SEC 연락처·Census 키·비공개 저장 토큰·암호는 그대로 사용한다. 비공개 저장 토큰을 공개 개발 브랜치 push에 사용하지 않는다.

## 기관별 설정

| 기관 / 공식 발급 안내 | Actions Secret | 무료·접근 조건과 사용자가 할 일 |
|---|---|---|
| 미국 GSA SAM.gov — [공식 안내](https://open.gsa.gov/api/get-opportunities-public-api/) / [Account Details](https://sam.gov/profile/details) | `BCT_SAM_API_KEY` | 본인 일반 계정 로그인 → Account Details → API Key 요청/조회. Opportunities는 개인 키 필수·역할별 제한. [Contract Awards 문서](https://open.gsa.gov/api/contract-awards/)의 비연방·역할 없는 개인 계정은 **10회/일**; 역할 있는 비연방/연방 개인은1,000회/일. 공개 revealed 데이터와 미공개 unrevealed 권한은 다르다. 공개된 DoD 계약도 서명 후90일 경계가 있다. 일반 키로 미공개 계약 접근을 가정하지 않는다. 유료 구독·정부 역할 신청은 하지 않는다. |
| 금융감독원 OpenDART — [공식 사이트](https://opendart.fss.or.kr/) / [개발 가이드](https://engopendart.fss.or.kr/guide/main.do?apiGrpCd=DE001) | `BCT_OPENDART_API_KEY` | 본인 회원가입/로그인 → 인증키 신청·관리에서 이용 신청 → 발급·승인 상태 확인. 공개 공시 조회만 사용. 이번에 영문 가이드 HTML은 확인했으나 현재 계정 한도·승인·무료 조건은 미인증 상태이며 등록 후 확인한다. 원문/첨부 조회는 공시 목록 성공과 별개다. |
| 일본 금융청 EDINET — [공식 서비스](https://disclosure2.edinet-fsa.go.jp/) / [공식 안내](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html) | `BCT_EDINET_API_KEY` | 본인 EDINET API v2 이용자 등록·로그인 → API 키 발급. v2 `Subscription-Key` 전달 코드만 준비했으며 이번 회차의 계정 발급 화면·무료 한도·응답은 검증하지 못했다. 로그인/등록은 사용자만 수행한다. API v1 무인증 성공으로 대체하지 않는다. |
| 영국 Companies House — [개발자 사이트](https://developer.company-information.service.gov.uk/) | `BCT_COMPANIES_HOUSE_API_KEY` | Sign in / Register → 개발자 애플리케이션 관리 → 읽기 전용 REST API용 API key 생성. 기본 인증의 사용자명은 키, 비밀번호는 빈 값이다. 공식 무료 공개 회사 조회 API와 유료 인증서/주문 상품은 구분한다. 실제 계정 한도는 아직 확인하지 않았다. |
| 유럽 ENTSO-E — [공식 플랫폼](https://transparency.entsoe.eu/) / [공식 API 안내](https://transparencyplatform.zendesk.com/hc/en-us/articles/15692855254548-Sitemap-for-Restful-API-Integration) | `BCT_ENTSOE_API_TOKEN` | 본인 플랫폼 계정 등록 → 공식 Restful API integration guide의 접근 신청 절차 → 승인 후 토큰 확인. 웹 계정과 API 권한은 별개다. 현재 승인·토큰 발급 메뉴·무료 한도는 미검증. 유료 상품/별도 계약이 표시되면 진행하지 않는다. |
| 통계청 KOSIS — [공식 OpenAPI](https://kosis.kr/openapi/) | `BCT_KOSIS_API_KEY` | 본인 로그인 → 인증키 신청 → 통계표 ID와 서비스 범위 확인. 공식 홈페이지가 이번 환경에서503이라 현재 신청 화면·무료 조건·조회 계약은 미검증이다. 요청 빌더는 있으나 실제 인증·파싱 성공은 아니다. |
| 일본 e-Stat — [공식 API](https://www.e-stat.go.jp/api/en) / [실제 Sign up 링크](https://www.e-stat.go.jp/en/mypage/user/preregister) | `BCT_ESTAT_APP_ID` | 본인 e-Stat 회원 등록/로그인 → 마이페이지에서 API application ID 발급. 통계표 `statsDataId` 선택. API 사양 문서와 회원등록 필요는 확인했으나 계정별 한도·인증 응답은 미검증이다. |
| 한국 조달청·공공데이터포털 — [공식 사이트](https://www.data.go.kr/) | `BCT_DATA_GO_KR_SERVICE_KEY` | 본인 로그인 → 필요한 나라장터 API 검색 → 해당 서비스의 활용신청 → 승인·허용 호출량 및 **Decoding 인증키** 확인. 사전규격/요청/공고/낙찰/계약/변경/기관/쇼핑몰은 각각 신청·권한·운영 경로를 확인해야 한다. 포털·상세 문서가503이라 현재 operation 계약은 BLOCKED. 예전 URL을 임의 실행하지 않는다. Secret 연결 위치만 준비했고 요청 실행은 차단한다. |
| UN Statistics Division Comtrade — [공식 서비스](https://comtrade.un.org/) | `BCT_COMTRADE_API_KEY` | 현재 guest preview는 키 없이 실제 데이터 확보. 추가 API가 필요할 때 본인 계정의 무료/basic API 사용 범위와 subscription key를 확인한다. Premium/유료 업그레이드·카드 입력은 하지 않는다. 이번에는 preview용 헤더 전달만 준비했으며 정식 keyed endpoint·계정 한도는 미검증이다. 키는 현재 guest 수집의 필수조건이 아니다. |
| 미국 Regulations.gov — [공식 발급 폼과 API 안내](https://open.gsa.gov/api/regulationsgov/#getting-started) | `BCT_REGULATIONS_API_KEY` | 공식 페이지 Getting Started의 api.data.gov 가입 폼 → 본인 정보로 읽기 전용 API 키 요청. 문서 GET만 사용한다. **댓글 게시 활성화**에 필요한 추가 기관정보·세금번호 신청은 하지 않는다. DEMO_KEY는 사용하지 않는다. 실제 계정 한도·인증 응답은 아직 미검증이다. |

무료 API라는 일반 설명은 무제한 호출·모든 자료 접근·원문 재배포 허가를 뜻하지 않는다. 현재 공식 문서 또는 계정 조건이 확인되지 않은 부분은 위 표대로 미확인으로 남겼다. 카드·유료 요금제·제한된 정부 전용 역할이 필요한 경우 해당 경로만 BLOCKED다.

## GitHub에 등록하는 공통 절차

1. 발급한 값을 채팅이나 코드에 붙이지 않는다.
2. `irewon1-lgtm/bottleneck-control-tower` → **Settings → Secrets and variables → Actions → Secrets → New repository secret**.
3. 위 표의 이름을 **Name**, 발급값을 **Secret**에 입력하고 **Add secret**. 같은 이름이 이미 정상 등록돼 있다면 교체하지 않는다.
4. 개발 브랜치의 `.github/workflows/v4-cpu-private-research.yml`에는 해당 이름의 선택적 전달 위치만 준비돼 있다. 실행 로그는 `present: true/false`와 `authentication: NOT_TESTED`만 기록한다. 값이나 인증 헤더는 출력하지 않는다.
5. 등록 뒤 별도 수동 개발 실행에서 요청 계약·무료 한도·읽기 권한을 확인해야 한다. 이번 수집기는 새 키 경로를 자동 호출하지 않으며, 키 등록만으로 `LIVE_FETCH_PASS`를 부여하지 않는다.

현재 Codex GitHub integration은 Secret **이름 목록** 조회도403으로 거부됐다. 이를 키 무효화로 해석하지 않는다. Actions 실행기에 실제 전달됐는지는 수동 개발 실행의 불리언 증거로만 판단한다. 관리자 권한 확대나 Secret 재설정은 이번 작업에서 하지 않았다.
