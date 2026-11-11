"""Valid empty feed intake is a zero-record success, never fabricated coverage."""
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from bct.collector import MalformedRecord
from bct.collectors.rss.cli import main
from bct.collectors.rss.collector import RSSCollector, parse_feed
from bct.models import CollectorRun, RadarItem


EMPTY_RSS = b'<rss version="2.0"><channel><title>Example news</title><link>https://publisher.example/</link><description/></channel></rss>'
EMPTY_ATOM = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Example news</title><id>urn:example:news</id><updated>2026-11-11T08:00:00Z</updated></feed>'


def test_saved_valid_empty_source_preserves_exact_bytes_and_returns_no_items():
    path = Path(__file__).parent / 'fixtures/rss_empty_source.xml'
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == '148ee2cbd14f29c4c40d809dfe336a200fc73a2297f1ed035e07e050a5473c0c'
    assert parse_feed(payload, 10) == []
    assert path.read_bytes() == payload


@pytest.mark.parametrize('payload', [EMPTY_RSS, EMPTY_ATOM,
    EMPTY_RSS.replace(b'<description/>', b'<description>A news channel.</description>'),
    EMPTY_ATOM.replace(b'08:00:00Z', b'10:00:00+02:00'),
])
def test_valid_empty_rss_and_atom_return_no_items(payload):
    assert parse_feed(payload, 10) == []


@pytest.mark.parametrize('payload', [
    b'<html><title>Service unavailable</title></html>',
    b'<rss version="2.0"><channel>',
    b'<rss version="2.0"/>',
    b'<rss version="2.0"><channel/></rss>',
    EMPTY_RSS.replace(b'</rss>', b'<channel/></rss>'),
    EMPTY_RSS.replace(b'<title>Example news</title>', b''),
    EMPTY_RSS.replace(b'<title>Example news</title>', b'<title> </title>'),
    EMPTY_RSS.replace(b'</title>', b'</title><title>Duplicate</title>'),
    EMPTY_RSS.replace(b'<link>https://publisher.example/</link>', b''),
    EMPTY_RSS.replace(b'https://publisher.example/', b'not-a-URL'),
    EMPTY_RSS.replace(b'https://publisher.example/', b'javascript:alert(1)'),
    EMPTY_RSS.replace(b'https://publisher.example/', b'https://user:secret@publisher.example/'),
    EMPTY_RSS.replace(b'<description/>', b''),
    EMPTY_RSS.replace(b'version="2.0"', b'version="unknown"'),
    EMPTY_RSS.replace(b'</channel>', b'<wrapper><item/></wrapper></channel>'),
    EMPTY_RSS.replace(b'</rss>', b'<item/></rss>'),
    b'<feed xmlns="http://www.w3.org/2005/Atom"/>',
    EMPTY_ATOM.replace(b'<id>urn:example:news</id>', b''),
    EMPTY_ATOM.replace(b'urn:example:news', b'not-an-absolute-IRI'),
    EMPTY_ATOM.replace(b'<title>Example news</title>', b'<title/>'),
    EMPTY_ATOM.replace(b'<updated>2026-11-11T08:00:00Z</updated>', b''),
    EMPTY_ATOM.replace(b'2026-11-11T08:00:00Z', b'2026-11-11'),
    EMPTY_ATOM.replace(b'2026-11-11T08:00:00Z', b'2026-11-11T08:00:00'),
    EMPTY_ATOM.replace(b'2026-11-11T08:00:00Z', b'2026-02-30T08:00:00Z'),
    EMPTY_ATOM.replace(b'</updated>', b'</updated><updated>2026-11-11T08:00:00Z</updated>'),
    EMPTY_ATOM.replace(b'</feed>', b'<wrapper><entry/></wrapper></feed>'),
    b'<RDF xmlns="http://purl.org/rss/1.0/"/>',
])
def test_invalid_empty_container_does_not_become_no_input(payload):
    with pytest.raises(MalformedRecord):
        parse_feed(payload, 10)


@pytest.mark.parametrize('payload', [
    b'<!DOCTYPE rss [<!ENTITY unsafe "text">]>' + EMPTY_RSS,
    EMPTY_RSS.replace(b'</channel>', b'<item><link>https://publisher.example/item</link></item></channel>'),
    EMPTY_RSS.replace(b'</channel>', b'<item><title>Item</title><link>javascript:alert(1)</link></item></channel>'),
    EMPTY_RSS.replace(b'</channel>', b'<item><title>Item</title><link>https://publisher.example/item</link><pubDate>not-a-date</pubDate></item></channel>'),
    EMPTY_ATOM.replace(b'</feed>', b'<entry><title>Item</title></entry></feed>'),
])
def test_dtd_and_malformed_entries_remain_rejected(payload):
    with pytest.raises(MalformedRecord):
        parse_feed(payload, 10)


class PayloadTransport:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url):
        return self.payload


def test_empty_feed_is_no_new_input_with_existing_success_status_and_rows_preserved(setup):
    settings, sf = setup
    populated = EMPTY_RSS.replace(b'</channel>', b'<item><title>Existing item</title><link>https://publisher.example/item</link></item></channel>')
    assert RSSCollector(settings, PayloadTransport(populated)).run('https://publisher.example/feed', 'populated').saved == 1
    result = RSSCollector(settings, PayloadTransport(EMPTY_RSS)).run('https://publisher.example/feed', 'empty')
    assert result.status == 'succeeded' and result.error is None
    assert (result.saved, result.updated, result.duplicates, result.failed) == (0, 0, 0, 0)
    with sf() as db:
        assert db.get(CollectorRun, result.run_id).status == 'succeeded'
        assert db.scalar(select(func.count()).select_from(RadarItem)) == 1


def test_cli_accepts_valid_empty_feed_without_creating_articles(setup, tmp_path, monkeypatch, capsys):
    settings, sf = setup
    config = tmp_path / 'config.yaml'
    config.write_text(f'storage_root: {settings.root}\n')
    feeds = tmp_path / 'feeds.yaml'
    feeds.write_text('feeds:\n  Empty channel: https://publisher.example/feed\n')
    monkeypatch.setattr('bct.collectors.rss.cli.RSSTransport', lambda: PayloadTransport(EMPTY_RSS))
    assert main(['--config', str(config), '--feeds', str(feeds), '--run-key', 'empty-only']) == 0
    result = json.loads(capsys.readouterr().out)[0]
    assert result['status'] == 'succeeded' and result['saved'] == result['failed'] == 0
    with sf() as db:
        assert db.scalar(select(func.count()).select_from(RadarItem)) == 0
