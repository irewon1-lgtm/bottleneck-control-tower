# BCT V4 — 누락 뉴스·미판독 원인 추적 (2026-11-12)

작업 범위: GitHub에 실제 남아 있는 RSS 예약 실행 메타데이터, 2026-11-06 실패 원문 목록 아티팩트와 2026-11-12 정상 저장 아티팩트, 최신 CPU 실패 실행, 현행 코드. **전 기간 모든 원출처 기사 목록 또는 최신 비공개 CPU DB를 직접 전수 복원한 결과가 아니다.**

## 1. 확인 가능한 RSS 예약 운영 기록

- 조회된 기록 기간: 2026-09-30 10:07:31 UTC ~ 2026-11-12 00:06:42 UTC
- `RSS live environment check` schedule 실행: 232회
- 결과: SUCCESS 231회, FAILURE 1회
- 실패: [2026-11-06 08:19 KST, run 42128685872](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/42128685872)
- 전체 날짜의 수집작업 기록은 있지만, 이전 cron이 지금의 6회/일과 달랐을 수 있으므로 초기 12~16시간 간격을 곧바로 누락 예약으로 확정하지 않음
- 실행 성공은 해당 피드 125개의 기사 누락이 없었다는 증명이 아님

## 2. 실제 아티팩트 2개의 독립 대조

### 저장 실패 당시

- 실행 run: `42128685872`
- RSS artifact ID: `13460989300`, 이름 `rss-live-result`
- ZIP SHA256: `3a38692fab1e56220d78a1f86ededaf73fc4818d38102a4568ad898fc1bcb6d1`
- 초기 기사 8,939 → 임시 저장 8,968, 신규 29
- remote push: `fatal error in commit_refs_rules`로 실패
- 아티팩트 안의 `new-document-manifest.json`에서 실제 신규 문서 29개의 URL을 복원

### 2026-11-12 정상 저장 결과

- 실행 run: `43124853838`
- RSS artifact ID: `13902102291`, 이름 `rss-live-result-1`
- ZIP SHA256: `9c27bc543de49a0ad6504d7da21ce0eb6deb5893831aa876df52f358faf02f17`
- 초기 기사 10,179 → 최종 기사 **10,210**, 신규 31
- 최신 manifest의 `preexisting_urls` 및 이번 `documents`를 합친 URL과 과거 실패 당시 신규 URL을 **정확한 문자열 일치**로 비교

| 판정 단위 | 실측 |
|---|---:|
| 실패 당시 신규 기사 URL | 29 |
| 11월12일 기사 목록에 존재 | **29** |
| 여전히 확인되지 않는 URL | **0** |
| 기존 document ID가 이후 ID 집합에 존재 | 0 |

**결론:** 위 실패분은 현재 저장 기사 URL 기준 전량 재확인됐다. **누락 29건이라고 보고하거나 다시 수집해서 중복 저장하면 안 된다.** 문서 ID가 바뀌었을 가능성은 높으며, ID 단독으로 기사 동일성을 판단하면 안 된다. URL 존재는 원문 본문 FULL 확보 또는 CPU 판독 완료를 의미하지 않는다.

## 3. 최근에도 실제 실패하는 RSS 출처

2026-11-12 09:08 KST 종료된 정상 RSS 결과 아티팩트 기준 피드 125개 중 성공 114개, 실패 11개:

- ESA Space News / Launchers / Navigation / Space Engineering Technology / Telecommunications Integrated Applications / Space Science / Operations: HTTP 404, 총 7개 피드
- DOE Carbon Capture: TLS/SSL 연결 EOF
- DOE Fossil clean coal news: 네트워크 접근 불가
- DOE Fossil oil natural gas news, DOE Fossil petroleum reserves news: TLS/SSL 연결 EOF

11월6일 실패 실행에서는 16개 피드가 실패했으며, 일부 문제(USGS 정상 빈 피드, EIA 날짜 파싱 등)는 이후 수정됐으나 위 11개 출처의 실제 기사 누락 범위는 아직 UNKNOWN. **기사 출처별 아카이브와 보존된 시점 데이터를 따로 대조해야 한다.**

## 4. 확인된 CPU 자동 분석 공백

- 예약 CPU [run 43126034663](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43126034663)에서 `research` 실제 성공:
  - 대상 17개 문서
  - 신규 판독 24개 창
  - 6,774자
  - 이번 실행의 판독 내부 실패 0
  - 이번 실행의 메모리 내 처리 후 `CPU_pending=336` 보고
- `seal`은 암호화 결과 파일 1,386,717바이트를 생성
- 이후 `actions/cache/save`가 `cache write denied: token has no writable scopes`로 실패
- `publish`는 `fail-on-cache-miss` 때문에 실패
- 해당 실행의 결과 artifact도 **0건**. 따라서 24개 창과 336 pending은 **미게시 실행의 관측치**이며 최신 비공개 영속 상태의 실측 잔여량이라고 단정하지 않는다.
- 공개된 마지막 정상 연구 generation 20은 수동 연구 성과. 새 예약 판독 성공·영속 저장 영수증은 아직 확인하지 못함.

기존 고정 pin의 `.github/scripts/receive_cpu_delta.py`는 이전 체크포인트에서 확인되는 미완료 창을 이전 원문 artifact로부터 최대 8개 그룹·512MiB 범위에서 복구하려는 기능이 있다. 하지만 **아예 체크포인트에 쓰이지 못한 최초 유입 문서의 모든 과거 실행 재발견 기능까지 입증한 것은 아니다.** 이는 별도 검증·보완 대상이다.

## 5. 현재 수정 진행 상태와 미완료 검증

- [PR #54](https://github.com/irewon1-lgtm/bottleneck-control-tower/pull/54): cache read-only 정책을 우회하지 않고 인증된 암호화 결과를 아티팩트로 전달하는 격리 브랜치 수정.
- CPU 모델 고정 pin `6e788d18cf85fdb834b451bb35585a8b58925301` 변경 없음.
- GPG AES256·private CAS·정본 원장·최초 발견 기록·HOLDOUT·Q1~Q7 보존.
- 별도 `tools/bct_rss_gap_reconcile.py`를 제공해 원래 RSS artifact와 후속 artifact의 URL 보존을 새 HTTP 요청 없이 반복 검산 가능.
- 최신 main/DB 또는 배포는 이 감사/PR로 변경되지 않음.

### 판정

| 구분 | 판정 |
|---|---|
| 11월6일 29개 URL의 현재 저장 여부 | **PASS, 29/29** |
| RSS 전체 장기간 예약 중단 | 조회된 기간에서는 입증되지 않음 |
| 전체 공식 원출처 뉴스 빠짐없는 수집 | **UNKNOWN** |
| 실패/차단 출처별 기사 누락량 | **UNKNOWN** |
| RSS에 존재하지만 본문 미확보 | 일부 존재, 전수 수 미계수 |
| CPU 대기열 전체 최신 잔여량 | 비공개 원장 직접 복원 필요 |
| 예약 CPU 결과의 비공개 저장 및 복원 | **FAIL/BLOCKED** |
| 후속 자동 대기열 소진 | **NOT_RUN** |

일회성 과거 누락량은 '0건 전체'가 아니다. 전 산업·전체 기간·외부 원출처의 게시물 목록까지 대조하지 못했기 때문에 UNKNOWN이 남는다. 비공개 영속 DB에 저장하지 않은 임시 CPU 처리량을 복구 완료로 계산하지 않는다.
