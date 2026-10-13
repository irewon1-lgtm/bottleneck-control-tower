# 실증 재현 안내

이 패키지는 완성된 BCT V4 앱이 아니라 조사·부품 시험·최소 저장 adapter다. 운영 V3.3과 연결하거나 기존 DB를 바꾸는 명령은 없다.

원문1건: evidence/bct-input.json의 보존 EIA body; SHA-256 86d3b545d115eaec86b175ad9e32429b35a05bdb5596a51b0b8733cb64aac10e. 당시 기존 BCT에서도 PARTIAL. 현재 원문 전체의 동일성으로 주장하지 않는다.

tests/run.py의 각 assert가 기능시험의 기대 결과다. synthetic fixture는 실제 수급·EARLY 성능으로 채점하지 않는다. tests/gliner_probe.py는 CPU4threads의 로컬 모델만 사용한다. tests/integrate.py는 해당 모델 출력의 원문 span과 단일 저장만 검증한다. 데이터나 모델 다운로드가 막히면 BLOCKED이며 API로 대체하지 않는다.

환경: Python 3.12/Linux. 재현용 환경의 정확한 설치 버전은 evidence/environment-freeze.txt. torch는 CPU 배포를 사용했다. gliner2 2.1.0, trafilatura 2.3.1, statsforecast 2.1.1, edgartools 2.21.1. EdgarTools 버전은 구버전이며 현재 HEAD와 동일한 API가 아니다. 최신 소스와 실행한 package 버전을 혼동하지 않는다.

실행 스크립트의 상대경로는 `bct-v4-research/`가 현재 디렉터리 아래 있는 구조다. 내려받은 압축의 `bct-v4-research` 폴더를 유지해야 한다. venv·모델 weights는 포함하지 않는다. 실행 시 무료 공개 weights 다운로드와 CPU시간·디스크가 필요하다. paid API credential는 사용하지 않는다.

허용된 제3자 코드:
- sources/mercer14k__SupplyGraphAI/files/: domain graph/models/validation. Apache-2.0 LICENSE와 원출처 https://github.com/mercer14k/SupplyGraphAI 동봉. 전체 앱을 검증한 것은 아니다.
- sources/sanorthey__pemmss/files/: deposit/file_export/spatial의 시험용 하위 모듈. BSD-3-Clause LICENSE.md와 원출처 https://github.com/sanorthey/pemmss 동봉. 전체 모델/GUI를 검증한 것은 아니다.

그 외 원격 소스는 SOURCE_MANIFEST.json의 조사 기록과 프로젝트 코드 위치로 참조하며 무단 재배포하지 않는다. source snapshot은 일부 HEAD와 일부 고정 commit이 섞여 있으므로 고정 commit과 installed package를 다시 대응시킨 뒤 운영 채택해야 한다. weights·model-card·전이 의존성은 각각 조건을 따른다.

본 패키지에서 실증하지 않은 것: TARGET 5필드 정확도, 실제 주문/공급 역할 정확도, 독립 원출처 자동 판정, 실제 신규 미래병목, EARLY, 실제 대량 서로 다른 문서, 자동 스케줄·대시보드·알림. 평가 결과를 허용 범위 이상으로 확장하지 않는다.
