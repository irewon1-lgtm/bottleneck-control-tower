"""Source-bound search leads only; never supplies pair fields or provenance."""
import re
from urllib.parse import urlsplit

VERSION = 'BCT_V2_IDENTIFIER_SEARCH_1'


def normalized(value):
    return ' '.join(value.replace('®', '').split()).casefold()


def verified_names(target, documents):
    names = []
    for ref in target['references']:
        doc = documents[ref['document_id']]
        a, b = ref['locator']['start'], ref['locator']['end']
        if not doc.get('provenance_verified') or doc['body'][a:b] != ref['quote']:
            raise ValueError('UNVERIFIED_SEARCH_IDENTIFIER')
        names.append(ref['quote'])
        definition = ref.get('definition_quote')
        # An explicit expansion is a search alternative, never an inferred alias.
        if definition and definition in doc['body']:
            long = re.sub(r'\s*\([^)]*\)\s*$', '', definition)
            names.append(long)
    return list(dict.fromkeys(normalized(n) for n in names))


def queries(target, documents, namespace_refs=()):
    names = verified_names(target, documents)
    namespace = []
    for ref in namespace_refs:
        doc = documents[ref['document_id']]
        a, b = ref['locator']['start'], ref['locator']['end']
        if not doc.get('provenance_verified') or doc['body'][a:b] != ref['quote']:
            raise ValueError('UNVERIFIED_SEARCH_NAMESPACE')
        namespace.append(ref['quote'])
    if not namespace:
        namespace = namespace_hints(target, documents)
    # Short alternatives avoid requiring every acquisition hint in one page.
    direction = ('(capacity OR production OR ramp OR qualification)' if
                 'DEMAND' in target['roles'] else '(order OR contract OR purchase OR offtake)')
    anchor = ' OR '.join('"' + n.replace('"', '') + '"' for n in names)
    scope = ' '.join('"' + n.replace('"', '') + '"' for n in namespace)
    return list(dict.fromkeys([
        f'({anchor}) {scope} {direction}',
        f'({anchor}) {scope} {direction} ("press release" OR "investor relations" OR filing)',
        f'({anchor}) {scope} {direction} (site:gov OR site:sec.gov)',
    ]))


def identifier_present(text, names):
    text = normalized(text)
    return any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', text) for n in names)


def namespace_hints(target, documents):
    """Literal context for ambiguous codes; no external alias dictionary."""
    verified_names(target, documents)
    hints = []
    for ref in target['references']:
        body = documents[ref['document_id']]['body']
        definition = ref.get('definition_quote')
        if definition and definition in body:
            words = re.sub(r'\s*\([^)]*\)\s*$', '', definition).split()
            if len(words) >= 3:
                hints.append(' '.join(words[-3:]))
        a = body.rfind('\n', 0, ref['locator']['start']) + 1
        b = body.find('\n', ref['locator']['end'])
        paragraph = body[a:b if b >= 0 else len(body)]
        match = re.search(re.escape(ref['quote']) + r'\s+\w+\s+from\s+([A-Z][\w-]*)', paragraph)
        if match:
            hints.append(match[1])
    return list(dict.fromkeys(normalized(h) for h in hints))


def candidate_matches(text, target, documents):
    if not identifier_present(text, verified_names(target, documents)):
        return False
    hints = namespace_hints(target, documents)
    # Missing context is deferred, never a same-TARGET assertion.
    return not hints or identifier_present(text, hints)


def usable_url(url, failed_urls, failed_hosts=()):
    p = urlsplit(url)
    return (p.scheme == 'https' and bool(p.hostname) and not p.username and
            url not in failed_urls and p.hostname not in failed_hosts)


def priority(url):
    """Ordering only. A government or IR URL does not prove provenance."""
    p = urlsplit(url)
    if p.hostname and (p.hostname.endswith('.gov') or p.hostname.endswith('.gov.au')):
        return 0
    if re.search(r'(?:investor|/ir/|filing|newsroom|press-release|news-release)', url, re.I):
        return 1
    return 2
