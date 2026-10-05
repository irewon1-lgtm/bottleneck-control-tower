import pytest
from bct.shadow_search_v2 import queries, verified_names, identifier_present, usable_url, candidate_matches


def seed():
    body = 'High Mobility Artillery Rocket System (HIMARS)'
    documents = {'a': {'body': body, 'provenance_verified': True}}
    target = {'roles': ['DEMAND'], 'references': [{'document_id': 'a',
        'quote': 'HIMARS', 'locator': {'start': body.index('HIMARS'), 'end': body.index('HIMARS') + 6}, 'definition_quote': body}]}
    return target, documents


def test_explicit_expansion_and_opposite_direction():
    t, d = seed()
    q = queries(t, d)
    assert len(q) == 3 and all('capacity OR production' in s for s in q)
    assert 'high mobility artillery rocket system' in q[0]
    t['roles'] = ['SUPPLY']
    assert all('order OR contract' in s for s in queries(t, d))


def test_no_identifier_or_namespace_injection():
    t, d = seed()
    d['a']['provenance_verified'] = False
    with pytest.raises(ValueError): verified_names(t, d)
    d['a']['provenance_verified'] = True
    with pytest.raises(ValueError): queries(t, d, [{'document_id':'a', 'quote':'Saab', 'locator':{'start':0,'end':4}}])


def test_distinct_models_and_blocked_sites():
    assert not identifier_present('Galaxy A260 phone', ['a26'])
    assert not identifier_present('Gripen C/D', ['gripen e/f'])
    assert not usable_url('https://example.com/a', {'https://example.com/a'})
    assert not usable_url('https://example.com/b', set(), {'example.com'})
    assert usable_url('https://other.example/a', set(), {'example.com'})


def test_homonymous_acronym_needs_source_context():
    t, d = seed()
    assert candidate_matches('HIMARS High Mobility Artillery Rocket System', t, d)
    assert not candidate_matches('HIMARS land records platform', t, d)
    body = 'three A26 submarines from Saab'
    d = {'a': {'body':body, 'provenance_verified':True}}
    t['references'] = [{'document_id':'a','quote':'A26','locator':{'start':6,'end':9}}]
    assert not candidate_matches('Samsung A26 phone', t, d)
    assert candidate_matches('Saab A26 submarine', t, d)
