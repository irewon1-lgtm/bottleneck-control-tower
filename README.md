# bct-stocks

## 고정 목적
지금까지 수집한 모든 BCT 자료에서 어떤 경제적 수혜 경로든 검토해, 현재 가격·자금·희석을 반영한 12개월 내 주가 2~3배 가능성을 근거로 선별합니다. 수익을 보장하지 않습니다. 미국 정규거래소 상장 보통주/ADR·ADS만 대상으로 하며 OTC는 제외합니다.

## BCT와 분리
새 SQLite DB: `data/bct-stocks.sqlite3` (GitHub 저장본은 무손실 gzip 압축 `data/bct-stocks.sqlite3.gz`). BCT 운영 DB·판정·history에는 쓰지 않습니다. BCT의 병목 등급·과거 주가·종목 순위는 투자결론으로 승계하지 않습니다. `project.json`과 DB의 `objective_versions`에 목적과 합의 규칙이 저장됩니다.

현재 위치는 기존 공개 저장소의 독립 `bct-stocks` 브랜치입니다. 새 GitHub 저장소가 생성된 것은 아닙니다. 이 브랜치는 독립 실행이 가능하도록 BCT 앱 코드를 포함하지 않으며 기존 main에 병합하지 않습니다. 개인 보유종목·계좌·비밀키·비공개 거래정보를 넣지 마세요. 공개 웹앱은 배포하지 않습니다.

## 실행
Python 3 표준 라이브러리와 Git만 필요합니다. 유료 API, OpenAI API 키, DB 서버가 필요하지 않습니다.

```sh
# 압축 저장본이 있으면 먼저 복원
gzip -dc data/bct-stocks.sqlite3.gz > data/bct-stocks.sqlite3
python bct_stocks.py verify
python -m unittest discover -s tests -v
# 신규 초기화는 python bct_stocks.py init
# 소스 저장소를 읽기 전용 로컬 mirror로 가져온 후:
git init .bct-source
git -C .bct-source remote add origin https://github.com/irewon1-lgtm/bottleneck-control-tower.git
git -C .bct-source fetch --depth=1 --no-tags origin '+refs/heads/*:refs/remotes/bct/*'
python bct_stocks.py import-git --source .bct-source
```

## 이관 범위와 한계
현재 보이는 원격 브랜치들의 tip에 남은 연구 형식 파일을 content-addressed 방식으로 복사합니다. 원문 bytes·Git SHA·SHA256·원격 branch/commit/path·JSON 위치를 보존합니다. JSON과 기존 SQLite 행을 별도 레코드로 추출합니다. 테스트·fixture·앱 코드·워크플로는 근거로 사용하지 않고 제외 이유를 남깁니다. 90MiB 초과 개별 파일과 지원하지 않는 형식은 누락 목록에 표시합니다.

삭제된 모든 Git 과거 버전, 접속하지 않은 외부 URL의 원문 전체, 비공개 자료까지 이관했다고 주장하지 않습니다. 링크와 발췌를 가져온 것은 그 원문을 재검증한 것이 아닙니다. 원문 bytes 보존과 entity 추출 완료는 경제적 수혜 검증/미국 상장 검증/투자추천 완료가 아닙니다.

## 4단계
1. 전체 수혜기업 추출·기업명/티커 해석, 첫 10~20개 검토 묶음. 전체 후보 수 제한 없음.
2. 최신 공통일 가격·주식 수·수혜 크기·12개월 계기·자금/희석을 얇게 비교.
3. 통과 기업만 실적/현금/주당가치/2배·3배 역산/반증을 심층 카드로 통합.
4. 최종 비교·동결·비교군·저장. 사용자 PASS 후 다음 단계.

현 단계는 이관 및 원시 기업명 추출입니다. 후보 리스트·주가·목표주가·점수·매수 판단·동결일은 자동 생성하지 않습니다.

## 증분·감사
SHA로 원문 중복을 제거하고 기존 기록은 UPDATE/DELETE를 DB trigger로 금지합니다. 변경은 새 버전 INSERT입니다. import manifest에 모든 소스 ref를 고정합니다. 동일 manifest 재실행은 no-op입니다. `exports/import-receipt.json`, `exports/verification.json`, `exports/entity-mentions.json`, `exports/targets.json`에서 실측 결과를 확인합니다.

GitHub bootstrap은 전용 브랜치의 소스 파일 push 시에만 실행하는 초기화 경로입니다. 정기 수집·유료 AI 판독·매매는 없습니다. 동일 브랜치에서만 결과를 저장하며 non-fast-forward 충돌 시 실패합니다. DB 전후 백업을 보존합니다.
