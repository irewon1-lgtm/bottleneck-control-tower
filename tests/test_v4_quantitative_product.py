"""Synthetic source-review guards; not independent extraction accuracy."""
from copy import deepcopy
import pytest
from bct.v4.quantitative_product import review,save
from bct.v4.store import Ledger,sha,file_sha


def case(text='Buyer has signed a contract for the procurement of 12 Maker widgets.'):
 d={'document_id':'synthetic','body':text,'body_sha256':sha(text.encode()),'body_status':'FULL','provenance':'PASS','origin_url':'https://www.airbus.com/','published_at':'2026-10-15'}
 s={'context':text,'kind':'ACTUAL_ORDER','product':'widgets','quantity_literal':'12','unit':'widgets','customer':'Buyer','supplier':'Maker'}
 # The ordinary pattern is quantity + named product + unit, e.g. 12 ModelZ widgets.
 text=text.replace('Maker widgets','Maker ModelZ widgets');d.update(body=text,body_sha256=sha(text.encode()));s.update(context=text,product='ModelZ');return d,s


def test_exact_quantity_relation_source_date_and_idempotent_store(tmp_path):
 d,s=case();r=review(d,s);assert r['quantity']=='12'and r['s_stage']=='UNKNOWN'and r['qualified_capacity']is None
 l=Ledger(tmp_path/'research');assert save(l,[r])['added']==1;l.close();l=Ledger(tmp_path/'research');before=file_sha(l.path);assert save(l,[r])['added']==0;assert file_sha(l.path)==before;l.close()


def test_false_source_negation_money_and_output_order_are_rejected():
 for text in ['Buyer has not signed a contract for the procurement of 12 Maker widgets.',
              'Buyer has signed a contract with options for 12 Maker widgets.',
              'Buyer purchased equipment to produce 12 Maker widgets.']:
  d,s=case(text)
  with pytest.raises(ValueError):review(d,s)
 d,s=case();d['body_status']='PARTIAL'
 with pytest.raises(ValueError,match='SOURCE_BLOCKED'):review(d,s)
 d,s=case();s['quantity_literal']='13'
 with pytest.raises(ValueError,match='LITERAL'):review(d,s)
 d,s=case();s['unit']='USD'
 with pytest.raises(ValueError):review(d,s)
