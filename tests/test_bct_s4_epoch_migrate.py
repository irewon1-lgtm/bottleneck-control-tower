"""BCT V4 CPU private epoch migration safety + immutable source-free links."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

p=Path(__file__).resolve().parents[1]/"tools/bct_s4_epoch_migrate.py"
spec=importlib.util.spec_from_file_location("s4_epoch",p)
s4=importlib.util.module_from_spec(spec);spec.loader.exec_module(s4)


def fixtures():
    c={"format":"bct-s4-safe-private-storage-epoch-preflight-v1",
       "status":"PASS_READONLY_GATES_FOR_REVIEWED_STORAGE_EPOCH_DESIGN",
       "anchored_previous_ack":s4.OLD_ACK,
       "private_history_cap_bytes":s4.CAP,
       "durably_persisted_windows":35,
       "authenticated_unpublished_windows":24,
       "verified_read_windows":59,
       "verified_unread_windows":181,
       "sealed_unpublished_sqlite_sha256":s4.NEW_DB,
       "automatic_S1_S2_S3_or_LIVE_promotions":0,
       "new_remote_ref_writes":0,
       "private_archived_ref":s4.ARCHIVE_REF,
       "private_old_ref":s4.OLD_REF,
       "additional_bounded_CPU_batches_required":8}
    c["plan_sha256"]=s4.digest(s4.encoded(c))
    proof={"status":"SEALED_VERIFIED_UNPUBLISHED_DO_NOT_COUNT_AS_DURABLE",
           "authenticated_sealed_sqlite_sha256":s4.NEW_DB,
           "last_durable_private_commit":s4.OLD_ACK,
           "last_durable_run":s4.LAST_ACK_RUN,
           "unpublished_run":s4.SOURCE_RUN,
           "target_original_sources":11,
           "durable_promotion":False,"private_ref_writes":0,"new_model_calls":0,
           "counts":{"total":240,"prior_success":35,"sealed_success":59,
                     "sealed_pending":181,"unpublished_added":24},
           "per_source":[{"document_id":f"target-{i}"} for i in range(11)]}
    previous={"generation":{"private_commit":s4.OLD_ACK,
                            "checkpoint_commit":s4.OLD_CHECKPOINT,
                            "sqlite_sha256":s4.OLD_SQLITE,
                            "lineage_root":s4.OLD_ROOT,
                            "ack_sequence":s4.OLD_ACK_SEQUENCE,
                            "producer_run_id":s4.LAST_ACK_RUN}}
    return c,proof,previous


def test_epoch_disjoins_old_history_and_preserves_lineage():
    c,proof,old=fixtures()
    assert s4.secure_source_free_preflight(c,proof) is True
    link=s4.link(c,old)
    assert link["new_epoch_ref"]!=link["old_cpu_ref"]
    assert link["old_ack_sequence"]==68
    assert link["new_epoch_independent_root_required"] is True
    assert link["old_ref_modified"] is False
    assert link["public_schedule_activated"] is False


@pytest.mark.parametrize("change",[
    lambda c,p,o:c.update(anchored_previous_ack="0"*40),
    lambda c,p,o:c.update(private_history_cap_bytes=128*1024**2),
    lambda c,p,o:c.update(verified_read_windows=240),
    lambda c,p,o:c.update(new_remote_ref_writes=1),
    lambda c,p,o:p.update(authenticated_sealed_sqlite_sha256="0"*64),
    lambda c,p,o:p.update(durable_promotion=True),
    lambda c,p,o:p.update(private_ref_writes=1),
    lambda c,p,o:p["counts"].update(unpublished_added=25),
    lambda c,p,o:p.update(per_source=[]),
])
def test_mismatched_preflight_or_sealed_fails_closed(change):
    c,proof,old=fixtures()
    change(c,proof,old)
    with pytest.raises(ValueError):
        s4.secure_source_free_preflight(c,proof)


@pytest.mark.parametrize("field",["private_commit","checkpoint_commit",
                                  "sqlite_sha256","lineage_root",
                                  "ack_sequence","producer_run_id"])
def test_old_ack_and_old_root_must_not_change(field):
    c,p,old=fixtures()
    old["generation"][field]="bad"
    with pytest.raises(ValueError,match="OLD_PUBLIC_ACK_LINEAGE"):
        s4.link(c,old)


def test_cap_on_independent_new_git_root_only():
    def small(*args,stdin=None):
        if args[:2]==("rev-list","--objects"):
            return "a"*40+"\n"+"b"*40+" checkpoint.json\n"
        if args[0]=="cat-file":
            return "a"*40+" commit 199\n"+"b"*40+" blob 4100000\n"
        raise AssertionError(args)
    assert s4.history_measure(small,"a"*40)==4100199
    def too_big(*args,stdin=None):
        if args[0]=="cat-file":
            return "a"*40+" commit 200\n"+"b"*40+" blob "+str(s4.CAP)+"\n"
        return "a"*40+"\n"+"b"*40+" checkpoint.json\n"
    with pytest.raises(ValueError,match="HISTORY_CAP_EXCEEDED"):
        s4.history_measure(too_big,"a"*40)


def test_no_private_repos_or_branches_may_be_implicitly_overwritten():
    assert s4.PRIVATE_REPO=="irewon1-lgtm/bct-v4-private-state"
    assert s4.OLD_REF!=s4.EPOCH_REF
    assert s4.ARCHIVE_REF!=s4.EPOCH_REF
    assert "force" not in s4.EPOCH_REF
    source=p.read_text()
    assert 'git("push","origin",ack+":"+EPOCH_REF)' in source
    assert "git(\"rev-list\",\"--parents\",\"-n\",\"1\",root)" in source
    assert "EPOCH_NEW_PRIVATE_REF_ALREADY_EXISTS_NEVER_OVERWRITE" in source
