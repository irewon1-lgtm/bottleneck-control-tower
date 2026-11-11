# Rolling seven-day Actions metadata snapshot

Fixed UTC creation window: **2026-11-04T18:00:41Z through 2026-11-11T18:00:41Z** (604,800 seconds). Fetch finished 2026-11-11T18:00:52Z.
Retrieval: 5 page(s), 499 unique runs, GitHub total 499; truncated=False.

| Scope | Observed counts |
|---|---|
|All branches/all events|499 runs: success 345, failure 83, skipped 54, cancelled 16, unfinished 1|
|Main/all events|371 runs: success 240, failure 64, skipped 54, cancelled 12, unfinished 1|
|Main automatic: schedule/workflow_run/repository_dispatch|339 runs: success 213, failure 60, skipped 54, cancelled 11, unfinished 1|
|Main schedule only|85 runs: success 69, failure 15, skipped 0, cancelled 0, unfinished 1|
|Main manual workflow_dispatch|17 runs: success 14, failure 3, skipped 0, cancelled 0, unfinished 0|

Successful distinct workflow names in main automatic scope: **7** — BCT read-only evaluation observer; BCT recovery storage gates; New precursor evidence acquisition; REVIEW_LEAD SHADOW intake; RSS AI annotation; RSS live environment check; Read-only BCT Pages.

| Workflow | Main automatic counts | Main manual dispatch counts |
|---|---|---|
|BCT read-only evaluation observer|14 runs: success 14, failure 0, skipped 0, cancelled 0, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|BCT recovery storage gates|5 runs: success 5, failure 0, skipped 0, cancelled 0, unfinished 0|4 runs: success 3, failure 1, skipped 0, cancelled 0, unfinished 0|
|Future bottleneck body candidates|57 runs: success 0, failure 56, skipped 1, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|
|New precursor evidence acquisition|43 runs: success 41, failure 0, skipped 1, cancelled 1, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|REVIEW_LEAD SHADOW intake|55 runs: success 50, failure 3, skipped 2, cancelled 0, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|RSS AI annotation|15 runs: success 14, failure 0, skipped 0, cancelled 0, unfinished 1|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|RSS live environment check|42 runs: success 41, failure 1, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|
|Read-only BCT Pages|64 runs: success 48, failure 0, skipped 6, cancelled 10, unfinished 0|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|
|V4 CPU main cache seed|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|
|V4 CPU private research consumer|44 runs: success 0, failure 0, skipped 44, cancelled 0, unfinished 0|9 runs: success 7, failure 2, skipped 0, cancelled 0, unfinished 0|
|V4 CPU private settings check|0 runs: success 0, failure 0, skipped 0, cancelled 0, unfinished 0|1 runs: success 1, failure 0, skipped 0, cancelled 0, unfinished 0|

The current queued scheduled RSS AI annotation run makes observed terminal successes a lower bound for eventual outcomes. Workflow success does not prove CPU or semantic reading. RSS43032161571 is manual; acquisition43032565649 is automatic. Manual failed research/recovery runs remain outside the main automatic denominator. AI annotation/REVIEW workflow success does not mean an API-key-backed semantic review occurred. Automatic recovery-storage successes can be preservation-only, not fresh Gate proof.

Named-run checks:
- 43032161571: RSS live environment check; event=workflow_dispatch, branch=main, status=completed, conclusion=success, attempt=1.
- 43032565649: New precursor evidence acquisition; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.
- 43057947172: V4 CPU private research consumer; event=workflow_dispatch, branch=main, status=completed, conclusion=failure, attempt=1.
- 43060982183: V4 CPU private research consumer; event=workflow_dispatch, branch=main, status=completed, conclusion=failure, attempt=1.
- 43064438463: REVIEW_LEAD SHADOW intake; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.
- 43064438487: Read-only BCT Pages; event=workflow_run, branch=main, status=completed, conclusion=success, attempt=1.

These fresh counts do not rewrite earlier fixed-window historical CPU-skip counts. No seven-day operating-success claim is made. Detailed allowlisted metadata and by-workflow/event/conclusion counts: /tmp/bct-final-7day-actions-LATEST.json.


Classifier reuse (metadata comparison only): 114 current main automatic failure/skipped runs; 112 unchanged prior classified IDs. Removed prior IDs: [41881922653]. New IDs: [43070231522, 43071173782]. No new job or log fetches.

Latest unfinished metadata:
- 43072823646: RSS AI annotation; schedule; status=queued; created=2026-11-11T17:55:37Z; head=5c66cd8ef5ec47046024027d52e0e8b755d1f012.

No RSS live schedule created at/after18:00UTC appears in this one-time snapshot. Latest RSS live schedule:43069839035,created17:36:44UTC,SUCCESS. The queued run is RSS AI annotation43072823646,created17:55:37UTC,not a new RSS live collection. No run was awaited.
