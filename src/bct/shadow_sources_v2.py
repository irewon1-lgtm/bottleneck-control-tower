"""Bounded primary-source intake for v2 shadow only; no production DB writes.

Provider indexes are leads, not provenance PASS or demand/supply facts. Preserve
raw bytes and metadata; only source-verified documents reach the existing gate.
"""
import argparse
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

from . import precursor_v2 as v2
from .shadow_v2 import run as shadow_run, now
from .target_acquisition import fetch, verify, error_status, Metadata, public_url
from .collectors.usaspending.collector import USAspendingTransport, request_body, parse_response
from .future_body import _Document, _nodes, _blocks, _text as node_text

_eaton_last_request=0.0


def private_root(path):
    root=Path(path).resolve()
    if 'live-state' in root.parts or (root/'session.json').exists():
        raise ValueError('LIVE_STORE_FORBIDDEN')
    root.mkdir(parents=True,exist_ok=True)
    return root


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def _get(url,source):
    public_url(url)
    if source['kind']=='sec_atom':
        agent=os.environ.get('BCT_SEC_USER_AGENT')
        if not agent or not re.search(r'\S+@\S+|https?://\S+',agent):
            raise ValueError('SEC_OPERATOR_CONTACT_NOT_CONFIGURED')
        if urlsplit(url).hostname not in ('www.sec.gov','data.sec.gov'):
            raise ValueError('SEC_SOURCE_HOST_MISMATCH')
        with urlopen(Request(url,headers={'User-Agent':agent,'Accept-Encoding':'identity'}),timeout=20) as r:
            raw=r.read(4*1024*1024+1);final=r.url;status=r.status;ctype=r.headers.get('Content-Type','')
        if len(raw)>4*1024*1024:raise ValueError('SOURCE_SIZE_LIMIT')
        return raw,final,status,ctype
    if urlsplit(url).hostname=='www.eaton.com':
        # The official robots.txt requests a 20-second crawl delay.
        global _eaton_last_request
        delay=20-(time.monotonic()-_eaton_last_request)
        if delay>0:time.sleep(delay)
        _eaton_last_request=time.monotonic()
    return fetch(url)


def common_document(value):
    """One schema, including failed inputs. Missing values stay null/UNKNOWN."""
    value=dict(value)
    for key in ('origin_id','origin_url','published_at','acquired_at','body','body_sha256','version'):
        value.setdefault(key,None)
    publisher=value.get('origin_publisher')
    value['publisher']=None if publisher in (None,'UNKNOWN') else publisher
    value['origin_publisher']=publisher or 'UNKNOWN'  # Existing shadow schema.
    value.setdefault('provenance_verified',False)
    value.setdefault('checks',{})
    value.setdefault('provenance_blockers',[value.get('error','SOURCE_PROOF_MISSING')] if not value['provenance_verified'] else [])
    value['provenance']='PASS' if value['provenance_verified'] else 'BLOCKED' if value.get('error') else 'FAIL'
    value['provenance_evidence']={'checks':value['checks'],'failures':value['provenance_blockers'],
                                  'source_proof':value.get('source_proof',{})}
    return value


class _SourceDOM(_Document):
    """Source DOM with character spans into the unchanged captured HTML."""
    def __init__(self,html):
        super().__init__();self.html=html;self.lines=[0]
        for match in re.finditer('\n',html):self.lines.append(match.end())
    def raw_offset(self):
        line,column=self.getpos();return self.lines[line-1]+column
    def handle_starttag(self,tag,attrs):
        offset=self.raw_offset();super().handle_starttag(tag,attrs)
        node=self.stack[-1] if self.stack[-1].tag==tag else self.stack[-1].children[-1]
        node.raw_start=offset
        if node.closed:node.raw_end=offset+len(self.get_starttag_text())
    def handle_endtag(self,tag):
        end=self.html.find('>',self.raw_offset())+1
        for node in reversed(self.stack):
            if node.tag==tag:
                node.raw_end=end;break
        super().handle_endtag(tag)


def _html_ref(html,node):
    start=getattr(node,'raw_start',0);end=getattr(node,'raw_end',start)
    return {'representation':'RAW_HTML','locator':{'start':start,'end':end},'quote':html[start:end]}


def _date(raw):
    if not isinstance(raw,str):return None,'UNKNOWN'
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):return datetime.strptime(raw,'%Y-%m-%d').date().isoformat(),'DATE'
        if re.fullmatch(r'[A-Za-z]+ \d{1,2}, \d{4}',raw):return datetime.strptime(raw,'%B %d, %Y').date().isoformat(),'DATE'
        value=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if value.tzinfo:return value.isoformat(),'TIMESTAMP'
    except ValueError:pass
    return None,'UNKNOWN'


def verify_page(raw,url,final,acquired,status,ctype,adapter):
    """Visible source-specific publication/identity/body proof, never feed dates."""
    html=raw.decode('utf-8',errors='strict');dom=_SourceDOM(html);dom.feed(html);dom.close()
    nodes=list(_nodes(dom.root));meta=Metadata();meta.feed(html)
    if adapter=='eia':
        sections=[n for n in nodes if 'tie-article' in n.attrs.get('class','').split()]
        section=sections[0] if len(sections)==1 else None
        inner=list(_nodes(section)) if section else []
        dates=[n for n in inner if n.tag=='span' and 'date' in n.attrs.get('class','').split()]
        raw_pub=node_text(dates[0]) if len(dates)==1 else None
        publisher=meta.meta.get('agency')
        bound_url=meta.meta.get('og:url')
        body='\n'.join(_blocks(section)) if section else ''
        complete=bool(section and section.closed and getattr(section,'raw_end',None))
        headings=[node_text(n) for n in inner if n.tag=='h1']
        identity=(urlsplit(url).hostname=='www.eia.gov' and urlsplit(url).path=='/todayinenergy/detail.php'
                  and meta.meta.get('url')==bound_url and meta.meta.get('og:type')=='article'
                  and len(headings)==1 and meta.meta.get('og:title','').startswith(headings[0]))
        attribution=bool(publisher and 'Energy Information Administration' in publisher
                         and 'Energy Information Administration' in meta.meta.get('og:title','')
                         and 'U.S. Energy Information Administration' in body)
        proof_nodes=([section]+dates) if section else []
    elif adapter=='eaton':
        sections=[n for n in nodes if 'eaton-text-default__content' in n.attrs.get('class','').split()]
        raw_pub=meta.meta.get('publish-date');publisher=meta.meta.get('og:site_name');bound_url=meta.canonical
        body='\n'.join(b for n in sections for b in _blocks(n))
        title_nodes=[n for n in nodes if n.tag=='h1' and any(c in n.attrs.get('class','').split()
                     for c in ('eaton-title__headline','eaton-title__eyebrow-and-byline'))]
        headings=[node_text(n) for n in title_nodes]
        bylines=[n for n in nodes if 'eaton-title__byline' in n.attrs.get('class','').split()]
        complete=bool(sections and all(n.closed and getattr(n,'raw_end',None) for n in sections))
        identity=(urlsplit(url).hostname=='www.eaton.com' and '/company/news-insights/news-releases/' in urlsplit(url).path
                  and meta.meta.get('page-url')==bound_url==meta.meta.get('og:url') and bool(headings))
        first_blocks=_blocks(sections[0]) if sections else []
        visible_date=bool(raw_pub and first_blocks and first_blocks[0]==raw_pub)
        date_value,date_precision=_date(raw_pub)
        expected_byline=(publisher+', '+datetime.strptime(date_value,'%Y-%m-%d').strftime('%m/%d/%Y')) if publisher and date_precision=='DATE' else None
        byline_matches=bool(expected_byline and any(node_text(n)==expected_byline for n in bylines))
        attribution=bool(publisher and (('About '+publisher in body and visible_date)
                                       or (publisher+' is an' in body and byline_matches)))
        proof_nodes=sections+title_nodes+bylines
    else:raise ValueError('UNKNOWN_PAGE_ADAPTER')
    published,precision=_date(raw_pub)
    normalized=lambda u:(urlsplit(u or '').hostname,urlsplit(u or '').path.rstrip('/'),urlsplit(u or '').query)
    checks={'http_success':status==200,'source_page_identity':bool(identity and bound_url and normalized(url)==normalized(final)==normalized(bound_url)),
            'publisher_observed':bool(publisher),'attribution_consistent':attribution,
            'original_publication':bool(published),'complete_article_scope':complete and bool(body),
            'no_access_challenge':not bool(re.search(r'verify you are human|access denied|continue reading.{0,60}subscribe',body,re.I)),
            'publication_before_acquisition':bool(published and published[:10]<=acquired[:10]),
            'acquisition_recorded':bool(acquired),'body_hash_matches':bool(body)}
    # A metadata-only publisher or unrelated footer cannot establish ownership.
    proof={'article_sections':[_html_ref(html,n) for n in proof_nodes],
           'observed_metadata':{k:v for k,v in meta.meta.items() if k in ('agency','og:title','og:url','url','og:site_name','page-url','publish-date')},
           'metadata_references':[_html_ref(html,n) for n in nodes if n.tag=='meta'
                                  and (n.attrs.get('name') or n.attrs.get('property')) in ('agency','og:title','og:url','url','og:site_name','page-url','publish-date')],
           'publication_raw':raw_pub,'identity_url_raw':bound_url}
    sha=v2.digest(body.encode())
    return common_document({'origin_id':bound_url,'origin_url':url,'origin_publisher':publisher,
        'canonical_url':meta.canonical,'source_bound_url':bound_url,'published_at':published,
        'published_at_raw':raw_pub,'publication_precision':precision,'acquired_at':acquired,'available_at':acquired,
        'body':body,'body_sha256':sha,'version':sha,'raw_sha256':v2.digest(raw),'checks':checks,
        'source_proof':proof,'provenance_verified':all(checks.values()),
        'provenance_blockers':[k for k,val in checks.items() if not val],
        'body_status':'FULL' if complete and body else 'PARTIAL'})


def verify_award(raw,url,final,acquired,status,award):
    """Official structured record, not a contract announcement or signing date."""
    value=json.loads(raw);body=raw.decode('utf-8',errors='strict')
    # Preserve the complete response. Dates retain their documented semantics.
    # The award detail schema exposes date_signed and last_modified_date, not
    # an original publication timestamp or an explicit document publisher.
    published,precision=None,'UNKNOWN'
    publisher=None
    checks={'http_success':status==200,'official_record_identity':final==url and value.get('generated_unique_award_id')==award.external_id and value.get('piid')==award.award_id,
            'record_complete':isinstance(value.get('description'),str) and isinstance(value.get('period_of_performance'),dict),
            'publisher_observed':bool(publisher),'original_publication':bool(published),
            'publication_before_acquisition':bool(published and published[:10]<=acquired[:10]),'acquisition_recorded':bool(acquired)}
    sha=v2.digest(raw)
    return common_document({'origin_id':value.get('generated_unique_award_id'),'origin_url':url,
        'origin_publisher':publisher,'published_at':published,'publication_precision':precision,
        'acquired_at':acquired,'available_at':acquired,'body':body,'body_sha256':sha,'version':sha,
        'raw_sha256':sha,'checks':checks,'provenance_verified':all(checks.values()),
        'provenance_blockers':[k for k,val in checks.items() if not val],
        'source_proof':{'record_identity':value.get('generated_unique_award_id'),'date_signed':value.get('date_signed'),
                        'period_of_performance':value.get('period_of_performance'),
                        'awarding_agency':value.get('awarding_agency'),
                        'note':'Signing, performance and last-modified dates are not publication proof.'}})


def eaton_sitemap(source,root):
    """Official sitemap resolves the client-rendered listing, without a search API."""
    index='https://www.eaton.com/sitemap.xml'
    raw,final,status,ctype=_get(index,source)
    file=root/'raw'/(v2.digest(raw)+'.sitemap');file.parent.mkdir(exist_ok=True)
    if not file.exists():file.write_bytes(raw)
    tree=ET.fromstring(raw)
    children=[n.text for n in tree.findall('.//{*}loc') if n.text=='https://www.eaton.com/us/en-us.sitemap.xml']
    if len(children)!=1:raise ValueError('OFFICIAL_LOCALE_SITEMAP_MISSING')
    raw,final,status,ctype=_get(children[0],source)
    file=root/'raw'/(v2.digest(raw)+'.sitemap')
    if not file.exists():file.write_bytes(raw)
    tree=ET.fromstring(raw);leads=[];pattern=re.compile(source['article_path_pattern'])
    for n in tree.findall('{*}url'):
        url=n.findtext('{*}loc')
        if not url or urlsplit(url).hostname not in source['article_hosts'] or not pattern.search(urlsplit(url).path):continue
        leads.append({'url':url,'recorded_updated':n.findtext('{*}lastmod'),'recorded_publication':None})
    # URL ordering is scheduling only; lastmod/year never fills published_at.
    return sorted(leads,key=lambda x:x['url'],reverse=True)[:source.get('limit',2)]


def feed_links(raw,url,kind,limit):
    root=ET.fromstring(raw);out=[]
    if root.tag.endswith('feed'):
        for entry in root.findall('{*}entry'):
            links=[e.get('href') for e in entry.findall('{*}link') if e.get('rel','alternate')=='alternate']
            if not links:continue
            out.append({'url':urljoin(url,links[0]),'index_id':entry.findtext('{*}id'),
                        'title':entry.findtext('{*}title'),'recorded_publication':entry.findtext('{*}published'),
                        'recorded_updated':entry.findtext('{*}updated')})
    else:
        for entry in root.findall('.//item'):
            link=entry.findtext('link')
            if link:out.append({'url':urljoin(url,link),'index_id':entry.findtext('guid'),
                               'title':entry.findtext('title'),'recorded_publication':entry.findtext('pubDate')})
    return out[:limit]


def discover(source,raw,final):
    limit=source.get('limit',3)
    if source['kind'] in ('sec_atom','official_feed'):
        leads=feed_links(raw,final,source['kind'],limit)
    elif source['kind']=='official_index':
        meta=Metadata();meta.feed(raw.decode('utf-8',errors='replace'));leads=[]
        pattern=re.compile(source['article_path_pattern'])
        for href,title in meta.links:
            url=urljoin(final,href)
            if urlsplit(url).hostname not in source['article_hosts'] or not pattern.search(urlsplit(url).path):continue
            if any(x['url']==url for x in leads):continue
            leads.append({'url':url,'title':title,'recorded_publication':None})
            if len(leads)==limit:break
    else:raise ValueError('UNSUPPORTED_SOURCE_KIND')
    hosts=source['article_hosts']
    return [x for x in leads if urlsplit(x['url']).hostname in hosts and x['url'].startswith('https://')]


def _sec_primary(source,lead,root):
    """Resolve the SEC filing index; preserve acceptance/issuer as observations.

    Index times are not fabricated article metadata. Until issuer/acceptance/body
    correspondence is verified, a filing remains an intake lead, not PASS.
    """
    raw,final,status,ctype=_get(lead['url'],source)
    digest=v2.digest(raw);(root/'raw').mkdir(exist_ok=True)
    file=root/'raw'/(digest+'.html')
    if not file.exists():file.write_bytes(raw)
    html=raw.decode('utf-8',errors='strict');text=_text(html)
    issuer=re.search(r'<span\b[^>]*class=["\']companyName["\'][^>]*>\s*([^<]+)',html,re.I)
    accepted=re.search(r'\bAccepted\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\b',text)
    cik=re.search(r'/Archives/edgar/data/(\d+)/',urlsplit(final).path)
    links=[]
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',html,re.I|re.S):
        if not re.search(r'<td\b[^>]*>\s*8-K\s*</td>',row,re.I):continue
        m=Metadata();m.feed(row)
        links += [urljoin(final,h) for h,_ in m.links if urlsplit(urljoin(final,h)).path.endswith(('.htm','.html'))]
    prefix=urlsplit(final).path.rsplit('/',1)[0]+'/'
    links=[u for u in links if urlsplit(u).hostname=='www.sec.gov' and urlsplit(u).path.startswith(prefix)]
    if len(set(links))!=1 or not issuer or not accepted or not cik or final!=lead['url']:
        raise ValueError('SEC_ISSUER_ACCEPTANCE_PRIMARY_DOCUMENT_BINDING_UNVERIFIED')
    publication=datetime.strptime(accepted[1],'%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo('America/New_York')).isoformat()
    return {**lead,'filing_index_url':lead['url'],'url':links[0],'index_raw_sha256':digest,
            'issuer':unescape(issuer[1]).strip(),'issuer_cik':cik[1],
            'accepted_at_raw':accepted[1],'published_at':publication}


class _Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.ignore+=1
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.ignore:self.ignore-=1
    def handle_data(self,data):
        if not self.ignore and data.strip():self.parts.append(data.strip())


def _text(html):
    p=_Text();p.feed(html);return '\n'.join(p.parts)


def verify_sec(raw,lead,final,acquired,status,ctype):
    """SEC acceptance is an observed public filing time, not an RSS timestamp.

    The filing table binds the primary form to its issuer. Preserve the full
    form text and issuer as origin; SEC hosting does not make two filings from
    the same company independent sources.
    """
    html=raw.decode('utf-8',errors='strict');body=_text(html)
    publisher=lead['issuer'];pub=lead['published_at']
    normalize=lambda x:re.sub(r'\W+',' ',x).casefold().strip()
    checks={'http_success':status==200,'filing_primary_binding':final==lead['url'],
            'issuer_in_original_body':normalize(publisher) in normalize(body),
            'original_form_8k':bool(re.search(r'\bFORM\s+8-K\b',body,re.I)),
            'complete_original_html':bool(re.search(r'</html\s*>\s*$',html,re.I)) and 'html' in ctype,
            'acceptance_before_acquisition':datetime.fromisoformat(pub)<=datetime.fromisoformat(acquired),
            'available_at_recorded':bool(acquired),'nonempty_body':bool(body)}
    sha=v2.digest(body.encode())
    return {'origin_id':'sec-filer:'+lead['issuer_cik'],'origin_url':lead['url'],
            'canonical_url':None,'source_bound_url':lead['url'],'origin_publisher':publisher,
            'published_at':pub,'published_at_raw':lead['accepted_at_raw'],
            'publication_precision':'TIMESTAMP','publication_basis':'SEC_PUBLIC_ACCEPTANCE',
            'acquired_at':acquired,'available_at':acquired,'body':body,'body_sha256':sha,
            'version':sha,'raw_sha256':v2.digest(raw),'checks':checks,
            'source_proof':{k:lead[k] for k in ('filing_index_url','index_raw_sha256','issuer','issuer_cik','accepted_at_raw')},
            'provenance':'PASS' if all(checks.values()) else 'BLOCKED',
            'provenance_verified':all(checks.values()),'provenance_blockers':[k for k,val in checks.items() if not val],
            'body_status':'FULL' if all(checks.values()) else 'PARTIAL'}


def intake(catalog,root,*,completed_urls=()):
    root=private_root(root);seen=set(completed_urls);documents=[];receipts=[]
    for source in catalog['sources']:
        record={'source_id':source['id'],'kind':source['kind'],'at':now(),'leads':[]}
        try:
            if source['kind']=='usaspending':
                payload=USAspendingTransport().post(request_body(source['query'],'keyword',source.get('limit',3)))
                awards=parse_response(payload,source.get('limit',3))
                file=root/'raw'/(v2.digest(payload)+'.json');file.parent.mkdir(exist_ok=True);file.write_bytes(payload)
                record.update(status='INDEX_RECEIVED',awards=[a.__dict__ for a in awards],raw_sha256=v2.digest(payload))
                for award in awards:
                    url='https://api.usaspending.gov/api/v2/awards/'+quote(award.external_id,safe='')+'/'
                    if url in seen:continue
                    seen.add(url)
                    d={'document_id':'shadow-source-'+v2.digest(url),'source_id':source['id'],'url':url}
                    try:
                        raw,final,status,ctype=_get(url,source);acquired=now()
                        file=root/'raw'/(v2.digest(raw)+'.json')
                        if not file.exists():file.write_bytes(raw)
                        d.update(verify_award(raw,url,final,acquired,status,award))
                        d.update(status='BODY_CAPTURED',raw_path=str(file),final_url=final)
                    except Exception as exc:d.update(status=error_status(exc),error=str(exc))
                    documents.append(common_document(d))
                receipts.append(record);continue
            raw,final,status,ctype=_get(source['url'],source)
            file=root/'raw'/(v2.digest(raw)+'.index');file.parent.mkdir(exist_ok=True)
            if not file.exists():file.write_bytes(raw)
            leads=discover(source,raw,final)
            if not leads and source['id']=='official-capacity-eaton':
                leads=eaton_sitemap(source,root)
            record.update(status='INDEX_RECEIVED',raw_sha256=v2.digest(raw),leads=leads)
            if not leads:
                record['blocker']='SOURCE_INDEX_NO_ELIGIBLE_LINKS'
            for lead in leads:
                if lead['url'] in seen:continue
                seen.add(lead['url'])
                acquired=now();d={'document_id':'shadow-source-'+v2.digest(lead['url']),
                                  'source_id':source['id'],'url':lead['url'],'lead':lead,'acquired_at':acquired}
                try:
                    if source['kind']=='sec_atom':lead=_sec_primary(source,lead,root);d['lead']=lead
                    raw,final,status,ctype=_get(lead['url'],source);acquired=now()
                    file=root/'raw'/(v2.digest(raw)+'.html')
                    if not file.exists():file.write_bytes(raw)
                    if source['kind']=='sec_atom':result=verify_sec(raw,lead,final,acquired,status,ctype)
                    elif source['id']=='official-energy-capacity-eia':result=verify_page(raw,lead['url'],final,acquired,status,ctype,'eia')
                    elif source['id']=='official-capacity-eaton':result=verify_page(raw,lead['url'],final,acquired,status,ctype,'eaton')
                    else:result=verify(raw,lead['url'],final,acquired,status,ctype)
                    d.update(result)
                    d.update(status='BODY_CAPTURED',raw_path=str(file),final_url=final)
                except Exception as exc:d.update(status=error_status(exc),provenance='BLOCKED',provenance_verified=False,error=str(exc))
                documents.append(common_document(d))
        except Exception as exc:
            record.update(status='BLOCKED' if str(exc)=='SEC_OPERATOR_CONTACT_NOT_CONFIGURED' else error_status(exc),error=str(exc))
            record['input_status']=common_document({'origin_url':source.get('url'),'error':str(exc)})
        receipts.append(record)
    passed=[];hashes=set()
    for d in documents:
        if d.get('provenance_verified') is not True or d['body_sha256'] in hashes:continue
        try:v2.validate_document(d,now())
        except (KeyError,TypeError,ValueError) as exc:
            d.update(provenance='FAIL',provenance_verified=False,
                     provenance_blockers=d.get('provenance_blockers',[])+['SHADOW_DOCUMENT_VALIDATION:'+str(exc)])
            d.update(common_document(d))
            continue
        hashes.add(d['body_sha256']);passed.append(d)
    save(root/'intake.json',{'version':'BCT_V2_PRIMARY_SOURCE_INTAKE_2','adapter_sha256':v2.digest(Path(__file__).read_bytes()),
                            'receipts':receipts,'documents':documents,'verified_document_count':len(passed),'LIVE_writes':0})
    save(root/'verified-input.json',{'documents':passed,'mode':'SHADOW'})
    return passed,receipts


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--store',type=Path,required=True);p.add_argument('--completed-input',type=Path,action='append',default=[]);a=p.parse_args()
    # Validate both destinations before any request or write.
    private_root(a.output);private_root(a.store)
    completed=set()
    for path in a.completed_input:
        completed.update(d.get('origin_url') or d.get('url') for d in json.loads(path.read_text())['documents'])
    docs,receipts=intake(json.loads(a.catalog.read_text()),a.output,completed_urls=completed)
    result=shadow_run(a.store,docs)
    print(json.dumps({'source_receipts':receipts,'verified_documents':len(docs),'counts':result['counts'],'freeze':result['freeze']},ensure_ascii=False))


if __name__=='__main__':main()
