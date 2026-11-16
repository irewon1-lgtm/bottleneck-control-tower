"""Private-credential-only epoch bridge for one authenticated manual CPU run.

Runs in bridge job, never in research. The only outbound file is an AES256-GPG
sealed checkpoint and a source-free exact private ref proof. No original text.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from bct.v4 import private_state as state,cpu_operations as op,cpu_resume as resume

PRIVATE_URL=state.PRIVATE_URL
EXPECTED_OLD="8493ce906aea1c4ef14693873ba016e708d30245"
EXPECTED_ROOT="1fd5c95a7cafdd5b1fd7d87acf07f07950f3f1e2"
EXPECTED_SEED="b330cdf20ebfe479bedcbe929dfbfe65b2df48639d04dfdfa7d6250082f9a572"
ARCHIVE_REF="refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
LEGACY_REF="refs/heads/codex/bct-v4-cpu-research-state"
WORKFLOW="bct-s4-epoch-cpu-manual.yml"
MAX_BYTES=64*1024*1024

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify_scope():
    if (op.STATE_REF!="refs/heads/codex/bct-v4-cpu-research-epoch-20261116"
            or os.environ.get("GITHUB_REPOSITORY")!="irewon1-lgtm/bottleneck-control-tower"
            or os.environ.get("GITHUB_REF")!="refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
            or os.environ.get("GITHUB_JOB")!="bridge"
            or os.environ.get("GITHUB_WORKFLOW_REF","").split("@")[0].split("/")[-1]!=WORKFLOW):
        raise ValueError("EPOCH_BRIDGE_NOT_IN_APPROVED_MANUAL_JOB")

def bounded_epoch_ref_proof(repo, git, ack):
    refs=git("ls-remote","origin",LEGACY_REF,ARCHIVE_REF,op.STATE_REF)
    matches={line.split()[1]:line.split()[0] for line in refs.splitlines() if len(line.split())==2}
    if (matches.get(LEGACY_REF)!=EXPECTED_OLD or matches.get(ARCHIVE_REF)!=EXPECTED_OLD
            or matches.get(op.STATE_REF)!=ack):
        raise ValueError("EPOCH_ARCHIVED_REF_OR_CURRENT_HEAD_CHANGED")
    parents=git("rev-list","--parents","-n","1",ack).split()
    if len(parents)!=2:
        raise ValueError("EPOCH_CURRENT_ACK_NOT_CHILD")
    roots=git("rev-list","--max-parents=0",ack).split()
    if roots!=[EXPECTED_ROOT]:
        raise ValueError("EPOCH_INDEPENDENT_ROOT_NOT_VERIFIED")
    count=int(git("rev-list","--first-parent","--count",ack))
    if count<2 or count%2:
        raise ValueError("EPOCH_ACK_SEQUENCE_INVALID")
    objects=git("rev-list","--objects",ack).splitlines()
    ids=[x.split()[0] for x in objects]
    if len(set(ids))!=len(ids) or not ids:
        raise ValueError("EPOCH_GIT_OBJECT_DUPLICATION")
    raw=git("cat-file","--batch-check=%(objectname) %(objecttype) %(objectsize)",
            stdin="\n".join(ids)+"\n")
    sizes=[int(x.split()[-1]) for x in raw.splitlines() if len(x.split())==3]
    if len(sizes)!=len(ids) or sum(sizes)>MAX_BYTES:
        raise ValueError("EPOCH_64MIB_HISTORY_BOUND")
    return parents[1],count,sum(sizes)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    verify_scope()
    token=os.environ.get("BCT_V4_PRIVATE_STATE_TOKEN","")
    passphrase=os.environ.get("BCT_V4_STATE_PASSPHRASE","")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}",token) or not passphrase:
        raise ValueError("EPOCH_SECRETS_NOT_PRESENT")
    auth=base64.b64encode(("x-access-token:"+token).encode()).decode()
    env={**os.environ,"GIT_CONFIG_COUNT":"2",
        "GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+auth,
        "GIT_CONFIG_KEY_1":"credential.helper","GIT_CONFIG_VALUE_1":"",
        "GIT_TERMINAL_PROMPT":"0"}
    with tempfile.TemporaryDirectory(prefix="s4-epoch-bridge-") as t:
        root=Path(t);repo=root/"repo";repo.mkdir()
        def git(*args,stdin=None):
            out=subprocess.run(["git","-C",str(repo),*args],input=stdin,
                capture_output=True,text=True,env=env,timeout=65)
            if out.returncode:raise ValueError("EPOCH_PRIVATE_GIT_READ_DENIED_OR_CHANGED")
            return out.stdout.strip()
        def bytes_at(ack,name):
            proc=subprocess.run(["git","-C",str(repo),"show",ack+":"+name],
                 capture_output=True,env=env,timeout=65)
            if proc.returncode:raise ValueError("EPOCH_PRIVATE_CHECKPOINT_BLOB_MISSING")
            return proc.stdout
        git("init","-q");git("remote","add","origin",PRIVATE_URL)
        heads=git("ls-remote","origin",LEGACY_REF,ARCHIVE_REF,op.STATE_REF)
        refs={row.split()[1]:row.split()[0] for row in heads.splitlines()
              if len(row.split())==2}
        ack=refs.get(op.STATE_REF)
        if not ack or not re.fullmatch("[a-f0-9]{40}",ack):
            raise ValueError("EPOCH_PRIVATE_ACK_NOT_FOUND")
        # No shallow clone or older-reference reflog needed. Read only the new epoch.
        git("fetch","--no-tags","origin",op.STATE_REF)
        if git("rev-parse","FETCH_HEAD")!=ack or git("rev-parse","--is-shallow-repository")!="false":
            raise ValueError("EPOCH_PRIVATE_FETCH_OR_DEPTH_INVALID")
        checkpoint_commit,count,bytes_used=bounded_epoch_ref_proof(repo,git,ack)
        link=json.loads(bytes_at(ack,"epoch-link.json"))
        if (link.get("format")!="bct-v4-cpu-private-epoch-link-v1"
                or link.get("old_ack_commit")!=EXPECTED_OLD
                or link.get("new_epoch_ref")!=op.STATE_REF
                or link.get("immutable_archive_ref")!=ARCHIVE_REF
                or link.get("old_cpu_ref")!=LEGACY_REF
                or link.get("seed_sqlite_sha256")!=EXPECTED_SEED
                or link.get("old_ack_sequence")!=68):
            raise ValueError("EPOCH_CROSS_GENERATION_LINK_NOT_VERIFIED")
        receipt=json.loads(bytes_at(ack,"private-persistence.json"))
        proof=json.loads(bytes_at(ack,"checkpoint.json"))
        if (receipt.get("version")!="bct-private-persistence-1"
                or receipt.get("checkpoint_commit")!=checkpoint_commit
                or receipt.get("sqlite_sha256")!=proof.get("sqlite_sha256")
                or receipt.get("LIVE_registration") is not False
                or receipt.get("API_calls")!=0):
            raise ValueError("EPOCH_PRIVATE_ACK_NOT_LINKED_TO_CHECKPOINT")
        checkpoint=root/"checkpoint";checkpoint.mkdir()
        (checkpoint/"checkpoint.json").write_bytes(bytes_at(ack,"checkpoint.json"))
        (checkpoint/"checkpoint.sqlite3.gz").write_bytes(bytes_at(ack,"checkpoint.sqlite3.gz"))
        restored=op.restore(checkpoint,root/"restored")
        if restored.get("sqlite_sha256")!=receipt["sqlite_sha256"] or restored.get("tables")!=8:
            raise ValueError("EPOCH_PRIVATE_DB_RESTORE_FAILED")
        ledger=resume.Ledger(root/"restored")
        try:
            resume.audit(ledger)
            if any(ledger.db.execute("SELECT count(*) FROM "+table).fetchone()[0]
                   for table in ("firsts","blobs","documents","captures","readings","runs")):
                raise ValueError("EPOCH_SOURCE_SEPARATED_TABLES_NOT_EMPTY")
        finally:ledger.close()
        # Public artifact will not contain unencrypted derived CPU data.
        a.out.mkdir(parents=True,exist_ok=False)
        dest=a.out/"state.gpg"
        state.seal(checkpoint,dest,passphrase,ack)
        receipt_out={"format":"bct-s4-epoch-bridge-proof-v1",
             "ref":op.STATE_REF,"old_ack":EXPECTED_OLD,"epoch_root":EXPECTED_ROOT,
             "private_ack":ack,"sqlite_sha256":receipt["sqlite_sha256"],
             "epoch_link_verified":True,"archive_verified":True,
             "epoch_commit_count":count,"epoch_history_bytes":bytes_used,
             "producer_run_id":int(os.environ["GITHUB_RUN_ID"]),
             "producer_attempt":int(os.environ["GITHUB_RUN_ATTEMPT"]),
             "last_publisher_run":receipt["publisher_run_id"],
             "encrypted_sha256":sha(dest.read_bytes()),"new_model_calls":0}
        (a.out/"bridge-proof.json").write_text(json.dumps(receipt_out,sort_keys=True)+"\n")
        print("BCT_S4_EPOCH_BRIDGE="+json.dumps({
           k:receipt_out[k] for k in ("private_ack","epoch_commit_count",
             "epoch_history_bytes","producer_run_id","new_model_calls")},sort_keys=True))

if __name__=="__main__":
    main()
