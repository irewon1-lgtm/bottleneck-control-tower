# Current operational observation — A stage, no performance claim

Read-only observation started 2026-10-06 01:36:06 UTC. See current-observation.json for full query bounds, server metadata, metric source/window/unit, run IDs and completion time. This was one observer collection, not a document evaluation. Later additions to metric wrappers/draft validators did not trigger a second collection; the preserved snapshot is the evidence. Final helper code is the prepared next-observation version, not asserted byte-identical to the initial collector invocation.

## Actual status

- main: cae46f42a948a28b9154887cb922a60f92cbfec4. Related Stage 0 CI run 37388057269 succeeded (Python and JS).
- Workflow definitions: acquisition and SHADOW are GitHub active; definition existence/active is not actual job delivery. All available API run rows inspected: RSS 23/23, acquisition 4/4, SHADOW 0/0. Current SHADOW has no actual jobs or artifact to inspect; skip cause does not apply, no conclusion about whether a future job will pass the flag gate.
- Last RSS scheduled run: 37379872939, 2026-10-05 22:02:32Z, success; nominal 22:00Z. Last acquisition: 37380062579, started 22:04:16Z, completed/updated 22:05:15Z, success. Latest run job metadata is preserved. The last acquisition predates SHADOW main reflection; not an activation failure. Next nominal RSS is 2026-10-06 10:00Z, but no approved lateness alarm exists.
- Repository variable actual value: UNKNOWN, API 403. User's prior true-setting report is not an API observation. No variable, credential, flag or condition changed.
- review-lead-shadow-state: remote Git ref absent. No persisted activation/queue/first/history. Acquisition source cache activation is not SHADOW activation or preregistration t0.
- Last observer before this local execution: UNKNOWN (no prior observer checkpoint); this run has local UUID in current-observation.json. No observer production workflow exists/was activated.

## Throughput with denominators

| Value | Observed result | Window/source |
|---|---|---|
| New provenance-verified original documents | 59, as existing producer-reported count, not independently revalidated bodies | acquisition 37380062579; data 82ae564e38933ccb8e8ab1cd1851acd7ceaf9fcf:precursor-index.json; completed 2026-10-05 22:05:07.840748Z |
| Raw capture attempts/success/failure, unique original publishers/TARGETs | UNKNOWN | cache download blocked; no source-body restoration |
| SHADOW execution count | 0 | complete API listing through observation, total_count=0 |
| Deterministic processed documents in SHADOW | no persisted receipt; count UNKNOWN | store absent; not equated with producer's 59 verified bodies |
| Completed semantic documents | 0 persisted | cumulative SHADOW state only; not prior development readings |
| Pending semantic queue | 0 persisted; undelivered documents/readings-needed UNKNOWN | state branch absent; no SHADOW delivery yet |
| Newly pending this run / oldest waiting time | UNKNOWN / UNKNOWN | no run audit or actual queue |
| REVIEW_LEAD / HOLD / EXCLUDED / CONFIRMATION | 0 / 0 / 0 / 0 persisted cards | cumulative SHADOW state only, not semantic outcome of all upstream documents |
| State persistence success/failure | NOT_EVALUATED | SHADOW never ran; absence not classified as persistence failure |

No completed semantic outcome exists in this operational SHADOW cohort. These zero counts mean NO_SHADOW_EXECUTION, not “59 documents yielded no worthwhile leads.” Historical development cards and research reports are not this throughput denominator. No market/lead-time/accuracy results calculated.

## Artifact and access

precursor-private-cache id 11373163316, 13,869,442 bytes, created 2026-10-05T22:05:10Z, expires 2026-11-04T22:05:08Z; API expired=false at observation. Metadata accessible, actual archive download denied (403/Forbidden at redirect). Restore NOT_PERFORMED; body/provenance and cache recovery not independently verified. No signed URL or credential saved. This runtime access denial is not evidence that the GitHub runner itself has the same artifact access issue.

## Semantic actor / path

Actual main .github/workflows/review-lead-shadow.yml invokes frozen review_shadow run without --semantic. No AI/manual reader or semantic completion service is connected there. Existing deterministic extractor queues unreviewed eligible documents; attributed Objective-bound packets can be passed through the existing --semantic CLI, anchored to queue document ID/hash. No actor completion or semantic provenance is observed in persisted operational state. A does not connect a reader, investigate pending documents or change criteria.

## Limits and protections

GitHub metadata lists are complete for these workflows, latest job details only. Prior executions' internal counts are not summed from different code/cohort versions. No restoration of inaccessible bodies. No newly confirmed T, no T search, no model knowledge cutoff claim. Same-GitHub observer is not an external independent watchdog.

Local observer used read-only API plus fetch/show/ls-remote, wrote only this A report. main/data/LIVE remote refs at verification remained cae46f4 / 82ae564 / 21e1be0; no shadow-state branch appeared. No producer step, operational workflow, existing source, queue, card or criterion changed. The actual absent store cannot supply a restored-store immutability test; synthetic boundary checks exercise existing files separately. Natural scheduled changes, if later observed, must be logged as operation changes rather than this patch.

Status: A preparation can finish with the documented permission/body-access limits. No t0; no preregistration approval; no main merge; no observer schedule activation; no B-stage execution.
