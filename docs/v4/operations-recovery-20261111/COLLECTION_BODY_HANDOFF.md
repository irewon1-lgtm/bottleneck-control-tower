# Collection → body → product source handoff

Task `BCT_V4_AUTOMATION_FULL_RECOVERY_20261111`. Component commits: `b60de498e16b56ab1428a4fdeae49f7a06f56ea1` and `c34b6106ea883d48fdc8d898e95db1034b353e09`, isolated from development base `a6f5117`. Local component checks pass; main integration and a new actual operating run remain parent-controlled.

The actual paths differ. Main acquisition calls `precursor_collection.structure` and scope reader **5**, so PR44's generic product/order fix applies there. CPU pin `221fa92b` calls `cpu_automation.work → cross_industry.reading_result → evidence_path.analyze`, which does not call the scope reader. Its four CPU files remain byte-identical in this component. The CPU and graph agents own the new semantic hook and verified execution-pin alignment; updating main alone is not claimed as a CPU deployment.

The transport now retains every safe non-evaluation cache file, including activation, cycles, failed capture/request receipts, pending queues, source holds and all documents/raw/captures. Historical evaluation bytes remain in their immutable original artifact, referenced by run/artifact/digest; the helper does not expand those 49GB or call them new QA. Normal CPU input is a separate 128MiB-bounded, attempt-bound bundle containing literal document/native bytes, original RSS manifest and a separately hashed derived CPU manifest. Duplicate versions remain ambiguous and malformed/missing sources retain their existing downstream outcomes. SEC's referenced native metadata JSON travels with the HTML.

A new demand can depend on an older stored supply source. A narrow handoff callback records the already computed graph's root-connected sources, TARGET attribute/support sources, and relief dependencies by exact version/hash. These old bodies travel as **GRAPH_CONTEXT**, without becoming new RSS IDs or new CPU reading tasks. A genuine development timing-pair regression retains the same rooted candidate as the full state and excludes an unrelated old pair. If required originals cannot fit the bound, the bundle explicitly requests recovery from the exact compact-cache artifact; it cannot quietly turn missing input into zero pairs or normal semantic HOLD.

RSS delivery now uploads both required, attempt-bound delta files before the existing canonical CAS publication. Missing files or upload failure prevent that publication. RSS/acquisition/public/source bundles carry exact run attempts. Historical fixed230/manual diagnostic bindings are unchanged. Acquisition exports only typed public counters with their true units: seed capture outcomes are not relabelled HTTP requests; never-measured counters remain null. Reused private cycle receipts do not count their old acquisitions as new.

| Verification | Result |
|---|---|
| New transport/public/ordering regressions observed before their fixes | Expected failures preserved in local logs |
| Related producer, counters, RSS delivery, queue transport and order-binding checks | **110 passed**, zero failures |
| Preserved FOX-XP/Sonoma source bodies, native hashes, versions and model coordinates through full versus delta input | PASS; consumed development regression, no inference or new accuracy claim |
| New demand + old qualified supply timing candidate, unrelated old-pair exclusion | PASS; synthetic/development functional contract |
| Failed URL/cutover/control-state preservation with no refetch | PASS |
| Independent expanded review | 55 checks passed; no Important/Critical findings; exact attempt-name changes coordinated with CPU/REVIEW consumers |
| Wider regression run before parent preservation mapping | 97 passed; one expected failure in `test_original_frozen_UI_copy_and_evidence_files_are_preserved` for the authorized acquisition workflow change. Root retains exact sealed workflow copies; the golden manifest is unchanged. |

No source was recrawled and no model inference, operating DB write or new Gate run was performed by this component. The original seven-document snapshot's body hashes were checked read-only. No gold, HOLDOUT, Objective Lock, RSS cadence, graph comparison criterion or model revision was changed.

Resource limits are explicit: 4GiB expanded acquisition state, 128MiB total CPU bundle, 128MiB metadata scan, 2GiB disk reserve, 300s restore and 120s packaging. Acquisition still needs its complete source/control working set to preserve the existing graph's inputs: the old measured source set was 2,402,577,107 expanded bytes. The new compact ZIP's actual compressed size is **not yet measured**; no claim is made that acquisition performs no full-cache transport. Normal CPU runs use the small bundle, while exact older partial sources use the consumer's stored small-bundle descriptors.

Next: integrate producer/consumer/REVIEW/public snapshot changes, observe final-SHA CI/Gates, and prove a real new document/window through persistence and dashboard refresh. Local tests and the old source examples do not establish that operating chain, independent accuracy or seven-day stability.

Machine-readable hashes, versions, limits and evidence: [COLLECTION_BODY_HANDOFF.json](COLLECTION_BODY_HANDOFF.json).
