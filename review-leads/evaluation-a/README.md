# A preparation

PREREGISTRATION_DRAFT.md is authoritative and unapproved. config.json is checked against it; manifest.json stores its full-file hash outside the document. Templates and schemas do not activate anything.

One live read-only collection was executed:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python tools/review_evaluation_a.py --output review-leads/evaluation-a/current-observation.json

It must not overwrite that report. To reproduce observation later, use a new report filename, not a rerun of document processing. A final helper revision adds metric wrappers and source-hash validation after collection; current snapshot remains the initial evidence, not an exactly byte-frozen collector experiment. No claims about actual semantic performance are made.

Boundary + existing related regression tests:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_review_evaluation_a.py tests/test_review_shadow.py tests/test_review_intake.py tests/test_review_leads.py tests/test_early_forecast.py tests/test_prospective.py -q

No original ablation is run. A tests use synthetic fixtures, not the four real regression examples. Sidecar helpers are unconnected to production; append_sidecar accepts only evaluation-a namespace, rejects operational activation roots, never updates existing records. validate_state_ref accepts only refs/heads/review-lead-evaluation-state; no Git state writer in A.

observer-workflow.yml.template remains outside .github/workflows. Proposed twice-daily cadence is unapproved. Uses read-only permissions and no upstream/PR-controlled checkout, artifact code execution, operational state push or collection stop. Future evaluation-state writer/CAS/permissions need separate approval before operation; reserved branch is not created here.
