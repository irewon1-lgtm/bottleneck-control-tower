"""Canonical RSS publication must not outrun durable attempt-bound delta input."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_required_attempt_delta_is_uploaded_before_canonical_commit():
    path=ROOT/'.github/workflows/rss-live-check.yml'
    steps=yaml.safe_load(path.read_text())['jobs']['collect']['steps']
    upload=next(i for i,step in enumerate(steps)if step.get('with',{}).get('name','').startswith('rss-live-result'))
    publish=next(i for i,step in enumerate(steps)if step.get('name','').startswith('Publish verified database'))
    assert upload<publish
    assert steps[upload]['with']['name']=='rss-live-result-${{ github.run_attempt }}'
    assert steps[upload]['with']['if-no-files-found']=='error'
    assert any('test -s new-document-manifest.json'in step.get('run','')for step in steps[:upload])


def test_rss_manifest_and_acquisition_download_bind_the_same_attempt():
    producer=(ROOT/'.github/workflows/rss-live-check.yml').read_text()
    receiver=(ROOT/'.github/workflows/precursor-acquisition.yml').read_text()
    assert "'run_id':"in producer and "'run_attempt':"in producer
    assert 'RSS_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt || inputs.rss_run_attempt }}' in receiver
    assert '--name "rss-live-result-$RSS_RUN_ATTEMPT"'in receiver
    assert '--name rss-live-result --dir var/rss-delta'not in receiver

def test_manual_rss_handoff_is_guarded_and_exact():
    text=(ROOT/'.github/workflows/precursor-acquisition.yml').read_text()
    parsed=yaml.safe_load(text)
    triggers=parsed.get('on',parsed.get(True,{}))
    assert 'workflow_run' in triggers and 'workflow_dispatch' in triggers
    assert triggers['workflow_dispatch']['inputs']['rss_run_id']['required'] is True
    assert "github.ref == 'refs/heads/main'" in text
    assert 'gh api "repos/$GH_REPO/actions/runs/$RSS_RUN_ID"' in text
    assert '.head_repository.full_name == $repo' in text
    assert '.run_attempt == $attempt' in text
    assert '.conclusion == "success"' in text
    assert '--name "rss-live-result-$RSS_RUN_ATTEMPT"' in text
    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in text
