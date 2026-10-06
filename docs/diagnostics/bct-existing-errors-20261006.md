# Existing BCT errors: minimal branch-only follow-up

Base main: `ec2443cc41c15f7f37ffcaaa961be3e748b4d431` (read from remote at task start).
Branch: `codex/bct-existing-errors-minimal-20261006`.
No operational dispatch, retry, secret/variable edit, paid AI call or state write was performed.

## Sidecar: cause unconfirmed; no speculative change

Run `37380062515`, job `111999438902`: job metadata confirms failure in
`Publish candidate sidecar only`. Direct job-log access failed; `gh run view --log-failed`
reported Forbidden. Numeric HTTP status was not available in that log response.
Artifact metadata is readable: `11373059341`, `future-bottleneck-candidates`,
not expired. Artifact download was denied; its body was not inspected.

Read-only `future-bottleneck-data` commit history, bounded to this run's
2026-10-06 07:04:16–07:10:45 Asia/Seoul window, contains 23 storage commits.
Four touch `future-candidates.json`:

| Commit | Commit metadata time (Asia/Seoul) |
|---|---|
| `646185bd251ebe151b569cf5cb0f5e4f615094c6` | 07:06:46 |
| `d6a5a753e0c55933a9d140cabbe4c88c90827abc` | 07:07:52 |
| `19e6b5af2d44915a882a8c5c7426d72734c78967` | 07:08:39 |
| `5248b80befc256b5a31e28ae8e95edae53777683` | 07:09:58 |

First inspected commit `6bed7022eeab7df038196a53faef9e25ef7d704f` adds a shard;
last inspected `c449f72ada373fd5f33303f9156a110bb584e5ee` adds another shard at 07:10:22.
This demonstrates saved changes during the failure window, not an atomic rollback.
Commit timestamps and generic messages alone do not prove each change's run attribution
or establish which publish/recovery/queue subcommand failed. Exact failed subcommand,
run-level completeness and final manifest-to-artifact correspondence remain UNKNOWN.
The later successful run `37384991579` does not resolve the earlier run's effects.
CAS, immutable shards, hashes and retry/concurrency logic were left unchanged.

Read commands: job/artifact Actions API; `gh run view --log-failed`;
`gh run download --name future-bottleneck-candidates`; commits API filtered by
`sha=future-bottleneck-data`, run time window, and separately `path=future-candidates.json`.
All were read-only; download denial was not bypassed.

## RSS AI: runtime configuration issue reported; current configuration UNKNOWN

Run `37383222409`, job `112010112040`: metadata confirms failure in
`Annotate up to 20 unprocessed signal articles`, with the persistence step skipped.
The user supplied the error `OPENAI_API_KEY secret missing; no articles processed`.
Direct original log access is denied, so that precise text is user-provided evidence.
Current `.github/workflows/rss-ai.yml` passes `${{ secrets.OPENAI_API_KEY }}` to
`OPENAI_API_KEY`; Python checks the same name before any provider call. No job
`environment` is declared. No reference mismatch was found. Repository secret-name
listing returned HTTP 403; current secret existence/availability is UNKNOWN.
Therefore no workflow/code change or provider test was performed. The reported run
is BLOCKED_CONFIG; verifying/configuring the intended `OPENAI_API_KEY` is outside
this task's authorization. RSS AI is separate from REVIEW_LEAD semantic review.

## Observer: reproduced and minimally corrected

Previously the same instant `2026-10-05T15:00:00+00:00` and
`2026-10-06T00:00:00+09:00` produced different scheduled results because cron hours
were applied in the input timezone. `scheduled_slot` now requires an explicit
timezone and converts the timestamp to UTC before applying the existing cron.
Timezone-naive input previously had no documented interpretation; it is rejected
with ValueError rather than inferred from the host's local timezone. Production
callers use UTC-aware timestamps. Output fields and existing UTC results are preserved.

Regression covers UTC/KST equality at all six slots immediately before/at/after,
KST midnight before/at/after, existing UTC output and naive-input rejection.
No cron dependency, scheduler, threshold or candidate rule was added.

## Local verification (isolated temporary checkout, credentials absent)

Python 3.12.14; editable install with `python -m pip install -e '.[test]'`.
The checkout is shallow (depth 1 before the new commit).

- `python -m pytest tests/test_review_evaluation_a.py tests/test_review_evaluation_activation.py -q`: 36 passed.
- `python -m pytest -q`: 606 passed, 1 skipped.
- `node --test tests/*.js`: 27 passed.
- The existing skip requires unavailable independent frozen real pre-public holdout
  and archived precursor facts. It was not added or changed.

The full suites ran once after the code/test change. Remote CI is reported separately
after push; local results do not imply remote success. No forecasting-performance,
actual SHADOW run or candidate-quality claim is made.

## Protection

Only the observer function, its related test module, and this new diagnostic report
are changed. All existing workflow bytes (including RSS six slots), Objective Lock,
V2/EARLY/REVIEW_LEAD code, preregistration/manifests and frozen outputs are preserved.
No main merge or operational activation is part of this change.
