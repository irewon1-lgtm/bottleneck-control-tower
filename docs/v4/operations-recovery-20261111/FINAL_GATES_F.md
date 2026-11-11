# 최종 운영 main F — 실제 Gate 0~6 결과

**PASS — 현재 운영 코드 F에서 필수 Gate 0~6이 모두 실제 실행되어 통과했다.** `FULL` 완료·정기 CPU 운영·미래 병목 예측 성능은 이 결과에 포함하지 않는다.

- 작업 ID: `BCT_V4_AUTOMATION_FULL_RECOVERY_20261111`; 계획 `BCT-V4-Q-1.0` 유지.
- 대상 SHA: `66b790f2737a350950e2f609def51af3b18acf45`.
- 실제 실행: [43045049058](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43045049058), 수동 `workflow_dispatch`, attempt 1; storage job `130606669122` SUCCESS.
- 실행 시각: 2026-11-12T00:06:44+09:00 → 2026-11-12T01:12:53+09:00 (KST).
- [기계 판독 증거](FINAL_GATES_F.json)에 실제 GitHub 메타데이터와 독립 파일 검증을 기록했다.

| 필수 실제 단계 | 결과 | 완료 시각(KST) |
|---|---|---|
| Gate 0 then real GitHub storage Gate 1 | PASS | 2026-11-12T00:24:34+09:00 |
| Gate 2 original source access on GitHub runner | PASS | 2026-11-12T00:25:17+09:00 |
| Gate 3 full failed-source inventory | PASS | 2026-11-12T00:25:20+09:00 |
| Gate 4 official original verification and evidence holds | PASS | 2026-11-12T00:26:22+09:00 |
| Stage 5 cost-zero real-source reading pilot | PASS | 2026-11-12T01:04:03+09:00 |
| Gate 5 actual readings and atomic production queue recovery | PASS | 2026-11-12T01:07:02+09:00 |
| Restore original 230-source regression corpus | PASS | 2026-11-12T01:08:28+09:00 |
| Gate 6 real source E2E and required whole regressions | PASS | 2026-11-12T01:12:40+09:00 |

검증 artifact `13870728991` (`bct-recovery-checkpoint-43045049058`)는 **58,714,110바이트**, SHA-256 `d926c9ffa9ed462d0ef4936ea01c97f352c977ab46451e8746d9076c0a539635`다. GitHub digest와 실제 내려받은 ZIP 바이트가 일치한다. 만료 시각은 **2026-12-12T01:12:41+09:00 (KST)**이다. 원본 입력의 별도 보존 기간과 혼동하지 않는다.

기존 `bct_release_guard.py`는 최초 main `28d0b8c648c0218ab2e74a1fa04ca8d63e659933` 대비 diff가 없으며 SHA-256은 `a7736a4260c27fa1c98c60488d9c3f449b8b2b1d7a5409de200cc12bd6d51b87`다. 현재 GitHub run·필수 step·artifact·검증 코드 트리 조회를 사용하는 기존 검증기로 **262개 코드/시험 파일 일치**를 재확인했다. 파일 제외 규칙이나 PASS 기준은 변경하지 않았다. 이후 생성되는 릴리스 영수증과 기존 범위 밖 재개 요청 JSON 두 파일만 연결하므로, 병합 후 실제 main에서도 동일 검증을 다시 확인해야 한다.

재개 영수증은 `resume_input_only=false`이며 **21개 root 파일 SHA-256 전부 일치**했다. compact fixed230은 원본 230문서의 body/raw 해시를 확인한 **460개 파일·41,784,646바이트**다. file-map SHA-256 `a489b7f008fa80bf3729d1563a29c7e60effd4da011ba9fa54abed010689e566`; source fingerprint `acd344732f2f087b42767bfe32d9f16d96da6de49a766d6fc73f3c0ed298f9ec`. 원본은 수정하지 않았고, 입력 복원 자체의 HTTP 재수집·새 CPU 추론은 0건이다.

이번 Stage5는 기존 승인 Qwen backlog 경로다. E 실행에서 실제 완료된 **31건을 복원하고 F에서 19건만 새 추론**하여 총 50개 실제 결과를 Gate5에서 연결했다. 완료된 31건을 다시 추론하지 않았다. Gate5는 원격 재시작 동일 generation 및 중단·경합 복구를 PASS로 확인했다. 이를 신규 일반 GLiNER 판독 50건으로 집계하지 않는다.

중간 `local-reader-probe.json`의 `status=BLOCKED / PRODUCTION_QUEUE_RECOVERY_NOT_YET_CONNECTED`는 생산 큐 연결 전에 저장된 상태다. 실제 후속 Gate5 실행과 최종 checkpoint의 `gate5=PASS`가 큐 연결 결과를 나타내며, 중간 파일 값을 바꿔 쓰지 않았다.

**별도 미완료 조건:** 최종 checkpoint의 `full_clean_status=BLOCKED`, 사유 `OPERATING_PUBLICATION_STAGE_7_AND_FULL_REQUIRED`, 예측 성능 `UNVERIFIED`, `live_early=0`을 그대로 유지한다. 선택 Stage7/FULL 단계와 preserve-input job은 해당 실행 모드에서 SKIPPED이며 필수 Gate에 포함되지 않는다. 이 수동 Gate 실행은 신규 GLiNER 문서의 정기 수집→판독→비공개 저장→검토 완료 증거가 아니다.

다음 행동은 진짜 릴리스/재개 영수증 연결 후 실제 main 검증, 최신 private bridge 복구, 신규 원문의 CPU 판독·새 프로세스 복원·REVIEW·공개 갱신을 확인하는 것이다. 새 모델·유료 API·정답·HOLDOUT·판정 기준 변경은 없다.
