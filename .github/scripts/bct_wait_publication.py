"""Request one fresh automatic publication; never retry an unchanged failure."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from bct_release_guard import verify_release


def dispatch_and_wait(root, transport, *, deadline):
    request = transport.requester
    main = request('GET', '/git/ref/heads/main')['object']['sha']
    raw, _ = transport._root('config/bct-operating-release.json', main)
    verify_release(request, json.loads(raw), Path('.'))
    path = root/'operating-publication-request.json'
    if path.exists():
        proof = json.loads(path.read_text())
        if proof['run_id'] != os.environ['GITHUB_RUN_ID'] or proof['main_sha'] != main:
            raise ValueError('publication request belongs to a different execution or main code')
    else:
        proof = {'run_id': os.environ['GITHUB_RUN_ID'], 'main_sha': main,
                 'requested_at': datetime.now(timezone.utc).isoformat(), 'state': 'REQUESTING'}
        path.write_text(json.dumps(proof, indent=2)+'\n')
        # repository_dispatch is an explicitly supported GITHUB_TOKEN trigger.
        # No push loop, additional credential or paid service is introduced.
        request('POST', '/dispatches', {'event_type': 'bct-operating-publication',
            'client_payload': {'recovery_run_id': proof['run_id']}})
        proof['state'] = 'DISPATCHED'; path.write_text(json.dumps(proof, indent=2)+'\n')
    if proof['state'] == 'REQUESTING':
        raise RuntimeError('publication dispatch outcome uncertain; verify external run before resuming')
    start = datetime.fromisoformat(proof['requested_at'])
    while time.monotonic() < deadline:
        runs = request('GET', '/actions/runs?branch=main&per_page=100')['workflow_runs']
        fresh = [run for run in runs if run['head_sha'] == main
                 and datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')) >= start]
        candidates = [run for run in fresh if run['path'] == '.github/workflows/future-bottleneck.yml'
                      and run['event'] == 'repository_dispatch']
        if candidates:
            selected = min(candidates, key=lambda run: run['id'])
            proof['candidate_run_id'] = selected['id']
            if selected['status'] == 'completed' and selected['conclusion'] != 'success':
                raise RuntimeError('fresh automatic candidate workflow failed: '+str(selected['id']))
            if selected['status'] == 'completed':
                pages = [run for run in fresh if run['path'] == '.github/workflows/ui-pages.yml'
                         and run['event'] == 'workflow_run'
                         and run['created_at'] >= selected['created_at']]
                if pages:
                    page = max(pages, key=lambda run: run['id'])
                    proof['pages_run_id'] = page['id']
                    if page['status'] == 'completed' and page['conclusion'] != 'success':
                        raise RuntimeError('fresh Pages workflow failed: '+str(page['id']))
                    if page['status'] == 'completed':
                        proof['state'] = 'COMPLETED'
                        path.write_text(json.dumps(proof, indent=2)+'\n')
                        return selected['id'], page['id']
        path.write_text(json.dumps(proof, indent=2)+'\n')
        time.sleep(15)
    raise TimeoutError('publication deadline; keep exact request and external run IDs, no repeat dispatch')
