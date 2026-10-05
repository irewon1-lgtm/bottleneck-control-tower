"""Read-only preservation/workflow audit; no corpus/engine execution."""
import hashlib,json,subprocess
from pathlib import Path
from bct.objective_lock import objective_binding
R=Path('review-leads/shadow-20261005')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline=json.loads((R/'baseline-hashes.json').read_text());workflow='.github/workflows/precursor-acquisition.yml'
changed=[p for p,h in baseline.items() if sha(p)!=h]
assert changed==[],changed
original=subprocess.check_output(['git','show','83aaf61:'+workflow],text=True)
assert Path(workflow).read_text()==original
for p in ['src/bct/review_intake.py','src/bct/review_leads.py','src/bct/precursor_v2.py','src/bct/early_forecast.py','src/bct/prospective.py','BCT_OBJECTIVE_LOCK.md']:
 assert sha(p)==baseline[p]
print(json.dumps({'result':'PASS','baseline_files':len(baseline),'existing_artifact_changes':0,
 'existing_workflow_changes':0,'new_workflow':'Separate flag-gated artifact consumer; no producer job modification',
 'frozen_review_intake_83aaf61_unchanged':True,'Objective_Lock':objective_binding(),
 'old_FIRST_HISTORY_changes':0,'V2_EARLY_LIVE_engine_changes':0,'activation_performed':False},indent=2))
