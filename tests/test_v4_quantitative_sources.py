"""Source format/security tests; synthetic examples are not real event accuracy."""
import json
from pathlib import Path
import pytest
from bct.v4 import quantitative as q,quantitative_sources as source
from bct.v4.store import sha


def meta(tmp_path,raw,source_id='census_trade'):
 p=tmp_path/'source.raw';p.write_bytes(raw)
 return {'path':str(p),'sha256':sha(raw),'source_id':source_id,'url':'https://api.census.gov/data/timeseries/intltrade/imports/hs','published_at':'UNKNOWN','acquired_at':'2026-10-15'}


def test_census_credential_column_removed_without_changing_numbers():
 key='synthetic-test-credential';raw=json.dumps([['I_COMMODITY','GEN_QY1_MO','key'],['2504101000','123',key]]).encode()
 safe,review=source.census_safe(raw,key)
 assert key.encode()not in safe
 assert json.loads(safe)==[['I_COMMODITY','GEN_QY1_MO'],['2504101000','123']]
 assert review['credential_columns_removed']==1
 with pytest.raises(ValueError,match='UNREVIEWED_CREDENTIAL'):
  source.census_safe(json.dumps([['unknown'],[key]]).encode(),key)


def test_trade_flow_money_zero_and_unknown_are_distinct(tmp_path):
 raw=json.dumps([['I_COMMODITY','GEN_QY1_MO','CON_QY1_MO','GEN_VAL_MO','UNIT_QY1','CTY_CODE','time'],
 ['2504101000','100','0','800','KG','0000','2024-01'],['2504101000','W','','900','KG','0000','2024-02']]).encode()
 rows=source.parse_trade(raw,meta(tmp_path,raw),'imports','VERIFIED_ANNUAL_CODE_UNIT')
 assert len(rows)==6 and rows[0]['measurement_type']=='PHYSICAL'
 assert rows[1]['value_decimal_or_null']=='0'and rows[1]['quality_state']=='HELD_ZERO_SEMANTICS'
 assert rows[2]['measurement_type']=='MONEY'and rows[2]['value_decimal_or_null']=='800'
 assert rows[3]['value_decimal_or_null']is None
 assert all(r['stage']=='UNKNOWN'and not r['automatic_promotion']for r in rows)
 assert all(q.verify_locator(r,raw)for r in rows)
 held=source.parse_trade(raw,meta(tmp_path,raw),'imports','UNKNOWN')
 assert held[0]['quality_state']=='HELD_CODE_REVISION_UNVERIFIED'


def test_inline_quantity_sign_scale_context_and_source_coordinates(tmp_path):
 raw=b'''<html><xbrli:context id="year"><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
 <xbrli:unit id="mw"><xbrli:measure>company:MW</xbrli:measure></xbrli:unit>
 <ix:nonFraction id="f1" name="company:ReportedCapacity" contextRef="year" unitRef="mw" scale="3" sign="-">12</ix:nonFraction>
 <ix:nonFraction name="company:SplitToken" contextRef="year" unitRef="mw">1<span>,200</span></ix:nonFraction></html>'''
 m=meta(tmp_path,raw,'sec');rows,detail=source.parse_sec_inline(raw,m,'0000000001','0000000001-26-000001')
 assert len(rows)==1 and detail['unresolved_inline_context_or_unit']==1
 r=rows[0];assert r['value_original']=='12'and r['value_decimal_or_null']=='-12'
 assert r['value_normalized_or_null']=='-12000'and r['period_start']=='2025-01-01'
 assert r['attributes']['is_actual_order']is False
 assert q.verify_locator(r,raw)


def test_pdf_code_suffix_and_multiline_unit_cannot_borrow_from_next_product():
 text='''2846.90.20              Mixtures:
             05           Lanthanum oxide....................... kg
             15           Yttrium or scandium oxide
                          continued description............... kg
8101.94.00 00             Unwrought tungsten
                          continued description............... kg...... Free
8101.96.00 00             Missing unit deliberately
8101.99.80 00             Other................................ kg...... Free
'''
 rows=source.parse_codebook_text(text,'import');by={r['code']:r for r in rows}
 assert set(by)=={'2846902005','2846902015','8101940000','8101998000'}
 assert by['2846902015']['printed_unit_line']==4
 assert '8101960000'not in by


def test_source_processor_never_has_private_writer_credential():
 import yaml
 w=yaml.safe_load((Path(__file__).resolve().parents[1]/'.github/workflows/v4-cpu-private-research.yml').read_text())
 process=w['jobs']['q1-source-process']
 assert 'BCT_V4_PRIVATE_STATE_TOKEN'not in json.dumps(process)
 assert 'BCT_SEC_USER_AGENT'in json.dumps(process)and'CENSUS_API_KEY'in json.dumps(process)
 assert w['permissions']['contents']=='read'
