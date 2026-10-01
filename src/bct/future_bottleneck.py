"""Independent, recall-first body screening. Canonical SQLite is never written."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
from html.parser import HTMLParser
from html import unescape
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import tempfile
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

VERSION = "body-candidate-v3.3"
FILTER_VERSION = "bct-v33-recall-1"
CATEGORIES = {
    "DEMAND": r"\b(?:demand|orders?|order[- ]books?|backlog|offtake|procurement|consumption|contracts?|purchas\w*|shipments?|deliveries|installation|install\w*|adopt\w*|invest(?:s|ed|ing|ment|ments)?|projects?|construction|bookings?|sales|customer\w*|launch\w*)\b|수요|주문|계약|출하|설치|도입|투자|프로젝트",
    "SUPPLY": r"\b(?:supply|suppliers?|production|manufactur\w*|capacity|output|factories|factory|plants?|facilit\w*|mills?|mines?|certif\w*|qualif\w*|lead[- ]times?|deliveries|shipping|workforce|workers?|labor|labour|nurses?|drivers?|inventory|inventories)\b|공급|생산|공장|감산|인증|납기",
    "RELIEF": r"\b(?:expan\w*|new (?:plant|facilit\w*|suppliers?|providers?|sources?|entrants?|factory|fab|mill|production line)|second (?:source|supplier)|alternative\w*|substitut\w*|efficien\w*|productivity|yield|normaliz\w*|debottleneck\w*|recover\w*|capacity additions?|add(?:ing)? capacity|reduc\w* lead[- ]times?|short\w* lead[- ]times?)\b|증설|대체|효율|정상화|취소|감소",
}
PATTERNS = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
CHANGE = re.compile(r"\b(?:grow\w*|increas\w*|ris\w*|rose|surge\w*|jump\w*|accelerat\w*|double\w*|triple\w*|record|sign\w*|award\w*|secure\w*|win|won|book\w*|receive\w*|announc\w*|plan(?:s|ned|ning)?|expect\w*|forecast\w*|projected|projecting|anticipat\w*|will|would|may|could|ramp\w*|launch\w*|start\w*|begin\w*|began|build\w*|built|expand\w*|expansion|add(?:s|ed|ing)?|new|chang\w*|adopt\w*|install\w*|invest(?:s|ed|ing)?|commit\w*|cancel\w*|cut\w*|reduc\w*|declin\w*|fall\w*|fell|drop\w*|slow\w*|stop\w*|halt\w*|close\w*|closur\w*|suspend\w*|delay\w*|restrict\w*|pause\w*|retire\w*|short\w*|tight\w*|limit\w*|backlog\w*|outpac\w*)\b|증가|급증|확대|감소|지연|중단|폐쇄|계획|예정|취소", re.I)
SUPPLY_PRESSURE = re.compile(r"\b(?:shortages?|scarcity|scarce|bottlenecks?|constraints?|supply[- ]crunch|supply[- ]gap|disrupt\w*|export controls?|allocation|insufficient|limited|tight|capacity crunch|long lead[- ]times?|extended lead[- ]times?|lead[- ]times? (?:of|at|are|remain|stretch\w*|exceed\w*)|backlog\w*)\b|부족|제약|차질", re.I)
SUPPLY_LOSS = re.compile(r"\b(?:cut\w*|reduc\w*|declin\w*|fall\w*|fell|drop\w*|slow\w*|stop\w*|halt\w*|close\w*|closur\w*|suspend\w*|delay\w*|restrict\w*|pause\w*|retire\w*|shutdown|shut[- ]?down|outages?|disrupt\w*|unavailable|shortages?|scarcity|tight|limited|insufficient)\b|감산|중단|폐쇄|지연|제한|차질", re.I)
DEMAND_RELIEF = re.compile(r"\b(?:cancel\w*|cut\w*|reduc\w*|declin\w*|fall\w*|fell|drop\w*|slow\w*|less|lower|downturn)\b|취소|감소|둔화", re.I)
UNCERTAIN = re.compile(r"\b(?:may|might|can|could|would|if|unless|plan(?:s|ned|ning)?|expect\w*|forecast\w*|projected|propos\w*|not|no|never|denied|rumou?rs?|possible|potential)\b|계획|전망|예정|가능|않|아니", re.I)
COMPUTE_ONLY = re.compile(r"\b(?:CPU|GPU|RAM|gaming|frame rates?|software|database|algorithm|bandwidth|latency|performance|AI|connectivity|scheduling|workflow|queries|analytics|data analysis)\b", re.I)
REAL_OPERATION = re.compile(r"\b(?:suppl\w*|factories?|plants?|manufactur\w*|production|shipments?|shipping|freight|trucking|contracts?|purchas\w*|procurement|orders?|investment|install\w*|adopt\w*|facilit\w*|nurses?|workers?|workforce|labor|labour|customer\w*)\b", re.I)
COMPUTE_PERFORMANCE = re.compile(r"\b(?:CPU|RAM|gaming|frame rates?|algorithm|bandwidth|latency|performance|queries)\b", re.I)
LABOR = re.compile(r"\b(?:workers?|workforce|contractors?|crews?|staff|labor|labour|talent|skills?|skilled|professionals?|nurses?|drivers?|recruitment)\b", re.I)
SUPPLY = re.compile(r"\b(?:materials?|components?|equipment|factory|factories|plants?|suppliers?|supply chain|inventory|inventories|shipping|manufactur\w*)\b", re.I)
COMPUTE = re.compile(r"\b(?:CPU|GPU|RAM|gaming|frame rates?|software|database|algorithm|bandwidth|latency|performance)\b", re.I)
PRESSURE = re.compile(r"\b(?:shortages?|scarcity|scarce|constraints?|bottlenecks?|backlogs?|limited|tight|insufficient|outpac\w*|allocation|supply[- ]crunch|supply[- ]gap|supply disruptions?|throughput limits?|capacity limits?|orders? (?:are )?(?:accelerat\w*|surg\w*|jump\w*)|supply (?:may |could |will )?(?:recover\w*|normaliz\w*)|(?:long|extended|lengthy|rising|increas\w*) lead[- ]times?|lead[- ]times? (?:of|at|are|remain|stretch\w*|exceed\w*)|\d+(?:[- ](?:day|week|month|year)s?) lead[- ]time)\b", re.I)
PROCESS_ONLY = re.compile(r"\b(?:software|data(?:base)?|algorithm|AI|connectivity|latency|bandwidth|synchronization|scheduling|workflow|flight planning|revenue management|legacy systems?|downstream systems?|memory access)\b", re.I)
PHYSICAL_OBJECT = re.compile(r"\b(?:raw materials?|critical materials?|components?|equipment|suppliers?|inventory|inventories|shipping|factories?|plants?|transformers?|turbines?|engines?|fuels?|vessels?|tankers?|semiconductors?|wafers?|trucks?|fleets?|trailers?)\b", re.I)
TRANSPORT_PRESSURE = re.compile(r"\b(?:capacity crunch|(?:reduc\w*|tighten\w*) (?:trucking |freight )?capacity|(?:trucking|freight|cross-border trucking) supply contracts)\b", re.I)
TRANSPORT = re.compile(r"\b(?:trucks?|trucking|fleets?|freight|carriers?|cross-border)\b", re.I)
PREVENTION = re.compile(r"\b(?:avoid|prevent)\w*\b[^.!?]{0,80}\b(?:shortages?|overstocking)\b", re.I)
BLOCKED = re.compile(r"(?:verify (?:that )?you are human|enable javascript and cookies|checking your browser|access denied|just a moment)", re.I)
# Explicit fine-grained phrases, plus open phrase extraction below. Never a sector label.
TARGET = re.compile(r"\b(?:(?:high[- ]voltage|power|distribution|large power) transformers?|(?:gas|steam) turbines?|(?:high[- ]bandwidth|HBM\d*|DDR\d+) memory|advanced packaging|CoWoS|ABF substrates?|300\s*mm wafers?|solid rocket motors?|ammonium perchlorate|HTPB|high[- ]assay low[- ]enriched uranium|HALEU|battery[- ]grade lithium (?:carbonate|hydroxide)|copper (?:foil|concentrate)|rare[- ]earth magnets?|grain[- ]oriented electrical steel|silicon carbide wafers?|(?:marine|aviation|diesel) fuel|sulfuric acid|helium|medical isotopes?)\b", re.I)
OPEN_TARGET = re.compile(r"\b(?:shortages? of|scarcity of|supply constraints? for|lead[- ]times? for|production of|manufacturing of|capacity for)\s+([^.;:\n]{2,100})", re.I)
STOP = re.compile(r"\b(?:is|are|was|were|has|have|will|could|would|may|if|as|because|while|which|that|to|in|at|by|from|with|for|said|discussing|nearly|both|used)\b|[“”\"—]", re.I)
GENERIC_TARGET = re.compile(r"\b(?:up|between|just|time|ever|innovation|mindset|problem-solving|essential material|new equipment|expansion|technology|project|enhances|positions|manager)\b", re.I)


class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.blocks, self.scripts = [], [], []
        self.current, self.script = None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append(tag)
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.script = []
        if tag == "p" and not any(t in self.stack for t in ("nav", "footer", "header", "aside")):
            self.current = ([], "article" in self.stack, "main" in self.stack)
        if tag in ("br", "hr", "img", "meta", "link", "input", "source", "wbr"):
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if self.current and not any(t in self.stack for t in ("script", "style", "noscript")):
            self.current[0].append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag == "p" and self.current:
            text = " ".join(" ".join(self.current[0]).split())
            if len(text) >= 50:
                self.blocks.append((text, *self.current[1:]))
            self.current = None
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]


def _article_bodies(value):
    if isinstance(value, dict):
        kinds = value.get("@type", [])
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if any("Article" in k or "Posting" in k for k in kinds if isinstance(k, str)):
            if isinstance(value.get("articleBody"), str):
                yield value["articleBody"]
        for item in value.values():
            yield from _article_bodies(item)
    elif isinstance(value, list):
        for item in value:
            yield from _article_bodies(item)


def extract_body(html):
    from .future_body import extract_document
    document = extract_document(html)
    if document["body_status"] == "UNAVAILABLE":
        raise ValueError("NO_READABLE_BODY")
    return document["body"], document["extraction_method"]


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("INVALID_URL")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("NON_PUBLIC_URL")


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_html(url):
    public_url(url)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BottleneckControlTower/0.1)",
                                "Accept": "text/html,application/xhtml+xml"})
    with build_opener(PublicRedirect()).open(req, timeout=8) as response:
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("BODY_TOO_LARGE")
        return {"html": payload.decode(response.headers.get_content_charset() or "utf-8", errors="replace"),
                "status": response.status, "content_type": response.headers.get_content_type()}


def fetch_body(url):
    """Compatibility entry point; run() retains the completeness metadata."""
    document = fetch_html(url)
    return extract_body(document["html"])


def screen(body, tracked_terms=()):
    """Keep independent demand, supply and relief signals for human context review.

    Source-wide text is inspected; automatic matches never assign an S stage.
    Public excerpts share one 24-word budget. Other evidence is a body location.
    """
    if not isinstance(body, str):
        raise TypeError("body must be text")
    sentence_rows = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", body):
        sentence = match.group().strip()
        if sentence:
            start = match.start() + len(match.group()) - len(match.group().lstrip())
            end = start + len(sentence)
            sentence_rows.append((sentence, start, end, body.count("\n", 0, start) + 1))
    path_indexes = {"DEMAND": set(), "SUPPLY": set(), "RELIEF": set(), "TRACKED_CHANGE": set()}
    uncertain_indexes = set()
    digital_noise = False
    for i, (sentence, start, end, paragraph) in enumerate(sentence_rows):
        context = " ".join(r[0] for r in sentence_rows[max(0, i - 1):i + 2])
        has_demand = bool(PATTERNS["DEMAND"].search(sentence))
        has_supply = bool(PATTERNS["SUPPLY"].search(sentence))
        physical = bool(PHYSICAL_OBJECT.search(sentence) or TARGET.search(sentence) or OPEN_TARGET.search(sentence))
        compute_only = bool(COMPUTE_PERFORMANCE.search(context)) and not REAL_OPERATION.search(context)
        illustrative_list = bool(re.search(r"\bmay need\b", sentence, re.I)) and bool(PROCESS_ONLY.search(context))
        usage_scope = bool(re.search(r"\b(?:application|use|usage|analysis|study|research)\b.{0,70}\blimited to\b", sentence, re.I))
        if usage_scope and not (has_supply or TARGET.search(sentence)):
            digital_noise = True
            continue
        if illustrative_list and not (SUPPLY_LOSS.search(sentence) or TARGET.search(sentence)):
            digital_noise = True
            continue
        if compute_only:
            digital_noise = True
            continue
        if has_demand and CHANGE.search(sentence):
            path_indexes["DEMAND"].add(i)
        if (has_supply and SUPPLY_LOSS.search(sentence)) or (SUPPLY_PRESSURE.search(sentence) and (has_supply or physical or not COMPUTE_ONLY.search(context))):
            if not (PREVENTION.search(sentence) and not (has_demand and CHANGE.search(sentence))):
                path_indexes["SUPPLY"].add(i)
        if (PATTERNS["RELIEF"].search(sentence) and (has_supply or physical or has_demand)) or (has_demand and DEMAND_RELIEF.search(sentence)):
            path_indexes["RELIEF"].add(i)
        if UNCERTAIN.search(context) or re.search(r"\b(?:conference|webinar|presentation|illustrative|example)\b", context, re.I):
            uncertain_indexes.add(i)
    tracked_matches = []
    for term in tracked_terms or ():
        if not isinstance(term, str) or not term.strip():
            continue
        for i, (sentence, start, end, paragraph) in enumerate(sentence_rows):
            if re.search(r"(?<!\w)" + re.escape(term.strip()) + r"(?!\w)", sentence, re.I):
                path_indexes["TRACKED_CHANGE"].add(i)
                if term not in tracked_matches:
                    tracked_matches.append(term)
    qualifying = set().union(*path_indexes.values())
    candidate = bool(qualifying)
    context_review = candidate and bool(qualifying & uncertain_indexes)
    locations = {}
    evidence = {}
    remaining = 24
    for path, indexes in path_indexes.items():
        if not indexes:
            continue
        locations[path] = []
        evidence[path] = []
        for i in sorted(indexes):
            sentence, start, end, paragraph = sentence_rows[i]
            loc = {"paragraph": paragraph, "sentence": i + 1, "start": start, "end": end}
            locations[path].append(loc)
            if remaining:
                words = sentence.split()[:min(8, remaining)]
                evidence[path].append(" ".join(words))
                remaining -= len(words)
    targets = {}
    # Names remain extraction leads, and never establish a supply-chain relation.
    for i in sorted(qualifying):
        sentence, start, end, paragraph = sentence_rows[i]
        context_indexes = range(max(0, i - 1), min(len(sentence_rows), i + 2))
        for j in context_indexes:
            text, a, b, para = sentence_rows[j]
            loc = {"paragraph": para, "sentence": j + 1, "start": a, "end": b}
            for match in TARGET.finditer(text):
                targets.setdefault(match.group().lower(), {"name": match.group(), "method": "EXPLICIT_PHRASE", "evidence_location": loc})
        for match in OPEN_TARGET.finditer(sentence):
            phrase = STOP.split(match.group(1), maxsplit=1)[0].strip(" ,")
            for name in re.split(r",|\s+and\s+", phrase):
                name = re.sub(r"^(?:the|a|an)\s+", "", name.strip(), flags=re.I)
                if (1 <= len(name.split()) <= 6 and re.fullmatch(r"[A-Za-z][A-Za-z0-9 -]*", name)
                    and not LABOR.search(name) and not GENERIC_TARGET.search(name)
                    and name.lower() not in {"energy", "oil", "mining", "refining", "products", "goods", "services", "capacity", "demand", "production"}):
                    targets.setdefault(name.lower(), {"name": name, "method": "OPEN_PHRASE_UNVERIFIED",
                        "evidence_location": {"paragraph": paragraph, "sentence": i + 1, "start": start, "end": end}})
    reason = "COMPUTER_PERFORMANCE_ONLY" if not candidate and digital_noise else None
    return {"candidate": candidate,
            "decision": "CONTEXT_REVIEW" if context_review else "CANDIDATE_ONLY" if candidate else "EXCLUDED_NOISE" if reason else "NO_EVIDENCE",
            "reason": reason, "discovery_paths": [path for path, indexes in path_indexes.items() if indexes],
            "context_review": bool(context_review), "evidence": evidence,
            "evidence_locations": locations, "quoted_word_count": 24 - remaining,
            "tracked_matches": tracked_matches, "targets": list(targets.values()),
            "target_status": "EXTRACTED_UNVERIFIED" if targets else "UNRESOLVED", "final_bottleneck": None}


def run(db_path, output, *, limit=300, workers=6, fetcher=fetch_html,
        cache_dir=None, filter_version=FILTER_VERSION, screener=screen,
        trigger="AUTO", trigger_id=None, patch_output=None, tracking_path=None,
        tracked_terms=(), document_ids=None):
    from .future_body import acquire_document, read_cached_body
    from .future_store import LocalJSONTransport, store_patch
    if not 1 <= limit <= 1000 or not 1 <= workers <= 8:
        raise ValueError("invalid batch bounds")
    output = Path(output)
    state = json.loads(output.read_text()) if output.exists() else {"version": VERSION, "results": {}}
    if state.get("version") not in (VERSION, "body-candidate-v2"):
        raise ValueError("version mismatch; use a separate output")
    terms = set(tracked_terms)
    if tracking_path:
        tracking = json.loads(Path(tracking_path).read_text())
        for target in tracking.get("targets", []):
            for name in ("target", "product", "project"):
                value = target.get(name)
                if isinstance(value, str) and value:
                    terms.add(value)
                    terms.update(re.findall(r'\b[A-Za-z][A-Za-z0-9_-]{1,}\b', value))
            for name in ("aliases", "products", "projects", "tracking_terms"):
                terms.update(x for x in target.get(name, []) if isinstance(x, str) and x)
    terms_hash = hashlib.sha256(json.dumps(sorted(terms), ensure_ascii=False).encode()).hexdigest()
    with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute("SELECT id,title,url,source,collected_at,updated_at FROM radar_items WHERE status='active' ORDER BY collected_at,id")]
    # A processing bound never limits retention or the discovery window.
    scoped = rows
    now = datetime.now(timezone.utc)
    cache_dir = Path(cache_dir) if cache_dir else output.parent / ".future-body-cache"
    pending = []
    for row in scoped:
        if document_ids is not None and row['id'] not in document_ids:
            continue
        fingerprint = hashlib.sha256((row["url"] + row["updated_at"]).encode()).hexdigest()
        prior = state["results"].get(row["id"], {})
        same_source = prior.get("fingerprint") == fingerprint
        same_filter = (prior.get("filter_version") == filter_version
                       and prior.get("tracking_terms_sha256") == terms_hash)
        if trigger == "AUTO" and same_source and same_filter:
            if (prior.get("body_status") == "FULL" or prior.get("attempts", 0) >= 3
                    or prior.get("retry_after", "") > now.isoformat()):
                continue
        if (trigger == "AUTO" and same_source
                and (prior.get("attempts", 0) >= 3 or prior.get("retry_after", "") > now.isoformat())
                and prior.get("screening_pending_for") == filter_version
                and prior.get("pending_tracking_terms_sha256") == terms_hash):
            continue
        pending.append((row, fingerprint, prior))
    def process(job):
        row, fingerprint, prior = job
        def acquire(url):
            value = fetcher(url)
            if isinstance(value, tuple):
                # Explicit extracted-text adapters (including old callers) retain
                # unverified completeness rather than assuming FULL from length.
                return {"body": value[0], "extraction_method": value[1],
                        "body_status": "PARTIAL", "reasons": ["EXTERNAL_COMPLETENESS_UNVERIFIED"]}
            return value
        ledger = prior.get("acquisition", {})
        if not ledger and prior.get("fingerprint") == fingerprint:
            ledger = {"versions": {fingerprint: {
                "automatic_attempts": prior.get("attempts", 0), "explicit_checks": {}, "history": [],
                "latest": {"body_status": "PARTIAL" if prior.get("body_status") == "BODY_OK" else "UNAVAILABLE",
                           "body_sha256": prior.get("body_sha256"), "body_chars": prior.get("body_chars", 0),
                           "reasons": ["LEGACY_COMPLETENESS_UNVERIFIED"]}}}}
        acq_trigger = trigger
        latest = ledger.get("versions", {}).get(fingerprint, {}).get("latest", {})
        if (trigger == "AUTO" and (prior.get("filter_version") != filter_version
                                   or prior.get("tracking_terms_sha256") != terms_hash)
                and read_cached_body(cache_dir, latest.get("body_sha256")) is not None):
            acq_trigger = "FILTER_CHANGED"
        acquired = acquire_document(row["url"], fingerprint, ledger,
                                    cache_dir, acquire, trigger=acq_trigger, trigger_id=trigger_id,
                                    now=now.isoformat())
        meta = acquired["metadata"]
        meta.setdefault("body_status", "UNAVAILABLE")
        meta.setdefault("reasons", [acquired.get("blocked") or "NO_ACCESSIBLE_BODY"])
        body = acquired.get("body", "")
        result = {**row, **meta, "fingerprint": fingerprint, "source_version": fingerprint,
                  "filter_version": filter_version, "acquisition": acquired["ledger"],
                  "checked_at": now.isoformat()}
        if body:
            result.update(screener(body, tracked_terms=sorted(terms)) if terms else screener(body))
            result.update(tracking_terms_sha256=terms_hash, screening_pending_for="", pending_tracking_terms_sha256="", reaccess_status="AVAILABLE")
        else:
            # A missing cache is missing evidence, never a negative re-screen.
            for field in ('candidate', 'decision', 'reason', 'target_status', 'targets', 'evidence',
                          'discovery_paths', 'evidence_locations', 'context_review', 'quoted_word_count', 'tracked_matches'):
                if field in prior:
                    result[field] = prior[field]
            result.setdefault('candidate', False)
            result.setdefault('decision', 'UNREAD_MATERIAL')
            result.setdefault('targets', [])
            result.setdefault('evidence', {})
            result.setdefault('target_status', 'UNRESOLVED')
            result.update(body_status='UNAVAILABLE', acquisition_status='UNAVAILABLE',
                          screening_pending_for=filter_version, pending_tracking_terms_sha256=terms_hash,
                          filter_version=prior.get('filter_version', ''),
                          reaccess_status=acquired.get('blocked') or 'UNAVAILABLE')
        result["material_check_required"] = not body or result["body_status"] != "FULL"
        result["attempts"] = acquired["ledger"].get("versions", {}).get(fingerprint, {}).get("automatic_attempts", 0)
        result["retry_after"] = (now + timedelta(hours=6)).isoformat() if result["material_check_required"] else ""
        versions = {}
        old_hash = prior.get("body_sha256")
        if old_hash and old_hash not in prior.get("versions", {}):
            versions[old_hash] = {k: prior[k] for k in (
                "body_sha256", "body_status", "body_chars", "extraction_method", "checked_at") if k in prior}
            versions[old_hash]["completeness_unverified"] = True
        body_hash = meta.get("body_sha256")
        if body_hash and body:
            versions[body_hash] = {k: result[k] for k in (
                "body_sha256", "body_status", "body_chars", "extraction_method", "reasons",
                "completeness", "source_version", "checked_at", "filter_version", "candidate",
                "decision", "evidence", "discovery_paths", "evidence_locations", "context_review",
                "quoted_word_count", "tracked_matches", "targets", "queue_entered_at", "reaccess_status") if k in result}
            if body_hash in prior.get("versions", {}):
                # Source checks and body versions are different identities. An
                # unchanged body may be observed under a new source check.
                versions[body_hash].pop("source_version", None)
            result["current_body_sha256"] = body_hash
            for old_version in prior.get('versions', {}):
                if (old_version != body_hash
                        and read_cached_body(cache_dir, old_version) is None):
                    versions[old_version] = {"reaccess_status": "SOURCE_CHANGED", "access_checked_at": now.isoformat()}
        elif body_hash:
            versions[body_hash] = {"reaccess_status": "UNAVAILABLE", "access_checked_at": now.isoformat()}
            result["current_body_sha256"] = prior.get("current_body_sha256", body_hash)
        elif old_hash:
            # A failed reaccess does not delete the last successful body version.
            result["current_body_sha256"] = prior.get("current_body_sha256", old_hash)
        result["versions"] = versions
        if result["candidate"] or result["material_check_required"]:
            result["queue_entered_at"] = prior.get("queue_entered_at", now.isoformat())
        return result
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(process, pending[:limit]))
    from .future_store import deep_merge
    patch = {"version": VERSION, "filter_version": filter_version,
             "results": {r["id"]: r for r in results}}
    projected = deep_merge(state, patch)
    live = list(projected["results"].values())
    ok = sum(r["body_status"] == "FULL" for r in results)
    patch["summary"] = {"db_news_articles": len(rows), "scope_articles": len(scoped),
                        "new_documents_this_run": sum(r['collected_at'] > state.get('summary', {}).get('checked_at', now.isoformat()) for r in rows),
                        "processed_this_run": len(results), "body_ok_this_run": ok,
                        "body_rate_this_run": round(ok / len(results), 4) if results else None,
                        "candidates_this_run": sum(r["candidate"] for r in results),
                        "processed_total": len(live), "body_ok_total": sum(r.get("body_status") == "FULL" for r in live),
                        "candidates_total": sum(bool(r.get("candidate")) for r in live),
                        "pending_due": max(0, len(pending) - limit), "checked_at": now.isoformat(),
                        "private_cache": "RUNTIME_ONLY_NOT_PUBLISHED",
                        "source_reaccess_limit": "Cache may expire; historical body reproducibility is not guaranteed."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        output.write_text(json.dumps(state, ensure_ascii=False) + "\n")
    operation_id = "collect-" + str(uuid.uuid4())
    saved = store_patch(LocalJSONTransport(), str(output), owner="collection",
                        patch=patch, operation_id=operation_id)
    if saved.status not in ("APPLIED", "ALREADY_APPLIED"):
        raise RuntimeError("collection save pending: " + saved.reason)
    if patch_output:
        Path(patch_output).write_text(json.dumps({"operation_id": operation_id, "owner": "collection", "patch": patch}, ensure_ascii=False, indent=2) + "\n")
    return json.loads(output.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--patch-output", type=Path)
    parser.add_argument("--tracking", type=Path)
    parser.add_argument("--trigger", choices=["AUTO", "USER", "SCHEDULED"], default="AUTO")
    parser.add_argument("--trigger-id")
    parser.add_argument("--document-id", action="append")
    args = parser.parse_args()
    result = run(args.db, args.output, limit=args.limit, cache_dir=args.cache_dir, patch_output=args.patch_output,
                 tracking_path=args.tracking, trigger=args.trigger, trigger_id=args.trigger_id, document_ids=args.document_id)
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
