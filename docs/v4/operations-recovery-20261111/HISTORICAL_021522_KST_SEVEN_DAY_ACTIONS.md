# Rolling seven-day Actions metadata snapshot

Fixed UTC creation window: **2026-11-04T17:15:22Z through 2026-11-11T17:15:22Z** (604,800 seconds). Fetch finished 2026-11-11T17:15:33Z.
Retrieval: 5 page(s), 485 unique runs, GitHub total 485; truncated=False.

| Scope | Observed counts |
|---|---|
|All branches/all events|485 runs: success 333, failure 83, skipped 53, cancelled 15, unfinished 1|
|Main/all events|359 runs: success 230, failure 64, skipped 53, cancelled 11, unfinished 1|
|Main automatic: schedule/workflow_run/repository_dispatch|329 runs: success 206, failure 60, skipped 53, cancelled 10, unfinished 0|
|Main schedule only|84 runs: success 69, failure 15, skipped 0, cancelled 0, unfinished 0|
|Main manual workflow_dispatch|16 runs: success 12, failure 3, skipped 0, cancelled 0, unfinished 1|

Successful distinct workflow names in main automatic scope: **7** — BCT read-only evaluation observer; BCT recovery storage gates; New precursor evidence acquisition; REVIEW_LEAD SHADOW intake; RSS AI annotation; RSS live environment check; Read-only BCT Pages.

| Workflow | Main automatic counts | Main manual dispatch counts |
|---|---|---|
|BCT read-only evaluation observer|14 runs: success 14, failure 0, skipped 0, cancelled 0, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|BCT recovery storage gates|3 runs: success 3, failure 0, skipped 0, cancelled 0, unfinished 0|3 runs: success 2, failure 1, skipped 0, cancelled 0, unfinished 0|
|Future bottleneck body candidates|57 runs: success 0, failure 56, skipped 1, cancelled 0, unfinished 0|1 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 1|
|New precursor evidence acquisition|43 runs: success 41, failure 0, skipped 1, cancelled 1, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|REVIEW_LEAD SHADOW intake|53 runs: success 48, failure 3, skipped 2, cancelled 0, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|RSS AI annotation|14 runs: success 14, failure 0, skipped 0, cancelled 0, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|RSS live environment check|42 runs: success 41, failure 1, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|
|Read-only BCT Pages|60 runs: success 45, failure 0, skipped 6, cancelled 9, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|V4 CPU main cache seed|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|
|V4 CPU private research consumer|43 runs: success 0, failure 0, skipped 43, cancelled 0, unfinished 0|9 runs: success 7, failure 2, skipped 0, cancelled 0, unfinished 0|
|V4 CPU private settings check|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|

One manual Future run is in progress, making overall/manual terminal successes a lower bound for eventual outcomes; all main automatic runs in this fixed snapshot are terminal. Workflow success does not prove CPU or semantic reading. RSS43032161571 is manual; acquisition43032565649 is automatic. Manual failed research/recovery runs remain outside the main automatic denominator. AI annotation/REVIEW workflow success does not mean an API-key-backed semantic review occurred. Automatic recovery-storage workflow success can be preservation-only and does not independently establish fresh Gates.

Named-run checks:
- 43032161571: RSS live environment check; event=workflow_dispatch, branch=main, status=completed, conclusion=success, attempt=1.
- 43032565649: New precursor evidence acquisition; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.
- 43057947172: V4 CPU private research consumer; event=workflow_dispatch, branch=main, status=completed, conclusion=failure, attempt=1.
- 43060982183: V4 CPU private research consumer; event=workflow_dispatch, branch=main, status=completed, conclusion=failure, attempt=1.
- 43064438463: REVIEW_LEAD SHADOW intake; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.
- 43064438487: Read-only BCT Pages; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.

These fresh counts do not rewrite earlier fixed-window historical CPU-skip counts. No seven-day operating-success claim is made. Detailed allowlisted metadata and by-workflow/event/conclusion counts: /tmp/bct-final-7day-actions.json.
