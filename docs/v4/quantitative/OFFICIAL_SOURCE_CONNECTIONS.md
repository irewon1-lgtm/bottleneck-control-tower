# 공식 출처 연결표 — BCT-V4-Q-1.0

기존8개 범위·과거 기록을 보존했다. 아래40개 항목은 **후보/자료 유형**이며40개 수집기가 완료됐다는 뜻이 아니다. 이번 실제 자료 파싱13개 출처군 중12개는 비공개 연구 DB에 저장·원격 복원했다. BGS는 보관 조건 보류로 저장하지 않았다. 기업 IR·Federal Register·기존8개 부품은 재사용이며 새로 만든 수집기로 계산하지 않는다.

원격 실행: https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/38857135706 . 상세 수치·원문 해시/위치·조회 범위·커서는 source-registry.json의 global_sources와 OFFICIAL_SOURCE_RESULTS.json을 따른다.

| 기관 | 기존 부품 | 현재 상태 | 이번 원격 구조화 레코드/버전 | 다음 경계 |
|---|---|---|---:|---|
| [미국 SAM 입찰](https://open.gsa.gov/api/get-opportunities-public-api/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [미국 SAM 계약](https://open.gsa.gov/api/contract-awards/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [미국 국방부 계약](https://www.defense.gov/News/Contracts/) | 확장 후보 | ACCESS_RESTRICTED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [DSCA 판매 승인](https://www.dsca.mil/) | 확장 후보 | ACCESS_RESTRICTED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [EU TED](https://docs.ted.europa.eu/api/latest/search.html) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [영국 Find a Tender](https://www.find-tender.service.gov.uk/Developer/Documentation) | 확장 후보 | FACTS_STORED | 1788 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [영국 Contracts Finder](https://www.contractsfinder.service.gov.uk/apidocumentation) | 확장 후보 | FACTS_STORED | 476 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [캐나다 CanadaBuys](https://canadabuys.canada.ca/en/procurement-and-contracting-data) | 확장 후보 | FACTS_STORED | 269 | next publication/version after fixed2026-10-15; fiscal file must remain<=20MB; unknown contracts/signature/delivery remain review tasks |
| [호주 AusTender](https://www.tenders.gov.au/) | 확장 후보 | DISCOVERED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [한국 나라장터](https://www.data.go.kr/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [OpenDART](https://engopendart.fss.or.kr/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [일본 EDINET](https://disclosure2.edinet-fsa.go.jp/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [영국 Companies House](https://developer.company-information.service.gov.uk/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [GLEIF 법인 식별](https://www.gleif.org/en/lei-data/gleif-api) | 확장 후보 | FACTS_STORED | 1 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [Eurostat PRODCOM](https://ec.europa.eu/eurostat/web/prodcom) | 확장 후보 | BLOCKED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [Eurostat COMEXT](https://ec.europa.eu/eurostat/api/comext/dissemination) | 확장 후보 | BLOCKED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [UN Comtrade](https://comtrade.un.org/) | 확장 후보 | FACTS_STORED | 1 | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [MISO 접속 대기열](https://www.misoenergy.org/planning/resource-utilization/GI_Queue/gi-interactive-queue/) | 확장 후보 | FACTS_STORED | 3938 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [PJM](https://www.pjm.com/) | 확장 후보 | DISCOVERED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [ERCOT GIS](https://www.ercot.com/mp/data-products/data-product-details?id=PG7-200-ER) | 확장 후보 | FACTS_STORED | 3684 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [NESO TEC](https://www.neso.energy/) | 확장 후보 | FACTS_STORED | 2225 | Next official register version; same snapshot not refetched. Capacity/schedule records are not customer-qualified allocable supply. |
| [ENTSO-E](https://transparency.entsoe.eu/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [DOE HALEU](https://www.energy.gov/ne/haleu-availability-program) | 확장 후보 | FACTS_STORED | 3 | Actual allocated HALEU amount/customer need date/production-ready qualified supply remain missing. Mutable page2023/2025 creation dates do not date2026 facts. |
| [NIST CHIPS](https://www.nist.gov/chips) | 확장 후보 | FACTS_STORED | 1 | Issuer/customer/facility production and customer qualification evidence, not incentive dollars. |
| [NRC](https://www.nrc.gov/) | 확장 후보 | ACCESS_RESTRICTED | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [BGS](https://www.bgs.ac.uk/mineralsuk/) | 확장 후보 | PARSE_VALIDATED | — | offset=200; entire world dataset remains unread; terms review required before archive |
| [KOSIS](https://kosis.kr/openapi/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [일본 e-Stat](https://www.e-stat.go.jp/api/en) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [Regulations.gov](https://open.gsa.gov/api/regulationsgov/) | 확장 후보 | NEEDS_USER_KEY | — | AUTH_AND_ROLE_VERIFICATION_AFTER_OWNER_CONFIGURATION |
| [Federal Register](https://www.federalregister.gov/developers/documentation/api/v1) | 재사용 | FACTS_STORED | 101 | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [SEC EDGAR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [USGS](https://www.usgs.gov/centers/national-minerals-information-center) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [Census M3](https://www.census.gov/manufacturing/m3/) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [Fed G.17](https://www.federalreserve.gov/releases/g17/) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [EIA](https://www.eia.gov/electricity/data/eia860m/index.php) | 재사용 | REUSED_EXISTING_PARTIAL | — | VERIFIED_DATA_ENDPOINT_AND_PARSER |
| [Census 무역](https://www.census.gov/data/developers/data-sets/international-trade.html) | 재사용 | REUSED_EXISTING_PARTIAL | — | country identity; first release date; intra-year export HS revisions |
| [세계은행 조달](https://projects.worldbank.org/en/projects-operations/procurement) | 확장 후보 | FACTS_STORED | 100 | HOLD stable documented ordering/date filter before offset100;100 release rows/80 unique notices in this returned prefix, not global absence or a current live feed. |
| [기업 공식 IR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | 재사용 | REUSED_EXISTING_PARTIAL | — | 기존 정본/키 가이드 참조 |
| [추가 시설 인허가](https://www.federalregister.gov/developers/documentation/api/v1) | 재사용 | DISCOVERED | — | 기존 정본/키 가이드 참조 |
| [USAspending](https://api.usaspending.gov/docs/endpoints) | 재사용 | REUSED_EXISTING_PARTIAL | — | 기존 정본/키 가이드 참조 |

레코드에는 공고·lot·낙찰·계약·시점별 프로젝트·통계·법인·프로그램 문맥이 포함된다. **문서 수, 주문 수, 독립 사건 수, TARGET 수로 바꿔 합산하지 않는다.** 기존 Q1 수치38,046개/물리량21,916개는 별도 지표로 그대로 유지한다.

Q2: 서명일이 보고된 계약 검토 입력은 중복 공고4개를 합쳐239건이다. 고객기관·정확한 award ID·공급업체 연결은 보존했지만 제품별 실제 물량/고객 필요일/적격 공급능력은 미확인이다. 독립 수급쌍0건, Q3 전달 적격 TARGET0건, 신규 S1/S2/S3 모두0건이다. 정부지원금·입찰 자격·조건부 배정·계통 신청MW를 제품 주문/공급으로 승격하지 않는다.

이 작업은 수동 개발 실행이다. 운영 예약·AI·CPU·main/data·UI·Secret·실행 pin을 변경하지 않았다. 새로운 경로의 정기 활성화는 NOT_RUN이다.
