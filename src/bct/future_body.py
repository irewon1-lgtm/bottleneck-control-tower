"""Small body extraction and private runtime cache for the future sidecar.

FULL describes structurally complete accessible content, not a minimum length.
Nothing in this module fetches around a challenge, login or paywall.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
import socket
import ssl
from urllib.error import HTTPError, URLError


def access_failure(exc):
    """Keep environment/HTTP failures distinct; never infer absent source text."""
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(exc, HTTPError):
        status = exc.code
        retry = (exc.headers or {}).get('Retry-After')
        retry = retry if retry and retry.isdigit() else None
        state = ('SOURCE_WAIT' if status == 429 or status >= 500 else
                 'UNAVAILABLE' if status in (404, 410) else 'SOURCE_BLOCKED')
        return {'category': 'HTTP_' + str(status), 'http_status': status,
                'state': state, 'retryable': status == 429 or status >= 500,
                'retry_after_seconds': int(retry) if retry else None}
    if isinstance(reason, socket.gaierror):
        return {'category': 'DNS_RESOLUTION_FAILED', 'state': 'SOURCE_WAIT',
                'retryable': reason.errno == socket.EAI_AGAIN, 'dns_errno': reason.errno}
    if isinstance(reason, ssl.SSLError):
        return {'category': 'TLS_FAILED', 'state': 'SOURCE_BLOCKED', 'retryable': False}
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return {'category': 'TIMEOUT', 'state': 'SOURCE_WAIT', 'retryable': True}
    if isinstance(reason, ConnectionError) or isinstance(exc, URLError):
        return {'category': 'CONNECTION_FAILED', 'state': 'SOURCE_WAIT', 'retryable': True}
    known = str(exc) if isinstance(exc, ValueError) and str(exc) in (
        'BODY_TOO_LARGE', 'NON_PUBLIC_URL', 'INVALID_URL') else None
    return {'category': 'COLLECTOR_ERROR', 'state': 'ERROR', 'retryable': False,
            'error_type': type(exc).__name__, 'error_code': known}


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "menu"}
_CHALLENGE = re.compile(r"verify (?:that )?you are human|enable javascript and cookies|checking your browser|access denied|just a moment|captcha verification", re.I)
_PREVIEW = re.compile(r"\b(?:subscribe|sign in|log in|register)\b.{0,90}\b(?:continue reading|read (?:the )?(?:full|rest)|access (?:the )?(?:full|article))\b|\b(?:continue reading|read (?:the )?full article)\b.{0,90}\b(?:subscribe|sign in|log in|register)\b", re.I)
_SUBSCRIBER_ACCESS = re.compile(r"\bsubscriber\s+access\b", re.I)
_ACCESS_NOTICE = re.compile(r"\b(?:for|to)\s+(?:uninterrupted|full|continued)\s+access\b.{0,100}\b(?:sign\s+in|log\s+in|subscribe|upgrade)\b", re.I)
_MEDIA_SUMMARY = re.compile(r"\bthis\s+(?:summary|(?:text|article|post)\s+is\s+(?:a\s+)?summary)\b.{0,240}\b(?:full|complete)\s+(?:interview|conversation|episode)\b.{0,100}\b(?:video|podcast|audio)\b", re.I)
_TABLE_REF = re.compile(r"\b(?:table (?:below|above|\d+)|(?:following|below|above) table|see (?:the )?table)\b", re.I)
_NOISE_CLASS = re.compile(r"(?:^|[\s_-])(?:advert|advertisement|ad-slot|related|recommended|cookie|social|share|navigation|breadcrumb)(?:$|[\s_-])", re.I)
_PREVIEW_CLASS = re.compile(r"(?:^|[\s_-])(?:preview|teaser|excerpt|summary|paywall|subscriber-only)(?:$|[\s_-])", re.I)
_BODY_CLASS = re.compile(r"(?:article|story|entry|post)[-_ ]?(?:body|content|text)|body[-_ ]?copy", re.I)


def _plain(text):
    return " ".join(unescape(str(text)).split())


class _Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children, self.closed = tag, dict(attrs or ()), [], False


class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        # Recover the common optional HTML closing tags without joining blocks.
        if tag in {"p", "li", "td", "th", "tr"} and self.stack[-1].tag == tag:
            self.stack.pop().closed = True
        node = _Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag in _VOID:
            node.closed = True
        else:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                for node in self.stack[i:]:
                    node.closed = True
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _nodes(node):
    yield node
    for child in node.children:
        if isinstance(child, _Node):
            yield from _nodes(child)


def _skipped(node):
    label = " ".join(str(node.attrs.get(k, "")) for k in ("class", "id", "role"))
    return (node.tag in _SKIP or "hidden" in node.attrs
            or node.attrs.get("aria-hidden") == "true" or bool(_NOISE_CLASS.search(label)))


def _text(node, *, include_script=False):
    if not include_script and _skipped(node):
        return ""
    return _plain(" ".join(c if isinstance(c, str) else _text(c, include_script=include_script)
                           for c in node.children))


def _blocks(node):
    if _skipped(node):
        return []
    if node.tag == "tr":
        cells = [_text(c) for c in node.children if isinstance(c, _Node) and c.tag in {"td", "th"}]
        return [" | ".join(cells)] if any(cells) else []
    if node.tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd", "caption", "blockquote"}:
        text = _text(node)
        return [text] if text else []
    out, direct = [], []
    for child in node.children:
        if isinstance(child, str):
            direct.append(child)
        elif child.tag in {"span", "a", "b", "strong", "i", "em", "sup", "sub", "code", "br"}:
            direct.append(_text(child))
        else:
            if _plain(" ".join(direct)):
                out.append(_plain(" ".join(direct)))
            direct = []
            out.extend(_blocks(child))
    if _plain(" ".join(direct)):
        out.append(_plain(" ".join(direct)))
    return out


def _visible_nodes(node):
    if _skipped(node):
        return
    yield node
    for child in node.children:
        if isinstance(child, _Node):
            yield from _visible_nodes(child)


def _json_articles(value):
    if isinstance(value, dict):
        kinds = value.get("@type", [])
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if any(isinstance(k, str) and ("Article" in k or "Posting" in k) for k in kinds):
            yield value
        for child in value.values():
            yield from _json_articles(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_articles(child)


def extract_document(html, *, http_status=200, content_type="text/html"):
    """Return accessible text, a completeness state and auditable reasons."""
    if not isinstance(html, str):
        raise TypeError("HTML must be text")
    doc = _Document()
    doc.feed(html)
    doc.close()
    nodes = list(_nodes(doc.root))
    visible = _text(doc.root)
    titles = " ".join(_text(n) for n in nodes if n.tag == "title")
    reasons = []
    articles = []
    for node in nodes:
        if node.tag == "script" and node.attrs.get("type", "").lower() == "application/ld+json":
            try:
                articles.extend(_json_articles(json.loads(_text(node, include_script=True))))
            except (ValueError, RecursionError):
                pass
    paywall = any(a.get("isAccessibleForFree") in (False, "false", "False") for a in articles)
    paywall = paywall or bool(_PREVIEW.search(visible))
    # A publisher's subscriber-access notice can sit outside its closed preview
    # article. Generic newsletter or sign-in UI alone does not establish a wall.
    paywall = paywall or bool(_SUBSCRIBER_ACCESS.search(visible) and _ACCESS_NOTICE.search(visible))
    visible_nodes = list(_visible_nodes(doc.root))
    paywall = paywall or any(re.search(r"(?:^|[\s_-])(?:paywall|subscriber-only|subscription-required)(?:$|[\s_-])",
                                      str(n.attrs.get("class", "")), re.I) for n in visible_nodes)
    scopes = [n for n in visible_nodes if n.tag == "article" or n.attrs.get("itemprop") == "articleBody"
              or _BODY_CLASS.search(str(n.attrs.get("class", "")))]
    method = "ARTICLE"
    if not scopes:
        scopes = [n for n in visible_nodes if n.tag == "main"]
        method = "MAIN"
    # A nested article body is preferable to a wrapper containing related links.
    bodies = [(n, _blocks(n)) for n in scopes if not _skipped(n)]
    node, blocks = max(bodies, key=lambda x: sum(len(s) for s in x[1]), default=(None, []))
    body = "\n".join(blocks)
    status = "FULL"
    if http_status in (401, 403, 429) or http_status >= 400:
        status, body, reasons = "UNAVAILABLE", "", [f"HTTP_{http_status}"]
    elif content_type.split(";", 1)[0].lower() not in {"text/html", "application/xhtml+xml"}:
        status, body, reasons = "UNAVAILABLE", "", ["UNSUPPORTED_CONTENT_TYPE"]
    elif _CHALLENGE.search(titles) or (_CHALLENGE.search(visible) and (
            not body or re.match(r'\s*(?:verify (?:that )?you are human|access denied|checking your browser|just a moment|enable javascript and cookies|captcha verification)\b', body, re.I))):
        status, body, reasons = "UNAVAILABLE", "", ["ACCESS_CHALLENGE"]
    else:
        # Do not substitute hidden JSON-LD content for a subscriber preview.
        json_bodies = [a["articleBody"] for a in articles if isinstance(a.get("articleBody"), str)]
        if not body and json_bodies and not paywall:
            body = max((_plain(re.sub(r"<[^>]+>", " ", b)) for b in json_bodies), key=len)
            method = "JSON_LD"
        if not body:
            body = "\n".join(_blocks(doc.root))
            method = "UNSCOPED"
            status = "PARTIAL"
            reasons.append("UNVERIFIED_BODY_SCOPE")
        if not body or not re.search(r"[\w\uac00-\ud7a3]", body):
            status, body, reasons = "UNAVAILABLE", "", ["NO_READABLE_BODY"]
        elif method != "JSON_LD":
            substantive = [n for n in _nodes(node or doc.root) if n.tag in {"p", "li", "td", "dd", "blockquote"}
                           and not _skipped(n) and _text(n)]
            direct_text = bool(node and any(isinstance(c, str) and _plain(c) for c in node.children))
            scoped_unstructured = bool(node and body and len(body) >= 200 and not substantive and not direct_text)
            if scoped_unstructured:
                # Some publishers render article prose in nested div/span blocks
                # without semantic p/li tags. Keep the visible text as PARTIAL
                # rather than discarding it, but never call it complete.
                status = "PARTIAL"
                reasons.append("UNSTRUCTURED_ARTICLE_TEXT")
            elif not substantive and not direct_text:
                status, body, reasons = "UNAVAILABLE", "", ["NO_ARTICLE_CONTENT"]
            elif node and not node.closed:
                status = "PARTIAL"
                reasons.append("TRUNCATED_BODY_STRUCTURE")
        if body and paywall:
            status = "PARTIAL"
            reasons.append("PAYWALL_OR_LOGIN_PREVIEW")
        if body and node and any(_PREVIEW_CLASS.search(str(n.attrs.get("class", "")))
                                 for n in _nodes(node)):
            status = "PARTIAL"
            reasons.append("PREVIEW_OR_SUMMARY_CONTENT")
        if body and _MEDIA_SUMMARY.search(body):
            status = "PARTIAL"
            reasons.append("MEDIA_SUMMARY_NOT_FULL_CONTEXT")
        tables = [n for n in _nodes(node or doc.root) if n.tag == "table" and not _skipped(n)]
        table_rows = sum(1 for t in tables for n in _nodes(t) if n.tag == "tr" and _blocks(n))
        if body and (any(not any(n.tag in {"td", "th"} and _text(n) for n in _nodes(t)) for t in tables)
                     or (_TABLE_REF.search(body) and not table_rows)):
            status = "PARTIAL"
            reasons.append("MISSING_TABLE_CONTENT")
    table_rows = sum(1 for n in _nodes(node or doc.root) if n.tag == "tr" and _blocks(n)) if body else 0
    return {"body_status": status, "body": body,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest() if body else None,
            "body_chars": len(body), "extraction_method": method,
            "reasons": list(dict.fromkeys(reasons)),
            "completeness": {"explicit_body_scope": node is not None or method == "JSON_LD",
                             "body_scope_closed": bool(node and node.closed) or method == "JSON_LD",
                             "captured_table_rows": table_rows,
                             "assessment": "ACCESSIBLE_STRUCTURE_ONLY"}}


def _cache_path(cache_dir, digest):
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    return Path(cache_dir) / (digest + ".txt")


def cache_body(cache_dir, body):
    """Cache full text only in a private local runtime directory."""
    digest = hashlib.sha256(body.encode()).hexdigest()
    directory = Path(cache_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = _cache_path(directory, digest)
    if path.exists() and not path.is_symlink() and path.read_text(encoding="utf-8") == body:
        return digest
    fd, temp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
    return digest


def read_cached_body(cache_dir, digest):
    path = _cache_path(cache_dir, digest)
    if path is None or not path.is_file() or path.is_symlink():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return text if hashlib.sha256(text.encode()).hexdigest() == digest else None


SOURCE_FIELDS = frozenset({'origin_id', 'origin_url', 'origin_publisher', 'provenance_verified',
    'provenance_evidence', 'published_at', 'publication_precision', 'publication_verified',
    'publication_evidence', 'available_at', 'public_snapshot_observed_at'})


def verified_source_metadata(source, body_sha256):
    """Preserve only explicit verification bound to this body snapshot."""
    out = {}
    if not body_sha256:
        return out
    evidence = source.get('provenance_evidence') or {}
    if (source.get('provenance_verified') is True and isinstance(evidence, dict)
            and evidence.get('body_sha256') == body_sha256
            and evidence.get('verified_source_url') == source.get('origin_url')
            and evidence.get('source_identity')
            and all(source.get(k) not in (None, '', 'UNKNOWN') for k in
                    ('origin_id', 'origin_url', 'origin_publisher'))):
        out.update({k: deepcopy(source[k]) for k in
                    ('origin_id', 'origin_url', 'origin_publisher', 'provenance_verified', 'provenance_evidence')})
    publication = source.get('publication_evidence') or {}
    if (source.get('publication_verified') is True and isinstance(publication, dict)
            and publication.get('body_sha256') == body_sha256 and publication.get('source_quote')
            and source.get('publication_precision') in ('DATE', 'TIMESTAMP')
            and source.get('published_at') not in (None, '', 'UNKNOWN')):
        out.update({k: deepcopy(source[k]) for k in
                    ('published_at', 'publication_precision', 'publication_verified', 'publication_evidence')})
    for k in ('available_at', 'public_snapshot_observed_at'):
        if k in source and out:
            out[k] = deepcopy(source[k])
    return out


def discovery_document(record, body):
    """Project verified snapshot metadata for the common discovery path."""
    digest = hashlib.sha256(body.encode()).hexdigest()
    if digest != (record.get('current_body_sha256') or record.get('body_sha256')):
        raise ValueError('discovery snapshot hash mismatch')
    source = {**record, **record.get('versions', {}).get(digest, {})}
    metadata = verified_source_metadata(source, digest)
    return {'document_id': record['id'], 'body': body, 'body_sha256': digest,
            'origin_id': metadata.get('origin_id'), 'origin_url': metadata.get('origin_url'),
            'origin_publisher': metadata.get('origin_publisher'),
            'provenance_verified': metadata.get('provenance_verified') is True,
            'published_at': metadata.get('published_at'),
            'publication_precision': metadata.get('publication_precision', 'UNKNOWN'),
            'available_at': metadata.get('available_at') or source.get('available_at'),
            'public_snapshot_observed_at': metadata.get('public_snapshot_observed_at') or source.get('public_snapshot_observed_at')}


def public_metadata(result, *, redistribution_allowed=False):
    """Exclude arbitrary article full text from public sidecars by default."""
    allowed = {"body_status", "body_sha256", "body_chars", "extraction_method", "reasons", "completeness", "acquisition_status", "access_diagnostic"}
    source = result.get("metadata", result)
    out = {k: deepcopy(v) for k, v in source.items() if k in allowed}
    out.update(verified_source_metadata(source, source.get('body_sha256')))
    out["cache_access"] = "PRIVATE_RUNTIME"
    out["reproducibility_limit"] = "PRIVATE_CACHE_NOT_DURABLE_REACCESS_REQUIRED_IF_LOST"
    if redistribution_allowed is True:
        body = result.get("body", source.get("body"))
        if isinstance(body, str):
            out["body"] = body
            out["redistribution_allowed"] = True
    return out


def _utc(value):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def acquire_document(url, source_version, prior, cache_dir, fetcher, *, trigger="AUTO", trigger_id=None, now=None):
    """Acquire without resetting automatic retries or erasing explicit checks.

    AUTO allows at most three attempts per source version. USER and SCHEDULED
    checks allow one acquisition per explicit unique request/schedule ID and are
    separately counted, even after automatic retries are exhausted.
    """
    if trigger == "FILTER_CHANGE":
        trigger = "FILTER_CHANGED"
    if trigger not in {"AUTO", "FILTER_CHANGED", "USER", "SCHEDULED"}:
        raise ValueError("unknown acquisition trigger")
    if trigger in {"USER", "SCHEDULED"} and not trigger_id:
        raise ValueError("an explicit check needs a stable trigger_id")
    if not isinstance(source_version, str) or not source_version:
        raise ValueError("source_version is required")
    now = _utc(now)
    ledger = deepcopy(prior or {})
    versions = ledger.setdefault("versions", {})
    version = versions.setdefault(source_version, {"automatic_attempts": 0, "explicit_checks": {}, "history": []})
    latest = version.get("latest", {})
    cached = read_cached_body(cache_dir, latest.get("body_sha256"))
    blocked = None
    if trigger == "FILTER_CHANGED":
        blocked = None if cached is not None else "CACHE_UNAVAILABLE"
    elif trigger == "AUTO":
        if cached is not None and latest.get("body_status") == "FULL":
            blocked = "FULL_CACHE_REUSED"
        elif version.get("automatic_attempts", 0) >= 3:
            blocked = "RETRY_LIMIT"
        elif version.get("next_retry_at") and _utc(version["next_retry_at"]) > now:
            blocked = "RETRY_NOT_DUE"
    elif str(trigger_id) in version.get("explicit_checks", {}):
        blocked = "EXPLICIT_CHECK_ALREADY_USED"
    if trigger == "FILTER_CHANGED" or blocked:
        return {"body": cached or "", "metadata": deepcopy(latest), "ledger": ledger,
                "acquired": False, "cache_reused": cached is not None,
                "blocked": None if blocked == "FULL_CACHE_REUSED" else blocked}
    if trigger == "AUTO":
        version["automatic_attempts"] = version.get("automatic_attempts", 0) + 1
    else:
        version.setdefault("explicit_checks", {})[str(trigger_id)] = {"trigger": trigger, "at": now.isoformat()}
    try:
        fetched = fetcher(url)
        if isinstance(fetched, str):
            extraction = extract_document(fetched)
        elif isinstance(fetched, dict) and "html" in fetched:
            extraction = extract_document(fetched["html"], http_status=fetched.get("status", 200),
                                          content_type=fetched.get("content_type", "text/html"))
            if fetched.get('truncated'):
                if extraction['body_status'] == 'FULL':
                    extraction['body_status'] = 'PARTIAL'
                extraction.setdefault('reasons', []).append('BODY_DOWNLOAD_TRUNCATED')
            extraction.update(verified_source_metadata(fetched, extraction.get('body_sha256')))
        elif isinstance(fetched, dict) and ("body_status" in fetched or "status" in fetched) and "body" in fetched:
            extraction = deepcopy(fetched)
            extraction.setdefault("body_status", extraction.get("status"))
            if extraction["body_status"] not in {"FULL", "PARTIAL", "UNAVAILABLE"}:
                raise ValueError("invalid extraction status")
            body = extraction["body"]
            if not isinstance(body, str):
                raise TypeError("extracted body must be text")
            if not body and extraction["body_status"] in {"FULL", "PARTIAL"}:
                extraction["body_status"] = "UNAVAILABLE"
                extraction.setdefault("reasons", []).append("NO_READABLE_BODY")
            extraction["body_sha256"] = hashlib.sha256(body.encode()).hexdigest() if body else None
            extraction["body_chars"] = len(body)
            extraction.setdefault("reasons", [])
        else:
            raise TypeError("fetcher must return HTML or an extraction object")
    except Exception as exc:
        diagnostic = access_failure(exc)
        extraction = {"body": "", "body_status": "UNAVAILABLE", "body_sha256": None, "body_chars": 0,
                      "extraction_method": "FAILED", "reasons": [diagnostic['category'], type(exc).__name__],
                      "access_diagnostic": diagnostic}
    body = extraction.get("body", "")
    if body:
        extraction["body_sha256"] = cache_body(cache_dir, body)
    metadata = public_metadata(extraction)
    # Preserve readable partial data if a subsequent acquisition is unavailable.
    if not body and cached is not None:
        body = cached
        metadata["acquisition_status"] = "UNAVAILABLE"
        metadata["body_status"] = "PARTIAL"
        metadata["body_sha256"] = latest.get("body_sha256")
        metadata["body_chars"] = len(body)
        metadata["reasons"].append("PREVIOUS_ACCESSIBLE_BODY_RETAINED")
    history_entry = {"at": now.isoformat(), "trigger": trigger, "trigger_id": str(trigger_id) if trigger_id else None,
                     **metadata}
    version.setdefault("history", []).append(history_entry)
    version["latest"] = metadata
    if metadata.get("body_status") != "FULL":
        version["next_retry_at"] = (now + timedelta(hours=6)).isoformat()
    else:
        version.pop("next_retry_at", None)
    ledger["current_source_version"] = source_version
    return {"body": body, "metadata": metadata, "ledger": ledger,
            "acquired": True, "cache_reused": False, "blocked": None}
