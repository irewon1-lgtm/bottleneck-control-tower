"""Private persistence validates saved analysis with the publisher's stdlib only."""
import json
from pathlib import Path
import subprocess
import sys

from test_v4_cpu_review import analyzer, source, receipts, AS_OF


def test_saved_analysis_validates_and_restores_in_stdlib_only_publisher(tmp_path):
    from bct.v4.adapters import MODEL,MODEL_REVISION
    module=analyzer();assert (module.MODEL,module.MODEL_REVISION)==(MODEL,MODEL_REVISION)
    doc,raw=source();planned,results=receipts(doc)
    value=module.analyze_document(doc,planned,results,raw=raw,as_of=AS_OF)
    packet=tmp_path/'receipt.json';packet.write_text(json.dumps(value))
    code=r'''
import importlib.abc,json,pathlib,sys
sys.path.insert(0,sys.argv[1])
blocked={'yaml','bs4','sqlalchemy','requests','feedparser','lxml','pypdf','trafilatura',
         'torch','transformers','gliner','gliner2','huggingface_hub'}
class PublisherImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0]in blocked:raise AssertionError('PUBLISHER_IMPORT_'+fullname)
sys.meta_path.insert(0,PublisherImports())
from bct.v4.cpu_review import validate_receipt,FIELDS,MODEL,MODEL_REVISION
from bct.v4 import cpu_resume as resume,cpu_operations as operations
from bct.v4.store import Ledger,sha
assert (MODEL,MODEL_REVISION)==(resume.MODEL,resume.REVISION)
value=json.loads(pathlib.Path(sys.argv[2]).read_text())
assert validate_receipt(value)
for change,reason in [({'S2':1},'PROMOTION_FORBIDDEN'),
                      ({'missing_fields':['invented_field']},'REASON_INVALID'),
                      ({'body_sha256':'broken'},'SOURCE_HASH_INVALID'),
                      ({'quote':'source text must not persist'},'FIELDS_NOT_ALLOWED')]:
    bad={**value,**change}
    bad['id']='cpu-analysis-'+sha({k:v for k,v in bad.items()if k not in('id','evaluated_at','delivery')})
    try:validate_receipt(bad)
    except ValueError as error:assert reason in str(error),(reason,str(error))
    else:raise AssertionError('MALFORMED_RECEIPT_ACCEPTED')
root=pathlib.Path(sys.argv[3]);ledger=Ledger(root/'state')
with ledger.db:
    ledger.db.execute('INSERT INTO metadata VALUES(?,?)',('cpu_queue_format',resume.QUEUE))
    ledger.db.execute('INSERT INTO metadata VALUES(?,?)',('cpu_source_separated_format',resume.FORMAT))
    ledger.event('CPU_ANALYSIS_RESULT',value)
assert resume.audit(ledger)['status']=='PASS_SOURCE_SEPARATED_SCHEMA'
operations.checkpoint(ledger,root/'checkpoint');ledger.close()
proof=operations.checkpoint_storage_audit(root/'checkpoint',{},scope='private')
assert proof['status']=='PASS_PRIVATE_STORAGE_REVIEW',proof
operations.restore(root/'checkpoint',root/'restored');ledger=Ledger(root/'restored')
assert resume.audit(ledger)['status']=='PASS_SOURCE_SEPARATED_SCHEMA'
assert resume.rows(ledger.db,'CPU_ANALYSIS_RESULT')==[value]
ledger.close()
assert not blocked.intersection(sys.modules)
print(json.dumps({'receipt_valid':True,'malformed_rejected':4,'fresh_process_restore':True,
                  'third_party_modules_loaded':0,'model_calls':0}))
'''
    result=subprocess.run([sys.executable,'-I','-S','-c',code,str(Path(__file__).resolve().parents[1]/'src'),
        str(packet),str(tmp_path/'publisher')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'receipt_valid':True,'malformed_rejected':4,
        'fresh_process_restore':True,'third_party_modules_loaded':0,'model_calls':0}
