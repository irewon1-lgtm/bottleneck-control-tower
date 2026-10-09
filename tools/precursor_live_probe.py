"""Fetch current configured RSS originals through the production wrapper.

This read-only operational probe never creates a prospective session, writes a
canonical database, or calls external search. Newly fetched URLs are separated
from the historical QA cache, with literal publication/acquisition timestamps.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

from bct import precursor_collection as c


def feed_entries(raw):
    """RSS and Atom seed metadata; never original-source provenance."""
    dom=ET.fromstring(raw)
    for item in dom.iter():
        if item.tag.rsplit('}',1)[-1] not in ('item','entry'):continue
        fields={};links=[]
        for child in item:
            tag=child.tag.rsplit('}',1)[-1]
            if tag=='link':
                if child.get('href') and child.get('rel','alternate')=='alternate':links.append(child.get('href'))
                elif child.text:links.append(child.text.strip())
            elif child.text:fields[tag]=child.text.strip()
        if links:yield links[0],fields.get('pubDate') or fields.get('published'),fields.get('updated')


def feed_time(value):
    if not value:return None
    try:
        at=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        try:at=parsedate_to_datetime(value)
        except (ValueError,TypeError):return None
    return at.astimezone(timezone.utc) if at.tzinfo else None


def run(output,state,baseline,known_document_ids=None,known_urls=None,published_since=None):
    repository=Path(__file__).resolve().parents[1]
    feeds=yaml.safe_load((repository/'rss_feeds.yaml').read_text())['feeds']
    # Fixed configured feed selection spans defense, power and official agency
    # publications. No cache-derived query or web search is ever submitted.
    selected=list(feeds.items()) if published_since else list(feeds.items())[:4]+[(k,v) for k,v in feeds.items() if k in ('POWER Magazine','EIA Today in Energy','NIST News','Semiconductor Engineering')]
    exclusions=c.read(repository/'config/precursor-baseline-exclusions.json')['urls']+c.read(repository/'config/precursor-completed-exclusions.json')['urls']
    if baseline.exists():exclusions+= [c.read(p)['origin_url'] for p in (baseline/'documents').glob('*.json')]
    excluded=set(exclusions)|set(known_urls or []);started=c.acquisition.now();results=[]
    cutoff=feed_time(published_since) if published_since else None
    if published_since and not cutoff:raise ValueError('invalid prospective feed cutoff')
    def fetch(item):
        name,url=item;record={'feed':name,'url':url,'fetched_at':c.acquisition.now(),'documents':[]}
        try:
            raw,final,status,ctype=c.acquisition.fetch(url)
            path=output/'feeds'/(c.acquisition.digest(raw)+'.xml');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            old=unknown=0
            for link,published,updated in feed_entries(raw):
                at=feed_time(published)
                if cutoff and (not at or at<cutoff or at>feed_time(started)):
                    unknown+=not bool(at);old+=bool(at);continue
                if link and link.startswith('https://') and link not in excluded and 'rss-probe-'+c.acquisition.digest(link) not in set(known_document_ids or []):
                    record['documents'].append({'document_id':'rss-probe-'+c.acquisition.digest(link),'url':link,'collected_at':c.acquisition.now(),'rss_published_text':published,'rss_updated_text':updated})
            record.update(status='FETCHED',raw_sha256=c.acquisition.digest(raw),outside_feed_delta=old,feed_date_unknown=unknown)
        except Exception as exc:record.update(status=c.source_search.error_status(exc),error=str(exc)[:300])
        return record
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(fetch,selected))
    rows={r['url']:r for feed in results for r in feed['documents']}
    manifest={'collection_started_at':started,'documents':list(rows.values()) if cutoff else list(rows.values())[:24],'preexisting_document_ids':sorted(known_document_ids or []), 'preexisting_urls':sorted(excluded),'read_only_live_probe':True}
    output.mkdir(parents=True,exist_ok=True);(output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    spec=importlib.util.spec_from_file_location('operating_wrapper',repository/'.github/scripts/new_precursor_cycle.py');wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
    summaries=wrapper.run(manifest,state,search_endpoint=None,live_store=None)
    value={'mode':'ACTUAL_FRESH_RSS_OPERATING_PROBE','collection_started_at':started,'rss_publication_filter_not_provenance':published_since,'configured_feeds':len(feeds),'attempted_feeds':len(selected),'feed_results':results,'new_unique_rss_urls':len(rows),'attempted_new_urls':len(manifest['documents']),
           'verified_new_bodies':sum(r['new_seed_statuses'].get('CAPTURED',0) for r in summaries),
           'new_live_early_candidates':sum(r.get('gap_verified_early_preflight',0) for r in summaries),
           'raw_engine_preflight':sum(r.get('unique_early_preflight',r.get('early_preflight',0)) for r in summaries),
           'frozen_new_live_candidates':sum(r['live_execution']['frozen']+r.get('graph_live_execution',{}).get('frozen',0) for r in summaries),
           'canonical_write_count':0,'existing_live_store_write_count':0,'external_search_requests':0,'summaries':summaries}
    (output/'summary.json').write_text(json.dumps(value,indent=2));print(json.dumps({k:v for k,v in value.items() if k not in ('feed_results','summaries')}));return value


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--known-document-ids',type=Path);p.add_argument('--known-urls',type=Path);p.add_argument('--published-since')
    a=p.parse_args();run(a.output,a.state,a.baseline,json.loads(a.known_document_ids.read_text()) if a.known_document_ids else None,json.loads(a.known_urls.read_text()) if a.known_urls else None,a.published_since)
