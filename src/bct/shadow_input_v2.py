"""Offline v2 input loader: preserved snapshots plus source-bound PASS proofs.

No fetching, corpus scanning or modification of original input/proof records.
Only explicitly supplied local indexes participate in the input union.
"""
import json
from html.parser import HTMLParser
from pathlib import Path

from . import precursor_v2 as v2


class _SourceHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonical=[];self.metadata={};self.article_text=[];self.stack=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and 'canonical' in a.get('rel','').split():self.canonical.append(a.get('href'))
        if tag=='meta':self.metadata.setdefault(a.get('property'),[]).append(a.get('content'))
        scope=tag=='article' or bool({'entry-content','wp-block-post-content','article-content'} & set(a.get('class','').split()))
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append((tag,scope))

    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:];break

    def handle_data(self,data):
        if any(scope for _,scope in self.stack) and not any(tag in ('script','style') for tag,_ in self.stack):self.article_text.append(data)


def _json(path):
    return json.loads(Path(path).read_text())


def _snapshot(raw):
    if 'origin_url' in raw:
        return dict(raw)
    return {'document_id':raw['document_id'],'body':raw['body'],
            'body_sha256':raw['body_sha256'],'version':raw['body_sha256'],
            'origin_url':raw.get('original_url') or raw.get('url'),
            'origin_id':None,'origin_publisher':None,'provenance_verified':False,
            'published_at':None,'publication_precision':'UNKNOWN',
            'available_at':raw.get('collected_at'),
            'snapshot_recorded_published_at':raw.get('publication_timestamp'),
            'snapshot_source_version':raw.get('acquisition_ledger',{}).get('current_source_version')}


def _verified_proof(entry,documents):
    proof=_json(entry['proof'])
    if proof.get('provenance')!='PASS':raise ValueError('PROOF_NOT_PASS')
    html_path=Path(entry['source_html']);text=Path(entry['source_text']).read_text()
    doc=documents.get(proof['document_id'])
    if doc is None:
        # A PASS-indexed preserved source must not disappear merely because the
        # old selected-document list omitted it. Every value comes from its
        # existing proof/text; the same HTML and metadata checks still apply.
        doc={'document_id':proof['document_id'],'body':text,'body_sha256':proof['body_sha256'],
             'version':proof['body_version'],'origin_url':proof['url'],
             'available_at':proof['acquired_at_snapshot'],'provenance_verified':False,
             'snapshot_source_version':proof.get('snapshot_source_version')}
    if (v2.digest(html_path.read_bytes())!=proof['source_sha256'] or text!=doc['body']
            or v2.digest(text.encode())!=proof['body_sha256']
            or proof.get('body_version')!=doc['body_sha256']):
        raise ValueError('PROOF_SOURCE_BODY_VERSION_MISMATCH')
    source=_SourceHTML();source.feed(html_path.read_text())
    canonical=source.canonical
    def meta(name):
        return source.metadata.get(name,[])
    if (proof['url']!=doc['origin_url'] or proof['url'] not in canonical
            or proof['publisher'] not in meta('og:site_name')
            or proof['published_at_original'] not in meta('article:published_time')
            or proof['acquired_at_snapshot']!=doc['available_at']
            or proof.get('http')!=200 or proof.get('body_equals_snapshot') is not True):
        raise ValueError('PROOF_SOURCE_METADATA_MISMATCH')
    # The cached extracted text must correspond to the article in retained HTML,
    # rather than a second text file merely repeating the snapshot.
    if not source.article_text:raise ValueError('PROOF_ARTICLE_BODY_MISSING')
    original=' '.join(' '.join(source.article_text).split())
    if any(' '.join(line.split()) not in original for line in text.splitlines() if line.strip()):
        raise ValueError('PROOF_HTML_BODY_CORRESPONDENCE_MISMATCH')
    origin_id=proof.get('article_id')
    if not origin_id:raise ValueError('PROOF_ORIGIN_ID_MISSING')
    return {**doc,'origin_id':origin_id,'origin_publisher':proof['publisher'],
            'provenance_verified':True,'published_at':proof['published_at_original'],
            'publication_precision':'TIMESTAMP','provenance_proof_path':str(entry['proof'])}


def load_documents(input_path,*,source_snapshots=(),provenance_indexes=()):
    documents={};duplicates=0
    for path in (input_path,*source_snapshots):
        for raw in _json(path)['documents']:
            doc=_snapshot(raw)
            if v2.digest(doc['body'].encode())!=doc['body_sha256']:
                raise ValueError('INPUT_BODY_HASH_MISMATCH')
            key=doc['document_id']
            if key in documents:
                if documents[key]['body_sha256']!=doc['body_sha256']:
                    raise ValueError('INPUT_DOCUMENT_VERSION_CONFLICT')
                duplicates+=1
                # Preserve already verified source metadata over a raw snapshot.
                if documents[key].get('provenance_verified'):continue
            documents[key]=doc
    supplied_pass=set();applied=set();errors=[]
    for path in provenance_indexes:
        for entry in _json(path)['proofs']:
            proof=_json(entry['proof'])
            if proof.get('provenance')!='PASS':continue
            supplied_pass.add(proof['document_id'])
            try:
                doc=_verified_proof(entry,documents)
                documents[doc['document_id']]=doc;applied.add(doc['document_id'])
            except (KeyError,ValueError,TypeError,OSError) as exc:
                errors.append({'document_id':proof.get('document_id'),'reason':str(exc)})
    return list(documents.values()),{'documents_loaded':len(documents),'duplicate_versions_excluded':duplicates,
           'pass_proofs_supplied':len(supplied_pass),'pass_proofs_applied':len(applied),
           'provenance_pass_documents_missing':len(supplied_pass-applied),
           'proof_errors':errors,'network_requests':0}
