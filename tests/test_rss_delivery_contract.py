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
    assert 'RSS_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt }}'in receiver
    assert '--name "rss-live-result-$RSS_RUN_ATTEMPT"'in receiver
    assert '--name rss-live-result --dir var/rss-delta'not in receiver
