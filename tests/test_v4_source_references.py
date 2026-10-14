"""Development-authored examples; never independent accuracy evidence."""
from copy import deepcopy
import json
import pytest
from bct.v4.free_ai import HTTPAdapter, source_input, validate_reading
from bct.v4.store import encode
from bct.v4.public_input import review_native, selected_input
from test_v4_free_ai import config, document, response
from test_v4_repair import native


def cfg():
 c=config();c.update(response_protocol='context-reference-v1',input_policy='sentence-context-v3',max_input_characters=1200)
 return c


def item(entity='NovaLT16', role='DEMAND_INCREASE', facts=None, context_id='w0'):
 return {'context_id':context_id,'entity':entity,'kind':'PHYSICAL_PRODUCT','role':role,'actuality':'ACTUAL','facts':facts or []}


def read(body, proposal):
 d=document(body);s=source_input(d,cfg(),{});return validate_reading(encode({'items':proposal}),d,s)


def test_repeated_name_uses_exact_full_context_without_approving_legacy_short_quotes():
 body='Atlas received an order for NovaLT16. NovaLT16 production remains planned.'
 d=document(body);s=source_input(d,cfg(),{});r=validate_reading(encode({'items':[item()]}),d,s)
 assert len(r['items'])==1 and r['items'][0]['entity']['quote']==body
 assert r['items'][0]['evidence_origin']=='MODEL_CONTEXT_ID_RESOLVED_TO_EXACT_INPUT_WINDOW'
 old=json.loads(response(d)['text']);old['items'][0]['entity']['quote']='NovaLT16'
 legacy=source_input(d,config(),{})
 assert validate_reading(encode(old),d,legacy)['rejected_items'][0]['reason']=='AMBIGUOUS_QUOTE'


@pytest.mark.parametrize('entity,field,value,reason',[
 ('missing','quantity','four','VALUE_NOT_LITERAL'),
 ('NovaLT16','quantity','4','VALUE_NOT_LITERAL'),
 ('Nova','quantity','four','PRODUCT_TOKEN_BOUNDARY'),
 ('four NovaLT16','quantity','four','COUNT_IN_PRODUCT_IDENTITY')])
def test_nonliteral_numbers_partial_names_and_count_identities_stay_rejected(entity,field,value,reason):
 r=read('Atlas received an order for four NovaLT16 turbines.',[item(entity,facts=[{'field':field,'value':value}])])
 assert not r['items'] and r['rejected_items'][0]['reason']==reason


def test_unknown_context_id_never_searches_other_or_unread_source():
 r=read('Atlas received an order for NovaLT16.',[item(context_id='w3')])
 assert not r['items'] and r['rejected_items'][0]['reason']=='QUOTE_NOT_IN_SOURCE'


def test_fact_from_other_window_is_not_adopted_for_chosen_context():
 d=document('Atlas received an order for NovaLT16.\nBeta expanded production of Zeta cells to 400 units.')
 s=source_input(d,cfg(),{})
 first=next(i for i,w in enumerate(s['windows']) if 'NovaLT16' in w['text'])
 r=validate_reading(encode({'items':[item(context_id='w'+str(first),facts=[{'field':'quantity','value':'400'}])]}),d,s)
 assert not r['items'] and r['rejected_items'][0]['reason']=='VALUE_NOT_LITERAL'


def test_duplicate_fact_fields_are_rejected_not_merged():
 r=read('Atlas received an order for four NovaLT16 turbines.',[item(facts=[{'field':'quantity','value':'four'}]*2)])
 assert not r['items'] and r['rejected_items'][0]['reason']=='SOURCE'


def test_literal_written_number_is_preserved_without_numeric_conversion():
 r=read('Atlas received an order for four NovaLT16 turbines.',[item(facts=[{'field':'quantity','value':'four'},{'field':'unit','value':'turbines'}])])
 x=r['items'][0];assert x['facts'][0]['value']=='four' and x['facts'][1]['value']=='turbines'
 assert x['s_stage']=='UNKNOWN' and not x['forecast_candidate']


@pytest.mark.parametrize('entity,body,wanted,role,actuality',[
 ('NovaLT16','Atlas received an order for four NovaLT16 turbines. It will expand production next year.','SUPPLY_INCREASE','DEMAND_INCREASE','ACTUAL'),
 ('gas turbines','Atlas received orders for gas turbines.','SUPPLY_INCREASE','DEMAND_INCREASE','ACTUAL'),
 ('battery cells','Beta production of battery cells decreased in June.','SUPPLY_DECREASE','SUPPLY_DECREASE','ACTUAL'),
 ('transformers','Beta delivery of transformers was delayed.','SUPPLY_DELAY','SUPPLY_DELAY','ACTUAL'),
 ('lasers','Beta lead times for lasers shortened.','SUPPLY_DELAY','RELIEF','ACTUAL'),
 ('chips','Beta did not expand production of chips.','SUPPLY_INCREASE','UNKNOWN','NEGATED'),
 ('pumps','Beta plans to increase production of pumps.','SUPPLY_INCREASE','SUPPLY_INCREASE','PLAN'),
 ('reactors','Beta received government funding for reactors.','SUPPLY_INCREASE','UNKNOWN','ACTUAL')])
def test_cross_industry_product_and_actual_event_roles(entity,body,wanted,role,actuality):
 r=read(body,[item(entity,wanted)]);x=r['items'][0]
 assert x['physical_exploration_lead'] and x['role']==role and x['actuality']==actuality
 assert not x['forecast_candidate']


def test_reference_protocol_has_smaller_payload_and_same_free_run_cap():
 s=source_input(document('Atlas received an order for NovaLT16.'),cfg(),{})
 url,headers,p=HTTPAdapter({}).request('groq',s,2048)
 assert url=='https://api.groq.com/openai/v1/chat/completions'
 m=json.loads(p['messages'][1]['content']);assert m['contexts'][0]['context_id']=='w0'
 assert 'start' not in p['response_format']['json_schema']['schema']['properties']['items']['items']['properties']
 assert len(encode(p).encode())+2048<6400
 assert p['max_completion_tokens']==2048 and p['model']=='openai/gpt-oss-20b'


def test_long_development_input_covers_more_without_cutting_counterevidence():
 body='Atlas received an order for NovaLT16 turbines.\n'+'It will manufacture the equipment for delivery in 2028. '+('The equipment has detailed technical specifications. '*10)+'\nHowever, qualified alternate supply covers all demand.'
 d,raw,row=native(body);review=review_native(d,raw,row)
 old={**cfg(),'input_policy':'sentence-context-v2','max_input_characters':600}
 new={**cfg(),'input_policy':'sentence-context-v3'}
 with pytest.raises(ValueError,match='NO_COMPLETE_SAFE'):
  selected_input(d,old,review,{})
 b=selected_input(d,new,review,{})
 assert 600<b['selected_characters']<=1200
 assert any('However,' in w['text'] and 'It will' in w['text'] for w in b['windows'])
 for w in b['windows']:assert d['body'][w['start']:w['end']]==w['text']
 assert b['coverage']!='FULL_DOCUMENT'


def test_unrelated_public_document_is_read_not_hidden_by_signal_prefilter():
 d,raw,row=native('The board announced the appointment of an independent director.')
 review=review_native(d,raw,row)
 s=selected_input(d,cfg(),review,{})
 assert any('independent director' in w['text'] for w in s['windows'])
 assert s['selected_characters']>0


def test_duplicate_entire_context_still_has_no_arbitrary_approved_position():
 d=document('Atlas ordered NovaLT16.\nAtlas ordered NovaLT16.')
 s=source_input(d,cfg(),{})
 r=validate_reading(encode({'items':[item()]}),d,s)
 assert not r['items'] and r['rejected_items'][0]['reason']=='AMBIGUOUS_QUOTE'
