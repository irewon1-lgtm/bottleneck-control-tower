"""Additive post-result pipeline diagnostic. Frozen scoring logic unchanged; no API."""
import json,pathlib,sqlite3
from collections import Counter
from bct.v4.comparison_evaluation import score_products,score_events
from bct.v4.event_evaluation import metrics
from bct.v4.store import now
R=pathlib.Path('docs/v4/path-comparison/final')
def total(xs):
 c=Counter()
 for x in xs:c.update({k:v for k,v in x.items()if type(v)is int and k not in('precision_denominator','recall_denominator')})
 return metrics(c)
def main():
 golds={x['document_id']:x for x in json.loads((R/'event-gold.json').read_text())['documents']};docs=[]
 db=sqlite3.connect('file:var/v4/path-comparison/final-events/v4.sqlite3?mode=ro',uri=True)
 for row in json.loads((R/'inputs.json').read_text())['documents']:
  did=row['document_id'];x=json.loads((R/'responses'/(did+'.json')).read_text());g=golds[did];cpu=json.loads((R/'cpu'/(did+'.json')).read_text())
  stored=[json.loads(t[0])for t in db.execute('SELECT payload FROM runs')];a=next(z for z in stored if any(r['context']['document_id']==did for r in z['records']))if any(any(r['context']['document_id']==did for r in z['records'])for z in stored)else x.get('alternative',{'records':[]})
  known={f['field']for t in g['targets']for e in t['events']for f in e['facts']if f['status']=='VERIFIED_PRESENT'}
  docs.append({'document_id':did,'packet_error_preserved':x.get('packet_error'),'alternate_already_stored_records':len(a['records']),'CPU_products':score_products([{'product':{'surface':s['text']}}for s in cpu.get('spans',[])if s['label']=='product'],g),'alternative_products':score_products(a['records'],g),'alternative_events':score_events(a['records'],g),'alternative_counts':a.get('counts'), 'known_reviewed_fields':sorted(known)})
 out={'at':now(),'scope':'Additive full6 pipeline diagnostic, not replacement of frozen scores. One legacy FORMAT packet failure remains failure; alternative had already saved its records before legacy threw. No response/gold/code change or new calls. Unknown DEMAND_DECREASE remains discovery only. CPU/gold/model same6 inputs.','frozen_primary_comparison_documents':5,'all6_diagnostics':{k:total(x[k]for x in docs)for k in('CPU_products','alternative_products','alternative_events')},'documents':docs}
 (R/'packet-isolation-diagnostic.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['all6_diagnostics']))
if __name__=='__main__':main()
