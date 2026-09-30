import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from bct.models import RadarItem
from bct.rss_ai import FIELDS, RSSAIReview, run


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.load((ROOT / '.github/workflows/rss-ai.yml').read_text(), Loader=yaml.BaseLoader)


def test_workflow_is_separate_and_uses_existing_write_lock():
    rss = yaml.load((ROOT / '.github/workflows/rss-live-check.yml').read_text(), Loader=yaml.BaseLoader)
    assert WORKFLOW['concurrency'] == rss['concurrency']
    assert {x['cron'] for x in WORKFLOW['on']['schedule']} == {'20 22 * * *', '20 10 * * *'}
    assert set(WORKFLOW['on']) == {'schedule', 'workflow_dispatch'}
    steps = WORKFLOW['jobs']['annotate']['steps']
    ai = next(s for s in steps if s.get('name', '').startswith('Annotate'))
    assert ai['env']['OPENAI_API_KEY'] == '${{ secrets.OPENAI_API_KEY }}'
    assert sum('OPENAI_API_KEY' in s.get('env', {}) for s in steps) == 1
    publish = steps[-1]['run']
    assert '"$current_sha" != "$BASE_DATA_SHA"' in publish
    assert '--force' not in publish
    assert 'rss_state.py save' in publish
    assert steps[-1]['if'] == "env.AI_PROCESSED != '0'"


def test_batch_limit_error_continuation_and_snapshot_resume(setup, tmp_path):
    settings, sf = setup
    feeds = tmp_path / 'feeds.yaml'
    feeds.write_text('feeds:\n  news: https://news.example.org/feed\n')
    with sf.begin() as db:
        for n in range(25):
            db.add(RadarItem(id=f'{n:02}', source='news.example.org', external_id=str(n),
                title='Steel shortage', url=f'https://news.example.org/{n}', source_type='NEWS'))
    def contents():
        with sqlite3.connect(settings.db_path) as db:
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'rss_ai_reviews'").fetchall()
            return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                    for (name,) in tables}
    before = contents()
    calls = []
    def reviewer(payload, *, model):
        calls.append(payload)
        if len(calls) <= 2:
            raise RuntimeError('private provider failure')
        value = dict.fromkeys(FIELDS, 'UNRESOLVED')
        value.update(SIGNAL_DIRECTION='PRESSURE', SIGNAL_TYPE='SHORTAGE')
        return value
    first = run(settings, feeds, model='test-model', reviewer=reviewer)
    assert (first['processed'], first['success'], first['error'], len(calls)) == (20, 19, 1, 21)
    assert contents() == before
    spec = importlib.util.spec_from_file_location('ai_state', ROOT / '.github/scripts/rss_state.py')
    state = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(state)
    branch = tmp_path / 'branch'
    state.save(settings.db_path, branch, 'ai-1')
    # Simulate the next runner restoring exactly the persisted database.
    sf.kw['bind'].dispose()
    settings.db_path.unlink()
    state.load(branch, settings.db_path)
    assert run(settings, feeds, model='test-model', reviewer=reviewer)['processed'] == 5
    state.save(settings.db_path, branch, 'ai-2')
    assert run(settings, feeds, model='test-model', reviewer=reviewer)['processed'] == 0
    with sf() as db:
        rows = db.scalars(select(RSSAIReview)).all()
        assert len(rows) == 25
        assert sum(r.status == 'ERROR' and r.attempts == 2 for r in rows) == 1
    assert contents() == before
    assert state.validate(branch)['radar_items'] == 25
    assert run(settings, feeds, model='other-model', reviewer=reviewer)['processed'] == 20


def test_workflow_missing_secret_does_not_process(monkeypatch, capsys):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    script = next(s['run'] for s in WORKFLOW['jobs']['annotate']['steps']
                  if s.get('name', '').startswith('Annotate')).split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    with pytest.raises(SystemExit, match='no articles processed'):
        exec(compile(script, '<workflow>', 'exec'), {})
    assert not capsys.readouterr().out


def test_workflow_persists_article_errors_without_logging_key(monkeypatch, tmp_path, capsys):
    import bct.rss_ai
    import bct.config
    key = 'secret-test-do-not-log'
    monkeypatch.setenv('OPENAI_API_KEY', key)
    monkeypatch.setenv('RSS_AI_MODEL', 'test-model')
    env_file = tmp_path / 'env'
    monkeypatch.setenv('GITHUB_ENV', str(env_file))
    monkeypatch.setattr(bct.config, 'load_settings', lambda path: object())
    monkeypatch.setattr(bct.rss_ai, 'run', lambda *args, **kwargs: {
        'processed': 20, 'success': 0, 'error': 20, 'results': [key]})
    script = next(s['run'] for s in WORKFLOW['jobs']['annotate']['steps']
                  if s.get('name', '').startswith('Annotate')).split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    exec(compile(script, '<workflow>', 'exec'), {})
    output = capsys.readouterr().out
    assert json.loads(output) == {'processed': 20, 'success': 0, 'error': 20}
    assert key not in output
    assert env_file.read_text() == 'AI_PROCESSED=20\n'
