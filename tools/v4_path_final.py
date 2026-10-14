"""One bounded cohort, no waiting/retry loop; shared quota pauses persisted."""
import json,pathlib,gzip
from bct.v4.research_reading import generate,decode
from bct.v4.evidence_path import save
from bct.v4.research_adapter import analyze as legacy
from bct.v4.store import Ledger,now,sha
R=pathlib.Path('docs/v4/path-comparison/final')


def verify():
    freeze=json.loads((R/'freeze.json').read_text())
    for p,h in freeze['file_sha256'].items():assert sha(pathlib.Path(p).read_bytes())==h,'FROZEN_CODE_OR_INPUT_CHANGED:'+p
    assert sha((R/'event-gold.json').read_bytes())==json.loads((R/'gold-freeze.json').read_text())['gold_sha256']


def main():
    verify();config=json.loads((R/'config.json').read_text());out=R/'responses';out.mkdir(exist_ok=True)
    for row in json.loads((R/'inputs.json').read_text())['documents']:
        p=out/(row['document_id']+'.json')
        if p.exists():continue
        verify();doc=row['doc'];windows=row['source']['windows'];prompt='SOURCE CONTEXTS (separate original spans, not continuous):\n'+ '\n\n'.join('[context '+str(i)+']\n'+w['text']for i,w in enumerate(windows))
        l=Ledger('var/v4/sequential/api-ledger')
        try:
            with l.worker():
                l.capture(doc,gzip.decompress(pathlib.Path(row['raw_path']).read_bytes()))
                receipt=generate(l,config,prompt,doc,windows,phase='final')
        finally:l.close()
        if receipt['status']=='WAIT_API':
            (R/'queue-state.json').write_text(json.dumps({'at':now(),'next_document_id':doc['document_id'],'receipt':receipt,'no_HTTP_attempt':True,'action':'Continue independent work; re-enter only after rolling window changes. No busy-wait loop.'},indent=2)+'\n');print(json.dumps(receipt));return
        result={'at':now(),'document_id':doc['document_id'],'receipt':receipt,'source':row['source']}
        if receipt['status']=='RECEIVED':
            try:
                proposals,held=decode(receipt['response']['text'],doc,windows)
                owned=Ledger('var/v4/path-comparison/final-events')
                with owned.worker():alternative=save(owned,[doc],{doc['document_id']:proposals},enabled=True)
                owned.close()
                quote_items=[{'kind':'PHYSICAL_PRODUCT','role':q['role'],'actuality':q['actuality'],'context':{'quote':q['reference']['quote'],'start':q['reference']['start'],'end':q['reference']['end']},'entity':{'value':q['product']['value'],'quote':q['product']['value'],'start':q['product']['reference']['start'],'end':q['product']['reference']['end']},'facts':[]}for q in proposals]
                legacy_source={k:v for k,v in row['source'].items()if k not in('response_protocol','response_contract')}
                old=legacy([doc],{doc['document_id']:{'text':json.dumps({'items':quote_items}),'source':legacy_source}},enabled=True,mode='BACKFILL',as_of='2026-10-14T12:00:00+00:00')
                result.update(proposals=proposals,source_held=held,alternative=alternative,legacy_connection=old,
                    comparison_scope='Same NEW JSON-mode model generation→legacy quote/source/adapter vs located alternative. NOT a new generation with the historically blocked old Groq prompt/strict schema.')
            except Exception as e:result['packet_error']=type(e).__name__+':'+str(e)
        with p.open('x')as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'document_id':doc['document_id'],'status':receipt['status'],'usage':receipt.get('response',{}).get('usage'),'alternative':result.get('alternative',{}).get('counts'),'packet_error':result.get('packet_error')}),flush=True)
        if receipt['status']!='RECEIVED':return
    (R/'queue-state.json').write_text(json.dumps({'at':now(),'status':'COMPLETE_NO_UNATTEMPTED_INPUTS'},indent=2)+'\n')


if __name__=='__main__':main()
