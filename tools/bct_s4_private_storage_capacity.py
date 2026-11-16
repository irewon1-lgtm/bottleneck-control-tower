"""Read-only exact Git-object accounting for the private V4 CPU state ref.

A Git history-size cap counts every unique blob/commit/tree in ancestry,
not the size of the latest zipped SQLite or current repository disk usage.
No remote refs may be written, moved or deleted by this audit.
"""
import argparse
import base64
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

PRIVATE_REPO="https://github.com/irewon1-lgtm/bct-v4-private-state.git"
CURRENT_REF="refs/heads/codex/bct-v4-cpu-research-state"
ARCHIVE_REF="refs/heads/archive/bct-v4-cpu-pre-64m-20261116"
EXPECTED_HEAD="8493ce906aea1c4ef14693873ba016e708d30245"
CAP=64*1024*1024


def parse_object_sizes(raw, expected):
    lines=raw.splitlines()
    seen=set()
    sizes=Counter()
    counts=Counter()
    for line in lines:
        parts=line.split()
        if (len(parts)!=3 or not re.fullmatch(r"[a-f0-9]{40}",parts[0])
                or parts[1] not in {"blob","commit","tree","tag"}
                or not parts[2].isdigit()
                or parts[0] in seen):
            raise ValueError("S4_GIT_OBJECT_SIZE_REPORT_NOT_VALID")
        seen.add(parts[0])
        counts[parts[1]]+=1
        sizes[parts[1]]+=int(parts[2])
    if len(seen)!=expected or expected<2:
        raise ValueError("S4_GIT_OBJECT_CARDINALITY_MISMATCH")
    return {"objects":dict(counts),"type_bytes":dict(sizes),
            "history_unique_object_bytes":sum(sizes.values())}


def audit():
    token=os.environ.get("BCT_V4_PRIVATE_STATE_TOKEN") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}",token):
        raise ValueError("S4_PRIVATE_TOKEN_MISSING_OR_INVALID")
    auth=base64.b64encode(("x-access-token:"+token).encode()).decode()
    env={**os.environ,
         "GIT_CONFIG_COUNT":"2",
         "GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader",
         "GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+auth,
         "GIT_CONFIG_KEY_1":"credential.helper",
         "GIT_CONFIG_VALUE_1":"",
         "GIT_TERMINAL_PROMPT":"0"}
    with tempfile.TemporaryDirectory(prefix="bct-s4-ro-private-history-") as t:
        folder=Path(t)/"repo"
        def git(*args,stdin=None):
            cp=subprocess.run(["git","-C",str(folder),*args],env=env,
                              input=stdin,text=True,capture_output=True,timeout=120)
            if cp.returncode:
                # Only classify the error. The full remote stderr may contain
                # sensitive URL/credential detail and must never be logged.
                error=cp.stderr.lower()
                category=("REF_NOT_ADVERTISED" if ("couldn't find remote ref" in error or "not our ref" in error)
                          else "AUTH_REJECTED" if ("authentication failed" in error or "401" in error or "403" in error)
                          else "REPOSITORY_NOT_VISIBLE" if "repository not found" in error
                          else "PACK_OR_TRANSPORT" if ("fetch-pack" in error or "early eof" in error or "rpc failed" in error)
                          else "UNKNOWN")
                raise ValueError("S4_PRIVATE_GIT_READ_COMMAND_FAILED_"+category)
            return cp.stdout.strip()
        folder.mkdir()
        git("init","-q")
        git("remote","add","origin",PRIVATE_REPO)
        # Separate authentication/ref visibility from object transport, so
        # an object pack failure cannot be mistaken for a missing archive.
        references=git("ls-remote","origin",CURRENT_REF,ARCHIVE_REF).splitlines()
        advertised={row.split()[1]:row.split()[0] for row in references if len(row.split())==2}
        if advertised.get(CURRENT_REF)!=EXPECTED_HEAD or advertised.get(ARCHIVE_REF)!=EXPECTED_HEAD:
            raise ValueError("S4_PRIVATE_REF_VISIBILITY_OR_HEAD_CHANGED")
        try:
            git("fetch","--no-tags","origin",
                "+"+CURRENT_REF+":refs/remotes/origin/cpu-state")
        except ValueError as exc:
            raise ValueError("S4_PRIVATE_FETCH_ACTIVE_"+str(exc)) from None
        # Both refs were independently attested via authenticated ls-remote,
        # and point to identical immutable commits. Fetching the object graph
        # once suffices; fetching the same remote head a second time is not
        # part of the history byte-count contract.
        if git("rev-parse","--is-shallow-repository")!="false":
            raise ValueError("S4_PRIVATE_HISTORY_SHALLOW_NOT_EXACT")
        current=git("rev-parse","refs/remotes/origin/cpu-state")
        archived=advertised[ARCHIVE_REF]
        if current!=EXPECTED_HEAD or archived!=EXPECTED_HEAD:
            raise ValueError("S4_CURRENT_OR_ARCHIVED_REF_CHANGED")
        objects=git("rev-list","--objects",current)
        ids=[row.split()[0] for row in objects.splitlines()]
        if not ids or len(set(ids))!=len(ids):
            raise ValueError("S4_PRIVATE_GIT_OBJECTS_NOT_UNIQUE")
        rows=git("cat-file","--batch-check=%(objectname) %(objecttype) %(objectsize)",
                 stdin="\n".join(ids)+"\n")
        data=parse_object_sizes(rows,len(ids))
        commit_count=int(git("rev-list","--count",current))
        result={"format":"bct-s4-private-history-pressure-v1",
                "status":"PASS_READONLY_PRIVATE_HISTORY_MEASURED",
                "cpu_ref":CURRENT_REF,"archive_ref":ARCHIVE_REF,
                "latest_confirmed_private_ack":current,
                "archive_fully_anchors_current_head":True,
                "history_unique_object_bytes":data["history_unique_object_bytes"],
                "history_limit_bytes":CAP,
                "headroom_bytes":CAP-data["history_unique_object_bytes"],
                "history_commits":commit_count,
                "object_count":len(ids),"git_object_counts":data["objects"],
                "git_object_bytes":data["type_bytes"],
                "unpublished_cpu_checkpoint_durable":False,
                "user_data_or_secrets_in_output":False,
                "private_ref_writes":0,
                "public_ref_writes":0,
                "recommended_next_action":"STORAGE_GENERATION_ROLLOVER_WITH_ARCHIVED_LINEAGE_PROOF"}
        return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError("S4_STORAGE_PRESSURE_OUTPUT_EXISTS")
    result=audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("BCT_S4_PRIVATE_STORAGE_HISTORY_JSON="+json.dumps({
        "status":result["status"],
        "used_bytes":result["history_unique_object_bytes"],
        "headroom_bytes":result["headroom_bytes"],
        "limit_bytes":result["history_limit_bytes"],
        "archive_proved":result["archive_fully_anchors_current_head"],
        "ref_writes":0},sort_keys=True))


if __name__=="__main__":
    main()
