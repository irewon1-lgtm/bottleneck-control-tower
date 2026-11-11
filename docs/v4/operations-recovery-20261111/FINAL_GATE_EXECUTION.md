# Final Gate execution checklist

Root merged PR48 including operating-restore repair `be232a25d22c0a3945db7902b2e98b68344943e8`, froze main **`933a29638c06d72d4cf4c17d843cfec2978066d2`**, then dispatched the single actual manual Gate run [43032067823](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43032067823) with `full_pipeline=false` around13:46UTC. The261 guarded files have file-set SHA256 `02eefa0b55116e777c3aecc62f41330cae98f13087d52741e12b112dda802944`. Actual result is pending; this checklist is not a Gate PASS. Root owns dispatch, main merges and operating writes.

The focused restore repair passed1104 Python tests +1 unchanged holdout skip,40 focused tests, changed-script mypy/Ruff/diff checks; independent review passed46 focused tests. It follows the active successful release/request origin exactly, supports authenticated preserved copies, refuses newer failed input for automatic operating use, and retains the300s bound. General Gate continuation can still use explicit newer partial input without claiming proof.

## Before root dispatch

1. Root recorded the final freeze above. Keep all guarded code/test/workflow/config/JS files unchanged through actual Gate and receipt preparation. Observation-only43031947496 was preservation maintenance triggered by a Future guard failure, not the real manual Gate.
2. Refresh immutable public/private snapshots immediately before the run. Root’s immediately-pre-Gate snapshot at13:45:48UTC ([FINAL_PRE_GATE_REFS.json](FINAL_PRE_GATE_REFS.json)) binds `future-bottleneck-data` was still `8730f5cdec9c7f6eb624df1c6d40a76b2b5d1bfe`, authoritative blobs `faf0b378a33a629145eb1f7218d58369280fe87e` / `adbec29fe290ff6a131c792861e564a15577c989`; both UI blobs and full root tree are in JSON. Review was `528ae7d4402402ca6828aa9467bf841c62fb71a8`; LIVE was `21e1be03b522d81a20d95e79694617967d8a608a`. The earlier13:32 snapshot remains historical in JSON.
3. **Data advanced:** `4b401f2b6af0084c856a8d7acb6bf2f829b2d872`; current SQLite blob `f77578938e886b698ba8b79f8b4437028737ced1`, previous `4d398e033167293932f346c929f068b7f6eb54d9`, state `4e3a8aaed8ef52796c2b8442727e22a4770cb890`. The old064 snapshot is historical; preserve the current generation and legitimate new inputs. Reuse the existing232MB paired future backup only while its exact immutable roots remain equal.
4. Check active writers/worker claim and retain CAS protections. The13:40 latest-run observation showed a branch test only; refresh rather than treating this as a permanent lock.
5. Preserve the original logical38331945733 resume identity. Actual preservation-only run [43020215888](https://github.com/irewon1-lgtm/bottleneck-control-tower/actions/runs/43020215888) passed with storage Gates skipped. Wrapper13854217801 is45,073,952B, SHA `6712804dc804cd2efb65a1d75b9b1e0e0ef7fa7b5036349a8ff3dd00eaeefdb3`, expires2027-02-09 12:25:34UTC. Actual runner readback verified original `00ac5d…` plus19 root pins/3280 cache files. It is available input transport, not fresh Gate proof. Do not substitute wrapper run/ID into the logical resume descriptor.
6. First fresh Gate still needs the unexpired original source/RSS inputs once because prior receipts contain no460-file corpus. Current metadata confirms source expires2026-12-11 and RSS2027-02-09. The bounded source-only receive avoids49GB evaluations expansion. The successful new checkpoint must contain the exact460 files /41,784,646B, golden map `a489b7f0…` and fingerprint `acd34473…`; later restores and bounded preservation reuse this compact corpus.

Keep `preserve_resume_only=false` and **`full_pipeline=false`**. The shipped request has no configured true FULL override and resumes38331945733. Root's current dispatch command is:

```sh
gh workflow run bct-recovery.yml --repo irewon1-lgtm/bottleneck-control-tower --ref main -f preserve_resume_only=false -f full_pipeline=false -f archive_key=recovery -f resume_run_id=38331945733
```

Confirm the resulting actual run's head equals the final frozen main SHA. An observation-only preservation run is not a Gate run. `full_pipeline=true` skips required0–6 steps and cannot provide this proof.

## Existing effects and required readback

| Execution | Existing permitted effects |
| --- | --- |
|Gate0/1|Read immutable public/SQLite baseline; isolated real storage/fault/interleaving probes; conditional preserving repair; atomic production candidate/queue projection.|
|Gate2–4|Actual source/evidence checks; reuse authenticated journals and stable relevant source-code identity. No fabricated coverage.|
|Stage5|Restore/build the same Qwen revision `bb5d59e…` and llama `79e2e74…`, exact existing two GGUF hashes; verify prior qualification; existing bounded DRAIN up to50 fresh calls/30min. Calls/deadlines can fail; retain actual receipts.|
|Gate5|Verify actual native readings and append preserving histories; CAS-update candidate/tracking/UI/shards together. Native fault probes stay isolated.|
|Gate6|Actual source traces, exact230 QA and unchanged full regressions/quality/frozen prediction checks. No Stage7/FULL or seven-day/prediction-success claim.|

After the run, require completed success on main at the exact frozen SHA, the storage job and all eight unchanged REQUIRED step names successful, and checkpoint status/PASS for gate0..6. Check real source/model counters and immutable before/published generations. Recheck the paired roots at one immutable commit. A later failure does not undo earlier legitimate publications; any compensation must preserve concurrent new inputs/readings/history and append a conditional generation at the fresh head. Never reset blindly to an older snapshot.

From a clean checkout with exactly the frozen code, run this **only after the actual successful run ID and frozen SHA are known**; replace those two labels and keep the destination/output paths new:

```sh
PYTHONPATH=src timeout 300 /workspace/bottleneck-control-tower/.venv/bin/python .github/scripts/recovery_artifacts.py prepare-receipts --root . --gate-run-id 43032067823 --expected-code-sha 933a29638c06d72d4cf4c17d843cfec2978066d2 --destination /tmp/bct-automation-full-recovery-20261111/receipt-43032067823 --output /tmp/bct-automation-full-recovery-20261111/receipt-43032067823.json
```

The helper verifies the unchanged real guard and actual checkpoint/artifact, requires the compact corpus, and prepares both `config/bct-operating-release.json` and `.github/bct-recovery-request.json` with latest completed readings/source journals/cache pins together. Review and publish these two metadata files only. Genuine proof cannot be renewed by copying. A later preservation-only actual runner readback can verify the new compact checkpoint without repeating Gates/model reads.

## Downstream after receipt publication

The two receipt paths alone do not match Future's push filter. The next successful main RSS workflow, Future schedule(10:45/22:45UTC), manual run or existing publication dispatch can pass the guard and proceed. Future can publish collection patches and existing bounded extra passes, perform up to5 same-pinned Qwen automatic reads, then publish the atomic operating queue/UI. V4 private GLiNER ENABLED=false does not disable this separate existing Qwen path. Gate0–6 with `full_pipeline=false` does not itself execute Stage7 publication dispatch. Record new actual writes/calls separately from Gate evidence.

Input and compact-corpus expiry maintenance is bounded automatic. Genuine proof renewal remains a real root-controlled Gate run plus truthful receipt publication; no automatic heavy Gate/merge was added, and fully automatic sustainable proof PASS is not claimed.

If local `gh` artifact download hits the already observed signed-blob403, do not retry it or change frozen main. Root can fetch the exact actual artifact through the supported GitHub connector, validate its size/SHA, and use a temporary local transport adapter for only that exact artifactZIP command; all metadata still comes from the real GitHub API. The unchanged helper then validates bytes, provenance, payload and genuine guard again. No existing preservation-only runner mode prepares a new release receipt; it intentionally follows the current pinned logical request. This fallback transports authenticated bytes and never manufactures proof.

Root also authorized RSS43032161571 in parallel. It can legitimately advance the canonical data generation after the pre-Gate snapshot; attribute and preserve those new inputs separately from Gate effects. The post-Gate command above is bound to43032067823 and must wait for its actual completed success; a running/failed result is rejected.
