# 최종 운영 main I — 실제 Gate 0~6 결과

**PASS — 현재 운영 대상 I에서 필수 Gate 0~6이 모두 실제 실행되어 통과했다.** 릴리스 영수증 병합 후 main 검증, 정기 CPU 운영, 미래 병목 예측 성능은 각각 별도 기준이다.

- 작업 ID: `BCT_V4_AUTOMATION_FULL_RECOVERY_20261111`; 계획 `BCT-V4-Q-1.0` 유지.
- 대상 SHA: `5c66cd8ef5ec47046024027d52e0e8b755d1f012`; 기존 CPU 처리 core `6e788d18cf85fdb834b451bb35585a8b58925301` 유지.
- 실제 실행: [43067179780](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43067179780), 수동 `workflow_dispatch`, attempt 1; storage job `130685154506` SUCCESS.
- 실행 시각: 2026-11-12T02:20:21+09:00 → 2026-11-12T02:49:09+09:00 (KST).
- [기계 판독 증거](FINAL_GATES_I.json)에 실제 GitHub 메타데이터와 독립 바이트 검증을 기록했다.

| 필수 실제 단계 | 결과 | 완료 시각(KST) |
|---|---|---|
| Gate 0 then real GitHub storage Gate 1 | PASS | 2026-11-12T02:37:09+09:00 |
| Gate 2 original source access on GitHub runner | PASS | 2026-11-12T02:37:49+09:00 |
| Gate 3 full failed-source inventory | PASS | 2026-11-12T02:37:51+09:00 |
| Gate 4 official original verification and evidence holds | PASS | 2026-11-12T02:38:53+09:00 |
| Stage 5 cost-zero real-source reading pilot | PASS | 2026-11-12T02:43:48+09:00 |
| Gate 5 actual readings and atomic production queue recovery | PASS | 2026-11-12T02:46:19+09:00 |
| Restore original 230-source regression corpus | PASS | 2026-11-12T02:46:20+09:00 |
| Gate 6 real source E2E and required whole regressions | PASS | 2026-11-12T02:48:58+09:00 |

검증 artifact `13877912797` (`bct-recovery-checkpoint-43067179780`)는 **60,268,206바이트**, SHA-256 `4dae80ee05be92ef6d7987c10817067c223a7f0e62eb9b03b46f3e5c582f6afe`다. GitHub digest와 실제 내려받은 ZIP 바이트가 일치한다. 만료 시각은 **2026-12-12T02:48:59+09:00 (KST)**다.

기존 `bct_release_guard.py`는 최초 main `28d0b8c648c0218ab2e74a1fa04ca8d63e659933` 대비 변경이 없다. 검증기 SHA-256 `a7736a4260c27fa1c98c60488d9c3f449b8b2b1d7a5409de200cc12bd6d51b87`; 현재 GitHub의 실제 run·필수 단계·artifact·코드 트리를 조회하는 기존 검증기로 **262개 코드/시험 파일 일치**를 재확인했다. I 동결 파일 지도 SHA-256 `3139e5460cd82f4d3a4a4e8f4623a79c1261e87c18dd21355bb566e944c9e706`의 모든 Git blob도 후보 트리와 일치한다. 검증 장치·파일 제외 규칙·PASS 조건을 변경하지 않았다.

릴리스 후보 `ceebce742d5b31c89c863cfad5bdbea59121a79f`는 I 대비 `.github/bct-recovery-request.json`, `config/bct-operating-release.json` **두 파일만 변경**하며 기존 prepare-receipts가 생성한 바이트와 완전히 같다. 이 경로들은 원래 검증 범위 규칙에 따라 처리된다. 실제 병합 후 main의 기존 검증기 PASS는 별도 확인할 항목이다.

재개 요청은 `resume_input_only=false`, 기존 지원 설정 `reader_batch_limit=1`이다. **21개 root 파일 SHA-256 모두 일치**했고 cache inventory도 실제 복원 검증을 통과했다. compact fixed230은 정확한 원본 230문서의 body/raw 해시를 확인한 **460개 파일·41,784,646바이트**다. file-map SHA-256 `a489b7f008fa80bf3729d1563a29c7e60effd4da011ba9fa54abed010689e566`; source fingerprint `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec`. compact 입력 복사는 새로운 Gate 증거로 취급하지 않으며 후속 Gate6 실행은 별도 실제 단계다.

이번 Stage5는 기존 승인 Qwen backlog 경로에서 **미판독 원문 1건을 새 추론**하고 Gate5가 그 결과 1건을 실제 큐에 연결했다. 기존 F 판독을 다시 실행하지 않았고 이전 1/10/50 자격 증거는 기존 해시·범위·모델 영수증 검증으로 유지했다. 이는 새 GLiNER 문서 1건 실적이 아니다. 생산 재시작 동일 generation, 실제 원격 중단·경합 복구, 기존 판정·완료·실패 이력 보존을 PASS로 확인했다.

중간 `local-reader-probe.json`의 `status=BLOCKED / PRODUCTION_QUEUE_RECOVERY_NOT_YET_CONNECTED`는 생산 큐 연결 전의 기록이며 값을 바꾸지 않았다. 후속 실제 Gate5와 최종 checkpoint가 큐 연결 PASS를 확인한다.

**별도 미완료 조건:** 최종 checkpoint의 `full_clean_status=BLOCKED`, 사유 `OPERATING_PUBLICATION_STAGE_7_AND_FULL_REQUIRED`, 예측 성능 `UNVERIFIED`, `live_early=0`을 유지한다. 선택 Stage7/FULL 단계와 preserve-input job의 SKIPPED는 이 실행 모드의 선택 분기이며 필수 Gate 통과로 바꾸어 집계하지 않는다. 수동 Gate 실행은 정기 CPU 자동 운영이나 독립 선행탐지 성능의 증거가 아니다.

다음 단계는 CI 확인 후 실제 영수증만 일반 병합하고, 병합된 main에서 기존 검증기를 다시 실행하는 것이다. 이미 별도 증거로 확인한 C6 신규 GLiNER 수동 왕복·연구 DB·검토·공개 데이터 결과와 이 Gate 결과를 섞지 않는다. 새 모델·유료 API·정답·HOLDOUT·판정 기준 변경은 없다.
