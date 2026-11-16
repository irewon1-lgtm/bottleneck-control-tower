"""Isolated CPU epoch pin never reads/writes historical state ref."""
from bct.v4 import cpu_operations as op,private_state as p

def test_writer_uses_only_new_parentless_epoch_ref():
    assert op.STATE_REF=="refs/heads/codex/bct-v4-cpu-research-epoch-20261116"
    assert op.STATE_HISTORY_LIMIT==64*1024**2
    assert p.PRIVATE_REPO=="irewon1-lgtm/bct-v4-private-state"

def test_archived_cpu_ref_is_not_current_writer():
    assert op.STATE_REF!="refs/heads/codex/bct-v4-cpu-research-state"
    assert op.STATE_REF!="refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
    assert p.PRIVATE_URL.endswith("/bct-v4-private-state.git")
