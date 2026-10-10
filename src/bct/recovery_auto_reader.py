"""Exact FULL source eligibility for the released, bounded CPU worker."""
from .future_body import read_cached_body, verified_source_metadata
from .recovery_e2e import confirmed_full_observation
from .recovery_queue import corrected_version


def eligible(item, observations, cache):
    digest = item.get('body_sha256')
    if item.get('body_status') != 'FULL' or not digest:
        return False
    observation = observations.get(item.get('url'), {})
    if corrected_version(observation, digest):
        return False
    body = read_cached_body(cache, digest)
    if body is None or len(body) != item.get('body_chars'):
        return False
    return (confirmed_full_observation(item, observation)
            or verified_source_metadata(item, digest).get('provenance_verified') is True)
