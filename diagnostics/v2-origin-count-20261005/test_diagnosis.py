"""Synthetic isolation checks, not the fixed-corpus comparison."""
from copy import deepcopy
import pytest
from bct import precursor_v2 as v
from source_count_only import build_relaxed, retained_source_checks_failed

NOW = '2030-01-02T00:00:00+00:00'
D = 'US Agency signed firm additional orders for 100 units of manufacturer Aster model AX-1 for US contract C-1, which requires certification CERT-X, for delivery in H1 2031.'
S = 'Manufacturer Aster model AX-1 for US requires certification CERT-X; production is allocated to contract C-1 and qualification to CERT-X completes in H2 2031.'


def fixture(supply=S, extra='', distinct=False):
    bodies = [D, supply] if distinct else [D + '\n' + supply + ('\n' + extra if extra else '')]
    docs = [{'document_id': str(i), 'body': b, 'body_sha256': v.digest(b.encode()),
        'version': v.digest(b.encode()), 'origin_id': str(i),
        'origin_url': f'https://source{i}.example/article', 'origin_publisher': str(i),
        'provenance_verified': True, 'published_at': '2029-12-01T00:00:00Z',
        'publication_precision': 'TIMESTAMP', 'available_at':'2029-12-02T00:00:00Z'}
        for i, b in enumerate(bodies)]
    events = [e for doc in docs for e in v.extract(doc)]
    d = next(e for e in events if e['role']=='DEMAND')
    s = next(e for e in events if e['role']=='SUPPLY')
    kwargs = dict(documents=docs, as_of=NOW, relationships=v.relation_edges(docs), context_events=events)
    return d, s, kwargs


def compare(**kwargs):
    d, s, settings = fixture(**kwargs)
    relaxed, proof = build_relaxed()
    a = v.evaluate_pair_v2(d, s, **settings)
    b = relaxed(d, s, **settings)
    assert proof['changed_predicate_count']==1 and proof['all_other_AST_nodes_identical']
    assert a['independent']==b['independent']
    for key in a.keys() - {'reasons','state','early_eligible','decision_sha256'}:
        assert a[key]==b[key], key
    return a, b


def test_only_origin_minimum_can_change_pass():
    a, b = compare()
    assert not a['early_eligible'] and b['early_eligible']
    assert a['independent'] is False and b['independent'] is False
    assert a['reasons']==['INDEPENDENT_ORIGINS_MISSING'] and b['reasons']==[]


def test_independent_baseline_identical():
    a, b = compare(distinct=True)
    assert a==b


def test_qualification_and_time_not_relaxed():
    for supply in (S.replace('CERT-X','CERT-Y'), S.replace('H2 2031','H1 2031')):
        a, b = compare(supply=supply)
        assert not a['early_eligible'] and not b['early_eligible']


def test_requotation_not_relaxed():
    a, b = compare(supply='According to Aster, '+S)
    assert not b['early_eligible'] and 'INDEPENDENT_ORIGINS_MISSING' in b['reasons']


@pytest.mark.parametrize('extra', [
    'Manufacturer Aster model AX-1 for US is certified to CERT-X; sufficient qualified supply available in H2 2030 covers all demand for contract C-1.',
    'Manufacturer Aster model AX-1 for US requires certification CERT-X; orders for contract C-1 are postponed to H1 2032.',
    'Manufacturer Aster model AX-1 for US requires certification CERT-X; actual shortage for contract C-1 is confirmed.',
])
def test_relief_demand_change_confirmation_unchanged(extra):
    a, b = compare(extra=extra)
    assert not b['early_eligible']
    assert a['refuted']==b['refuted'] and a['prior_confirmation']==b['prior_confirmation']


def test_provenance_and_event_integrity_not_relaxed():
    d, s, kw = fixture()
    relaxed, _ = build_relaxed()
    broken = deepcopy(kw)
    broken['documents'][0]['provenance_verified'] = False
    for func in (v.evaluate_pair_v2, relaxed):
        with pytest.raises(ValueError, match='PROVENANCE_UNVERIFIED'): func(d, s, **broken)
        altered = deepcopy(d); altered['direct_origin'] = False
        with pytest.raises(ValueError, match='EVENT_NOT_AUTOMATIC_SOURCE_BOUND_EXTRACTION'):func(altered,s,**kw)


def test_duplicate_quotes_and_same_family_still_recorded():
    d, s, kw = fixture()
    duplicate = deepcopy(s); duplicate['reference']['quote'] = d['reference']['quote']
    assert retained_source_checks_failed(d, duplicate)
    assert v._independent(d,s,{x['document_id']:x for x in kw['documents']}) is False
