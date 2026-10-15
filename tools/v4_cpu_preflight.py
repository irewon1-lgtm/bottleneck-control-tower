#!/usr/bin/env python3
"""Development preflight only. Does not enable a CPU schedule or register LIVE."""
import argparse
import json
from pathlib import Path

from bct.v4 import cpu_operations as op


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['guard','bootstrap-model','probe-model','checkpoint','restore','observe'])
    p.add_argument('--root',type=Path,default=Path('var/v4/cpu-operations/ledger'))
    p.add_argument('--runtime',type=Path,default=Path('.v4-cpu-runtime'))
    p.add_argument('--manifest',type=Path,default=Path('docs/v4/cpu-automation/preflight/model-manifest.json'))
    p.add_argument('--checkpoint',type=Path,default=Path('var/v4/cpu-operations/checkpoint'))
    p.add_argument('--output',type=Path)
    p.add_argument('--load-health-probe',action='store_true')
    p.add_argument('--execute-cpu',action='store_true')
    a=p.parse_args()
    if a.action=='guard': result=op.github_guard()
    elif a.action=='bootstrap-model':
        # The hosted job must prove free conditions before any cold setup.
        op.github_guard();result=op.bootstrap_model(a.runtime,json.loads(a.manifest.read_text()))
    elif a.action=='probe-model': result=op.runtime_probe(a.runtime,json.loads(a.manifest.read_text()),load=a.load_health_probe)
    elif a.action=='restore': result=op.restore(a.checkpoint,a.root)
    else:
        if a.action=='checkpoint':
            from bct.v4.store import Ledger
            l=Ledger(a.root)
        else:
            from bct.v4.cpu_automation import open_queue
            l=open_queue(a.root)
        try:
            if a.action=='checkpoint': result=op.checkpoint(l,a.checkpoint)
            else:
                from bct.v4.adapters import CPUExtractor
                result=op.observe(l,trigger='DEVELOPMENT_PREFLIGHT_NOT_SCHEDULED',execute=a.execute_cpu,extractor=CPUExtractor(a.runtime) if a.execute_cpu else None)
        finally:l.close()
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x')as f:f.write(text)
    else:print(text)
    # Compact, durable job-log evidence; no source text or credentials.
    if a.output: print(json.dumps({'action':a.action,'output':str(a.output),'result':result},ensure_ascii=False))


if __name__=='__main__':main()
