"""Feed dates select seeds and never become original publication evidence."""
import importlib.util
from pathlib import Path
from datetime import datetime,timezone

path=Path(__file__).resolve().parents[1]/'tools/precursor_live_probe.py'
spec=importlib.util.spec_from_file_location('probe',path);probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def test_rss_atom_and_namespace_entries_have_seed_only_times():
    rss=b'<rss><channel><item><link>https://agency.gov/a</link><pubDate>Fri, 09 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'
    atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><link rel="self" href="https://agency.gov/api/a"/><link rel="alternate" href="https://agency.gov/a"/><published>2026-10-09T00:00:00Z</published></entry></feed>'
    a=list(probe.feed_entries(rss));b=list(probe.feed_entries(atom))
    assert a[0][0]==b[0][0]=='https://agency.gov/a'
    assert probe.feed_time(a[0][1])==probe.feed_time(b[0][1])==datetime(2026,10,9,tzinfo=timezone.utc)


def test_updated_only_and_naive_dates_cannot_prove_new_publication():
    atom=b'<feed><entry><link href="https://agency.gov/a"/><updated>2026-10-09T00:00:00Z</updated></entry></feed>'
    assert list(probe.feed_entries(atom))[0][1] is None
    assert probe.feed_time('2026-10-09') is None
    assert probe.feed_time('invalid') is None
