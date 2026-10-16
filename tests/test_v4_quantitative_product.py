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


def test_received_order_preserved_with_unknown_physical_quantity_and_planned_shipping():
 text='Maker today announced a $22 million production order from Buyer.\nThe order includes multiple ModelZ equipment units. Maker expects to ship over the next six months.'
 d={'document_id':'synthetic-unknown','body':text,'body_sha256':sha(text.encode()),'body_status':'FULL','provenance':'PASS','origin_url':'https://www.airbus.com/synthetic'}
 s={'context':text,'kind':'ACTUAL_ORDER_QUANTITY_UNKNOWN','product':'ModelZ equipment','customer':'Buyer','planned_delivery':'over the next six months'}
 r=review(d,s);assert r['quantity']is None and r['unit']is None and r['actuality']=='ACTUAL'and r['need_window']is None and r['qualified_capacity']is None
 for replacement in ['expected production order','planned production order']:
  t=text.replace('production order',replacement);d.update(body=t,body_sha256=sha(t.encode()));s['context']=t
  with pytest.raises(ValueError,match='UNCONFIRMED'):review(d,s)
 t=text.replace('multiple ModelZ equipment units','equipment to produce ModelZ equipment units');d.update(body=t,body_sha256=sha(t.encode()));s['context']=t
 with pytest.raises(ValueError,match='OBJECT_UNKNOWN'):review(d,s)


def test_order_for_equipment_is_retained_but_output_and_currency_are_not_quantity():
 text='Maker announced it has received a $8 million order from Buyer for a fully automated ModelQ test system.\nThe system is expected to ship during the first half of 2027.'
 d={'document_id':'synthetic-new-industry','body':text,'body_sha256':sha(text.encode()),'body_status':'FULL','provenance':'PASS','origin_url':'https://maker.example/order'}
 s={'context':text,'kind':'ACTUAL_ORDER_QUANTITY_UNKNOWN','product':'ModelQ test system','customer':'Buyer','planned_delivery':'the first half of 2027'}
 r=review(d,s)
 assert r['quantity']is None and r['unit']is None and r['need_window']is None and r['qualified_capacity']is None
 for clause in ['equipment to produce ','chips made using ','a plant with ']:
  bad=text.replace('a fully automated ModelQ',clause+'ModelQ');d.update(body=bad,body_sha256=sha(bad.encode()));s['context']=bad
  with pytest.raises(ValueError,match='OBJECT_UNKNOWN'):review(d,s)


def test_plural_order_and_scheduled_delivery_remain_supplier_plan_not_customer_need():
 text='Maker announced production orders from Buyer.\nThe orders include ModelQ equipment. Deliveries under the order are scheduled over the next six months.'
 d={'document_id':'synthetic-plural','body':text,'body_sha256':sha(text.encode()),'body_status':'FULL','provenance':'PASS','origin_url':'https://maker.example/order'}
 s={'context':text,'kind':'ACTUAL_ORDER_QUANTITY_UNKNOWN','product':'ModelQ equipment','planned_delivery':'next six months'}
 r=review(d,s);assert r['actuality']=='ACTUAL'and r['need_window']is None and r['quantity']is None
