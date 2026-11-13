"""Opt-in fair source selection for the unchanged body fetch/save engine.

No source requests, no DB writes, no evidence decisions. Operates solely on
already eligible (source, fingerprint, previous result) tuples produced by the
existing retry, hold and source-version policy. All active RSS rows are still
scanned by the caller; selecting order does not redefine its metrics.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit

VERSION="bct-free-cpu-balanced-input-v1"

def select(pending, *, limit, now, screener, narrow=None,
           recent_fraction=.4, max_host=6):
    if (not 1<=limit<=300 or not 0<=recent_fraction<=1 or
        not 1<=max_host<=100 or now.tzinfo is None):
        raise ValueError("BCT_FAIR_QUEUE_BOUNDS")
    if not isinstance(pending,list):
        pending=list(pending)
    ids=[job[0]["id"] for job in pending]
    if len(set(ids))!=len(ids):
        raise ValueError("BCT_FAIR_QUEUE_DUPLICATE_ID")
    cutoff=now.astimezone(timezone.utc)-timedelta(hours=48)
    scores=[]
    for job in pending:
        row=job[0]
        metadata=str(row.get("title") or "")+"\n"+str(row.get("snippet") or "")
        try:
            discovery=screener(metadata).get("discovery_paths",[])
        except (ValueError,TypeError,KeyError):
            discovery=[]
        roles=set(discovery)&{"DEMAND","SUPPLY","RELIEF"}
        try:
            code=bool(narrow(row.get("title") or "",row.get("snippet") or "")) if narrow else False
        except (ValueError,TypeError,KeyError):
            code=False
        prio=(0 if len(roles)>=2 and code else
              1 if code or len(roles)>=2 else
              2 if roles else 3)
        try:
            collected=datetime.fromisoformat(str(row.get("collected_at") or "").replace("Z","+00:00"))
            recent=bool(collected.tzinfo and cutoff<=collected.astimezone(timezone.utc)<=now)
        except (ValueError,TypeError):
            recent=False
        host=(urlsplit(row["url"]).hostname or "").lower()
        if not host:raise ValueError("BCT_FAIR_QUEUE_INVALID_SOURCE_HOST")
        scores.append((prio,recent,host,str(row.get("collected_at") or ""),str(row["id"]),job))
    scores.sort(key=lambda v:(v[0],v[3],v[4]))
    recent=[v for v in scores if v[1]]
    older=[v for v in scores if not v[1]]
    chosen=[];selected_ids=set();host_counts=Counter()
    def add(group,ceiling):
        for x in group:
            if len(chosen)>=ceiling:break
            key=x[4]
            if key in selected_ids or host_counts[x[2]]>=max_host:continue
            selected_ids.add(key);host_counts[x[2]]+=1;chosen.append(x)
    add(recent,round(limit*recent_fraction))
    add(older,limit)
    add(recent,limit)
    result=[x[-1] for x in chosen]
    if len(result)>limit or len({x[0]["id"] for x in result})!=len(result):
        raise ValueError("BCT_FAIR_QUEUE_BOUND_VIOLATION")
    return result,{
        "fair_queue_version":VERSION,
        "fair_queue_input_due":len(pending),
        "fair_queue_selected":len(result),
        "fair_queue_recent":sum(x[1] for x in chosen),
        "fair_queue_older":sum(not x[1] for x in chosen),
        "fair_queue_hosts":len(host_counts),
        "fair_queue_max_host":max(host_counts.values(),default=0),
        "fair_queue_discarded_due_to_host_and_budget":len(pending)-len(result),
        "fair_queue_is_not_evidence_promotion":True
    }
