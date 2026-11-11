"""Public data writes stay on main and use the existing canonical writer lock."""
from pathlib import Path
import yaml


def test_main_only_public_cas_and_verified_code_preserve_existing_pages_boundary():
    root = Path(__file__).resolve().parents[1]
    flow = yaml.safe_load((root / '.github/workflows/ui-pages.yml').read_text())
    jobs = flow['jobs']
    assert "github.ref == 'refs/heads/main'" in jobs['source']['if']
    assert 'status=success' in jobs['source']['steps'][0]['run']
    assert flow['permissions'] == {'contents': 'read'}
    assert jobs['sync-public']['permissions'] == {'contents': 'write', 'actions': 'read'}
    assert jobs['sync-public']['concurrency'] == {'group': 'rss-canonical-data', 'cancel-in-progress': False}
    assert jobs['sync-public']['needs'] == 'source'
    cpu = yaml.safe_load((root / '.github/workflows/v4-cpu-private-research.yml').read_text())
    assert jobs['sync-public']['steps'][0]['with']['ref'] == cpu['env']['CPU_CODE_SHA']
    assert jobs['sync-public']['steps'][0]['with']['persist-credentials'] is False
    for job in ('build', 'deploy'):
        assert jobs[job]['steps'][0]['with']['ref'] == '${{ needs.source.outputs.code_sha }}'
        assert jobs[job]['steps'][0]['with']['persist-credentials'] is False
    text = (root / '.github/workflows/ui-pages.yml').read_text()
    assert 'BCT_V4_PRIVATE_STATE_TOKEN' not in text and 'BCT_V4_STATE_PASSPHRASE' not in text
    assert 'refs/heads/data' not in text  # data pushes never recursively trigger Pages
    assert '--public-input var/v4/pages-input' in text
    assert 'guard --manifest-env BCT_PAGES_MANIFEST' in text
    assert jobs['deploy']['permissions'] == {'contents': 'read', 'pages': 'write', 'id-token': 'write'}
