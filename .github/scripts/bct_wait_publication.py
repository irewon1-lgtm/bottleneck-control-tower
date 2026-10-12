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
    proof = None
    if path.exists():
        proof = json.loads(path.read_text())
        if not str(proof.get('run_id', '')).isdigit():
            raise ValueError('publication request has invalid execution')
        if proof.get('main_sha') != main:
            history_path = root/'operating-publication-history.json'
            history = json.loads(history_path.read_text()) if history_path.exists() else []
            if proof not in history:
                history.append(proof)
            history_path.write_text(json.dumps(history, indent=2)+'\n')
            proof = None
        # A hash-pinned recovery artifact may carry an uncertain request from
        # the immediately preceding runner.  Adopt that same request rather
        # than emitting a second dispatch; retain both execution identities.
        if proof is not None and proof['run_id'] != os.environ['GITHUB_RUN_ID']:
            proof['resumed_by_run_id'] = os.environ['GITHUB_RUN_ID']
            path.write_text(json.dumps(proof, indent=2)+'\n')
    if proof is None:
        proof = {'run_id': os.environ['GITHUB_RUN_ID'], 'main_sha': main,
                 'requested_at': datetime.now(timezone.utc).isoformat(), 'state': 'REQUESTING'}
        path.write_text(json.dumps(proof, indent=2)+'\n')
        # repository_dispatch is an explicitly supported GITHUB_TOKEN trigger.
        # No push loop, additional credential or paid service is introduced.
        request('POST', '/dispatches', {'event_type': 'bct-operating-publication',
            'client_payload': {'recovery_run_id': proof['run_id']}})
        proof['state'] = 'DISPATCHED'; path.write_text(json.dumps(proof, indent=2)+'\n')
    # REQUESTING means the POST outcome was not recorded.  It may nevertheless
    # have reached GitHub (for example, a successful 204 was decoded as JSON by
    # an older client).  Never dispatch again from that state.  Reconcile the
    # unique fresh external run below and keep waiting, or time out with the
    # exact request checkpoint intact.
    start = datetime.fromisoformat(proof['requested_at'])
    while time.monotonic() < deadline:
        runs = request('GET', '/actions/runs?branch=main&per_page=100')['workflow_runs']
        fresh = [run for run in runs if run['head_sha'] == main
                 and datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')) >= start]
        candidates = [run for run in fresh if run['path'] == '.github/workflows/future-bottleneck.yml'
                      and run['event'] == 'repository_dispatch']
        if candidates:
            selected = min(candidates, key=lambda run: run['id'])
            proof['state'] = 'DISPATCHED'
            proof['candidate_run_id'] = selected['id']
            if selected['status'] == 'completed' and selected['conclusion'] != 'success':
                raise RuntimeError('fresh automatic candidate workflow failed: '+str(selected['id']))
            if selected['status'] == 'completed':
                page_start = proof.get('pages_requested_at', selected['created_at'])
                pages = [run for run in fresh if run['path'] == '.github/workflows/ui-pages.yml'
                         and run['event'] in ('workflow_run', 'repository_dispatch')
                         and run['created_at'] >= page_start]
                if not pages and not proof.get('pages_requested_at'):
                    proof['pages_requested_at'] = datetime.now(timezone.utc).isoformat()
                    proof['pages_state'] = 'REQUESTING'
                    path.write_text(json.dumps(proof, indent=2)+'\n')
                    request('POST', '/dispatches', {'event_type': 'bct-pages-publication',
                        'client_payload': {'recovery_run_id': proof['run_id'],
                                           'candidate_run_id': selected['id']}})
                    proof['pages_state'] = 'DISPATCHED'
                    path.write_text(json.dumps(proof, indent=2)+'\n')
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
