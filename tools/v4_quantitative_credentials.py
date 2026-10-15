"""One-shot Actions probe. Emits flags/hashes/counts, never secret values or URLs with keys."""
import json,os,re,base64
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from bct.v4.store import sha,now
from bct.collectors.sec.transport import SECTransport

ROOT=Path('var/v4/quantitative/credentials')


def run():
    ROOT.mkdir(parents=True,exist_ok=False)
    ua=os.environ.get('BCT_SEC_USER_AGENT','');key=os.environ.get('CENSUS_API_KEY','')
    result={'at':now(),'code_SHA':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
      'bindings':{'BCT_SEC_USER_AGENT':{'present':bool(ua),'contact_format_valid':bool(re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+',ua))},
                  'CENSUS_API_KEY':{'present':bool(key),'value_printed':False}},'external_AI_calls':0,'settings_changed':False}
    if result['bindings']['BCT_SEC_USER_AGENT']['contact_format_valid']:
        try:
            raw=SECTransport(ua).get('https://data.sec.gov/submissions/CIK0001701605.json');obj=json.loads(raw)
            safe={'cik':obj['cik'],'name':obj['name'],'filings':obj['filings']}
            if ua.encode()in raw:raise ValueError('SEC_IDENTITY_ECHO_REFUSED')
            (ROOT/'sec-original.json').write_bytes(raw)
            # Submissions contain public filing metadata, not user-agent/contact.
            (ROOT/'sec-submissions.json').write_text(json.dumps(safe))
            result['sec']={'HTTP':200,'cik':str(obj['cik']),'recent_filings':len(obj['filings']['recent']['accessionNumber']),'sha256':sha(raw),'actual_query':True}
        except Exception as e:result['sec']={'HTTP':getattr(e,'code','TRANSPORT_OR_SCHEMA_ERROR'),'error_type':type(e).__name__,'retried':False}
    else:result['sec']={'status':'BINDING_OR_CONTACT_FORMAT_BLOCKED','requests':0}
    if key:
        params={'get':'I_COMMODITY,GEN_QY1_MO,CON_QY1_MO,GEN_VAL_MO,CON_VAL_MO,UNIT_QY1','time':'from 2023-09 to 2026-08','I_COMMODITY':'2504101000','CTY_CODE':'0000'}
        url='https://api.census.gov/data/timeseries/intltrade/imports/hs?'+urlencode({**params,'key':key})
        try:
            with urlopen(Request(url,headers={'User-Agent':'BCT-Q1-free-research/1.0'}),timeout=25)as r:
                status=r.status;raw=r.read(20000001)
            if status!=200 or not raw or len(raw)>20000000:raise ValueError('CENSUS_HTTP_OR_SIZE')
            if key.encode()in raw:raise ValueError('CENSUS_CREDENTIAL_ECHO_REFUSED')
            obj=json.loads(raw)
            if not isinstance(obj,list)or not obj or not isinstance(obj[0],list):raise ValueError('CENSUS_DATA_CONTRACT')
            (ROOT/'census-first.json').write_bytes(raw)
            result['census']={'HTTP':status,'rows':len(obj)-1,'columns':obj[0],'sha256':sha(raw),'query_without_key':params,'published_at':'UNKNOWN'}
        except Exception as e:result['census']={'HTTP':getattr(e,'code','TRANSPORT_OR_SCHEMA_ERROR'),'error_type':type(e).__name__,'retried':False}
    else:result['census']={'status':'BINDING_MISSING','requests':0}
    (ROOT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    from bct.v4.private_state import _gpg
    sealed=Path('var/v4/quantitative/q1-source-probe');sealed.mkdir(parents=True,exist_ok=False)
    payload={p.name:base64.b64encode(p.read_bytes()).decode()for p in ROOT.glob('*.json')}
    (sealed/'result.gpg').write_bytes(_gpg(json.dumps(payload).encode(),os.environ.get('BCT_V4_STATE_PASSPHRASE','')))
    print('BCT_Q1_CREDENTIAL_CHECK_JSON='+json.dumps(result))
if __name__=='__main__':run()
