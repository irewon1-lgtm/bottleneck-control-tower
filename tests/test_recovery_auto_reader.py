from hashlib import sha256
from copy import deepcopy

from bct.recovery_auto_reader import eligible


def source(tmp_path):
    body = 'Exact retained full-source fixture.'
    digest = sha256(body.encode()).hexdigest()
    (tmp_path/(digest+'.txt')).write_text(body)
    item = {'body_status': 'FULL', 'body_sha256': digest, 'body_chars': len(body), 'url': 'https://example.test/original'}
    observations = {item['url']: {'body_status': 'FULL', 'body_sha256': digest}}
    return item, observations


def test_exact_recovered_full_can_reach_auto_reader(tmp_path):
    item, observations = source(tmp_path)
    assert eligible(item, observations, tmp_path)


def test_partial_and_corrected_former_full_are_held(tmp_path):
    item, observations = source(tmp_path)
    assert not eligible({**item, 'body_status': 'PARTIAL'}, observations, tmp_path)
    observations[item['url']]['reclassification_rule'] = 'ARTICLE_TERMINAL_ELLIPSIS_V1'
    assert not eligible(item, observations, tmp_path)


def test_missing_cache_and_unverified_origin_do_not_enable_auto_reading(tmp_path):
    item, observations = source(tmp_path)
    assert not eligible(item, {}, tmp_path)
    (tmp_path/(item['body_sha256']+'.txt')).unlink()
    assert not eligible(item, observations, tmp_path)


def test_new_source_requires_provenance_bound_to_exact_body(tmp_path):
    item, _ = source(tmp_path)
    item.update(origin_id='official-document', origin_url=item['url'], origin_publisher='official',
                provenance_verified=True, provenance_evidence={'body_sha256': item['body_sha256'],
                'verified_source_url': item['url'], 'source_identity': 'official-document'})
    assert eligible(item, {}, tmp_path)
    changed = deepcopy(item); changed['provenance_evidence']['body_sha256'] = 'a'*64
    assert not eligible(changed, {}, tmp_path)
