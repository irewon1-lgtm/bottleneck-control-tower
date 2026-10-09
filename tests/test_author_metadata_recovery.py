from copy import deepcopy

import pytest

from bct.future_body import extract_document, is_author_metadata_only_body, is_video_summary_body
from bct.recovery_pilot import quarantine_corrected_readings, resume_batches
from bct.recovery_sources import restore_observations
from bct.future_body import cache_body
from test_recovery_pilot import fixture
import json


BIO = ('Reporter Name\nReporter writes, edits and produces the news articles and newsletters.\n'
       'Featured Products\nPrevious Article\nOther title\nNext Article\nAnother title')


def test_canonical_article_prose_inside_share_wrapper_is_not_author_footer():
    html = '''<html><head><link rel="canonical" href="https://www.semiconductor-digest.com/example/"></head>
    <body class="single-post wp-theme-goodlife-wp"><article data-url="https://www.semiconductor-digest.com/example/">
    <div class="share-container"><div class="post-content-container"><div class="post-content entry-content cf">
    <p>Demand for qualified packaging will grow in 2027.</p><p>The approved line will be ready in 2028.</p>
    </div></div><button>Share Article</button></div><p>Reporter profile.</p></article></body></html>'''
    result = extract_document(html)
    assert result['body_status'] == 'FULL' and result['extraction_method'] == 'PUBLISHER_BODY'
    assert result['body'] == 'Demand for qualified packaging will grow in 2027.\nThe approved line will be ready in 2028.'
    # Neither another canonical nor an ambiguous duplicate establishes scope.
    mismatch = html.replace('data-url="https://www.semiconductor-digest.com/example/"',
                            'data-url="https://www.semiconductor-digest.com/other/"')
    assert extract_document(mismatch)['extraction_method'] != 'PUBLISHER_BODY'


def test_author_only_full_is_held_without_erasing_cache_or_retrying_unchanged(tmp_path):
    assert is_author_metadata_only_body(BIO)
    assert not is_author_metadata_only_body('Actual article prose.\n' + BIO)
    digest = cache_body(tmp_path/'private-source-cache', BIO)
    original = {'url':'https://publisher.test/article','attempted':True,'body_status':'FULL',
                'status':'FULL','body_sha256':digest}
    (tmp_path/'source-recovery-attempts.jsonl').write_text(json.dumps(original)+'\n')
    observed, pending = restore_observations(tmp_path, tmp_path/'restored')
    row = observed[original['url']]
    assert not pending and row['body_status'] == 'PARTIAL'
    assert row['prior_observation_classification']['body_sha256'] == digest
    assert (tmp_path/'restored'/(digest+'.txt')).read_text() == BIO
    with pytest.raises(ValueError, match='changed code'):
        restore_observations(tmp_path, tmp_path/'next', reinspect_urls=[original['url']])
    _, pending = restore_observations(tmp_path, tmp_path/'next', retry_errors=True,
                                      reinspect_urls=[original['url']])
    assert pending[original['url']]['reclassification_rule'] == 'AUTHOR_METADATA_ONLY_V1'


def test_only_exact_corrected_drain_receipts_are_quarantined_with_full_history():
    p, items, config = fixture()
    p.update(mode='DRAIN',batches=[{'limit':5,'actual_model_calls':3,'status':'RUNNING',
                                 'results':p['batches'][0]['results']+p['batches'][1]['results']}])
    original = deepcopy(p)
    corrections={('1','1'):{'body_sha256':'1','reclassification_rule':'AUTHOR_METADATA_ONLY_V1'},
                 ('2','2'):{'body_sha256':'2','reclassification_rule':'AUTHOR_METADATA_ONLY_V1'}}
    resumable, held = quarantine_corrected_readings(p, corrections)
    assert p == original and [h['result'] for h in held] == original['batches'][0]['results'][1:]
    assert len(resume_batches(resumable,[items[0],*items[3:]],config,limits=(5,))[0]['results']) == 1
    corrections[('1','1')]['body_sha256']='another-hash'
    with pytest.raises(ValueError,match='exact source correction'):
        quarantine_corrected_readings(p,corrections)
    p['mode']='QUALIFICATION'
    with pytest.raises(ValueError,match='exact source correction'):
        quarantine_corrected_readings(p,{('2','2'):corrections[('2','2')]})


def test_video_synopsis_preserves_partial_text_but_never_claims_full_transcript():
    body='DCD Studio: Infrastructure interview\nA synopsis of the recorded interview.\nTags\nAI\nComments'
    url='https://www.datacenterdynamics.com/en/videos/interview/'
    assert is_video_summary_body(body,url)
    assert not is_video_summary_body(body,url.replace('/videos/','/news/'))
    assert not is_video_summary_body(body+'\nTranscript\nFull conversation.',url)
    html=f'<link rel="canonical" href="{url}"><article>'+''.join(f'<p>{s}</p>' for s in body.splitlines())+'</article>'
    result=extract_document(html)
    assert result['body_status']=='PARTIAL' and result['body']==body
    assert 'VIDEO_SUMMARY_WITHOUT_TRANSCRIPT' in result['reasons']


def test_breaking_defense_video_episode_and_related_cards_are_not_a_full_article(tmp_path):
    body = '\n'.join([
        'In this episode of The Pentagon Buzz, the host introduces the topic.',
        'Breaking Defense Video',
        'First related video', 'Watch Now »',
        'Second related video', 'Watch Now »',
        'Third related video', 'Watch Now »',
        'Scroll for more video',
    ])
    url = 'https://breakingdefense.com/2026/10/example-video/'
    assert is_video_summary_body(body, url)
    assert not is_video_summary_body(body.replace('Scroll for more video', 'Article conclusion.'), url)
    assert not is_video_summary_body(body + '\nTranscript\nFull conversation.', url)
    html = f'<link rel="canonical" href="{url}"><article>' + ''.join(
        f'<p>{line}</p>' for line in body.splitlines()) + '</article>'
    result = extract_document(html)
    assert result['body_status'] == 'PARTIAL'
    assert result['body'] == body
    assert 'VIDEO_SUMMARY_WITHOUT_TRANSCRIPT' in result['reasons']

    digest = cache_body(tmp_path / 'private-source-cache', body)
    original = {'url': url, 'attempted': True, 'body_status': 'FULL',
                'status': 'FULL', 'body_sha256': digest}
    (tmp_path / 'source-recovery-attempts.jsonl').write_text(
        json.dumps(original) + '\n')
    observed, pending = restore_observations(tmp_path, tmp_path / 'restored')
    assert not pending
    assert observed[url]['body_status'] == 'PARTIAL'
    assert (observed[url]['reclassification_rule'] ==
            'VIDEO_SUMMARY_WITHOUT_TRANSCRIPT_V1')
    assert observed[url]['prior_observation_classification']['body_sha256'] == digest
