import json

from sqlalchemy import func, select

from bct.collectors.rss.cli import main
from bct.collectors.rss.collector import RSSCollector, parse_feed
from bct.models import AuditLog, CollectorRun, RadarItem


def feed(*, changed=False):
    return ('<rss version="2.0"><channel><title>News</title>' + ''.join(
        f'<item><title>News {n}{" revised" if changed and n == 1 else ""}</title>'
        f'<link>https://example.org/news/{n}</link>'
        '<pubDate>Tue, 29 Sep 2026 12:00:00 GMT</pubDate>'
        f'<description>Summary {n}</description></item>' for n in range(1, 6)) +
        '</channel></rss>').encode()


class FakeTransport:
    def __init__(self, payload=None):
        self.payload = payload if payload is not None else feed()

    def get(self, url):
        return self.payload


def count(sf):
    with sf() as db:
        return db.scalar(select(func.count()).select_from(RadarItem))


def test_rss_repeat_update_and_audit(setup):
    settings, sf = setup
    collector = RSSCollector(settings, FakeTransport())
    url = 'https://example.org/feed.xml'
    runs = [collector.run(url, f'repeat-{n}', limit=5) for n in range(3)]
    assert [(r.saved, r.duplicates, r.status) for r in runs] == [
        (5, 0, 'succeeded'), (0, 5, 'succeeded'), (0, 5, 'succeeded')]
    assert count(sf) == 5
    changed = RSSCollector(settings, FakeTransport(feed(changed=True))).run(url, 'changed', limit=5)
    assert (changed.updated, changed.duplicates, count(sf)) == (1, 4, 5)
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.event == 'radar.updated')) == 1


def test_malformed_feed_preserves_rows_and_retries(setup):
    settings, sf = setup
    url = 'https://example.org/feed.xml'
    assert RSSCollector(settings, FakeTransport()).run(url, 'first').saved == 5
    bad = RSSCollector(settings, FakeTransport(b'<html>Not a feed</html>')).run(url, 'retry')
    assert bad.status == 'failed' and count(sf) == 5
    good = RSSCollector(settings, FakeTransport()).run(url, 'retry')
    assert good.status == 'succeeded' and good.duplicates == 5
    with sf() as db:
        row = db.get(CollectorRun, bad.run_id)
        assert row.attempts == 2 and row.status == 'succeeded'


def test_one_failed_feed_does_not_stop_other_feed(setup, tmp_path, monkeypatch, capsys):
    settings, sf = setup
    config = tmp_path / 'config.yaml'
    config.write_text(f'storage_root: {settings.root}\n')
    feeds = tmp_path / 'rss_feeds.yaml'
    feeds.write_text('feeds:\n  broken: https://example.org/bad.xml\n'
                     '  working: https://example.org/good.xml\n')

    class OneFailure(FakeTransport):
        def get(self, url):
            if url.endswith('bad.xml'):
                raise TimeoutError('simulated timeout')
            return feed()

    monkeypatch.setattr('bct.collectors.rss.cli.RSSTransport', OneFailure)
    args = ['--config', str(config), '--feeds', str(feeds), '--limit', '5']
    assert main(args + ['--run-key', 'first']) == 0
    results = json.loads(capsys.readouterr().out)
    assert [(r['feed'], r['status'], r['saved']) for r in results] == [
        ('broken', 'failed', 0), ('working', 'succeeded', 5)]
    assert main(args + ['--run-key', 'second']) == 0
    again = json.loads(capsys.readouterr().out)
    assert again[1]['duplicates'] == 5 and count(sf) == 5


def test_atom_feed_supported():
    data = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Capacity update</title><link href="https://example.org/news"/>
      <updated>2026-09-29T12:00:00Z</updated><summary>Short note</summary></entry>
    </feed>'''
    item = parse_feed(data, 5)[0]
    assert item.title == 'Capacity update' and item.published_at == '2026-09-29T12:00:00+00:00'
