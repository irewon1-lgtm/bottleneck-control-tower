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
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

VERSION = "body-candidate-v2"
CATEGORIES = {
    "DEMAND": r"\b(?:demand|orders?|backlog|offtake|procurement|consumption)\b",
    "CONSTRAINT": r"\b(?:shortages?|scarcity|scarce|constraints?|bottlenecks?|supply[- ]crunch|supply[- ]gap|export controls?|supply disruptions?|allocation)\b",
    "CAPACITY_LEAD_TIME": r"\b(?:capacity|lead[- ]times?|utilization|production|manufacturing|output|throughput)\b",
    "TIMING": r"\b(?:ramp[- ]up|commissioning|by 20\d{2}|in 20\d{2}|delays?|delayed|months?|years?)\b",
    "RELIEF": r"\b(?:expansion|expand\w*|new facilit\w*|new plant|new supplier|normaliz\w*|debottleneck\w*|capacity additions?|add(?:ing)? capacity|supply recover\w*)\b",
}
PATTERNS = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
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
    parser = ArticleHTML()
    parser.feed(html)
    choices = []
    for script in parser.scripts:
        try:
            choices.extend((x, "JSON_LD") for x in _article_bodies(json.loads(script)))
        except (ValueError, RecursionError):
            pass
    for index, method in ((1, "ARTICLE"), (2, "MAIN")):
        text = "\n".join(dict.fromkeys(t for t, a, m in parser.blocks if (a, m)[index - 1]))
        if text:
            choices.append((text, method))
    choices.append(("\n".join(dict.fromkeys(t for t, _, _ in parser.blocks)), "PARAGRAPHS"))
    for text, method in choices:
        text = unescape(re.sub(r"<[^>]+>", " ", text))
        if len(text) >= 400 and len(text.split()) >= 70 and not BLOCKED.search(text[:500]):
            return text, method
    raise ValueError("NO_READABLE_BODY")


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


def fetch_body(url):
    public_url(url)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BottleneckControlTower/0.1)",
                                "Accept": "text/html,application/xhtml+xml"})
    with build_opener(PublicRedirect()).open(req, timeout=8) as response:
        if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
            raise ValueError("UNSUPPORTED_CONTENT_TYPE")
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("BODY_TOO_LARGE")
        return extract_body(payload.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))


def screen(body):
    # No title or RSS snippet enters this decision.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", body) if s.strip()]
    evidence = {k: [s[:350] for s in sentences if p.search(s)][:2] for k, p in PATTERNS.items()}
    evidence = {k: v for k, v in evidence.items() if v}
    constrained = [s for s in sentences if PATTERNS["CONSTRAINT"].search(s)]
    def mixed_objects(sentence):
        for match in OPEN_TARGET.finditer(sentence):
            parts = re.split(r",|\s+and\s+", STOP.split(match.group(1), maxsplit=1)[0])
            if len(parts) > 1 and any(p.strip() and not LABOR.search(p) for p in parts):
                return True
        return False
    def strong_physical_signal(sentence):
        if TARGET.search(sentence) and PRESSURE.search(sentence):
            return True
        for match in OPEN_TARGET.finditer(sentence):
            phrase = STOP.split(match.group(1), maxsplit=1)[0]
            parts = [p.strip() for p in re.split(r",|\s+and\s+", phrase) if p.strip()]
            if any(not LABOR.search(p) and not PROCESS_ONLY.search(p) and not GENERIC_TARGET.search(p) for p in parts):
                return True
        return bool(
            PHYSICAL_OBJECT.search(sentence)
            and re.search(r"\b(?:shortages?|scarcity|scarce|backlogs?|tight|limited|supply[- ]crunch|supply[- ]gap|supply disruptions?|throughput limits?|capacity limits?)\b", sentence, re.I)
        )

    transport_constraint = any(TRANSPORT_PRESSURE.search(s) and TRANSPORT.search(
        " ".join(sentences[max(0, i - 1):i + 2])) for i, s in enumerate(sentences))
    physical_constraint = transport_constraint or any(strong_physical_signal(s) for s in constrained)
    labor_context = any(LABOR.search(" ".join(sentences[max(0, i - 1):i + 2]))
                        for i, s in enumerate(sentences) if s in constrained)
    labor_only = bool(constrained) and labor_context and not physical_constraint
    compute_only = bool(constrained) and all(COMPUTE.search(s) and not SUPPLY.search(s)
        and not re.search(r"\b(?:shortages?|supply|orders?|capacity|lead[- ]time)\b", s, re.I) for s in constrained)
    process_only = bool(constrained) and all(
        (PROCESS_ONLY.search(s) or COMPUTE.search(s) or re.search(r"\b(?:plann\w*|manual observation)\b", s, re.I))
        and not strong_physical_signal(s) for s in constrained
    )
    reason = ("LABOR_ONLY" if labor_only else "COMPUTER_PERFORMANCE_ONLY" if compute_only
              else "DIGITAL_PROCESS_ONLY" if process_only else None)

    # Require bottleneck-like pressure plus supporting evidence in the same
    # local context. Generic demand/capacity/expansion mentions alone stay out.
    qualifying_indexes = set()
    for i, sentence in enumerate(sentences):
        transport_pressure = bool(TRANSPORT_PRESSURE.search(sentence) and TRANSPORT.search(
            " ".join(sentences[max(0, i - 1):i + 2])))
        if not (PRESSURE.search(sentence) or PATTERNS["CONSTRAINT"].search(sentence) or transport_pressure):
            continue
        # Prevention advice and a hypothetical process inefficiency are not
        # reports of supply pressure. Keep conditional physical shortages.
        if PREVENTION.search(sentence) or (
            re.search(r"\b(?:can|could) become a bottleneck\b", sentence, re.I)
            and not strong_physical_signal(sentence)
        ):
            continue
        lo, hi = max(0, i - 1), min(len(sentences), i + 2)
        context = " ".join(sentences[lo:hi])
        local_labor_only = bool(LABOR.search(context)) and not (
            PHYSICAL_OBJECT.search(context) or TARGET.search(context) or OPEN_TARGET.search(context) or transport_pressure
        )
        anchor_physical = bool(
            PHYSICAL_OBJECT.search(sentence) or TARGET.search(sentence) or OPEN_TARGET.search(sentence)
            or re.search(r"\b(?:shortages?|scarcity|supply[- ]crunch|supply[- ]gap|supply disruptions?)\b", sentence, re.I)
        )
        local_process_only = bool(PATTERNS["CONSTRAINT"].search(sentence)) and bool(
            PROCESS_ONLY.search(context) or COMPUTE.search(context)
        ) and not anchor_physical
        if local_labor_only or local_process_only:
            continue
        axes = {k for k, pattern in PATTERNS.items() if pattern.search(context)}
        physical = bool(SUPPLY.search(context) or TARGET.search(context) or OPEN_TARGET.search(context))
        strong_constraint = "CONSTRAINT" in axes and (
            physical or bool(axes & {"DEMAND", "CAPACITY_LEAD_TIME", "RELIEF"})
        )
        structural_pressure = "CAPACITY_LEAD_TIME" in axes and bool(
            axes & {"DEMAND", "TIMING", "RELIEF"}
        )
        relief_pressure = (
            "RELIEF" in axes
            and bool(re.search(r"\bsupply .*?(?:recover|normaliz)|\bdebottleneck", context, re.I))
        )
        if transport_pressure or (PRESSURE.search(context) and (strong_constraint or structural_pressure or relief_pressure)):
            qualifying_indexes.update(range(lo, hi))

    candidate = bool(qualifying_indexes) and reason is None
    targets = {}
    if candidate:
        for i in sorted(qualifying_indexes):
            sentence = sentences[i]
            context = " ".join(sentences[max(0, i - 1):i + 2])
            for match in TARGET.finditer(context):
                targets.setdefault(match.group().lower(), {"name": match.group(), "method": "EXPLICIT_PHRASE", "evidence": context[:500]})
            for match in OPEN_TARGET.finditer(sentence):
                phrase = STOP.split(match.group(1), maxsplit=1)[0].strip(" ,")
                for name in re.split(r",|\s+and\s+", phrase):
                    name = re.sub(r"^(?:the|a|an)\s+", "", name.strip(), flags=re.I)
                    if (1 <= len(name.split()) <= 6 and re.fullmatch(r"[A-Za-z][A-Za-z0-9 -]*", name)
                        and not LABOR.search(name) and not GENERIC_TARGET.search(name)
                        and name.lower() not in {"energy", "oil", "mining", "refining", "products", "goods", "services", "capacity", "demand", "production"}):
                        targets.setdefault(name.lower(), {"name": name, "method": "OPEN_PHRASE_UNVERIFIED", "evidence": sentence[:500]})
    return {"candidate": candidate, "decision": "CANDIDATE_ONLY" if candidate else "EXCLUDED_NOISE" if reason else "NO_EVIDENCE",
            "reason": reason, "evidence": evidence, "targets": list(targets.values())[:12],
            "target_status": "EXTRACTED_UNVERIFIED" if targets else "UNRESOLVED", "final_bottleneck": None}


def run(db_path, output, *, limit=300, workers=6, fetcher=fetch_body):
    if not 1 <= limit <= 1000 or not 1 <= workers <= 8:
        raise ValueError("invalid batch bounds")
    output = Path(output)
    state = json.loads(output.read_text()) if output.exists() else {"version": VERSION, "results": {}}
    if state["version"] != VERSION:
        raise ValueError("version mismatch; use a separate output")
    with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute("SELECT id,title,url,source,collected_at,updated_at FROM radar_items WHERE status='active' AND source_type='NEWS' ORDER BY collected_at DESC,id DESC")]
    # Initial live check: latest batch. Subsequent runs cover ALL newly collected items.
    if "start_at" not in state:
        state["start_at"] = rows[min(limit, len(rows)) - 1]["collected_at"] if rows else ""
    scoped = [r for r in rows if r["collected_at"] >= state["start_at"]]
    now = datetime.now(timezone.utc)
    pending = []
    for row in reversed(scoped):
        fingerprint = hashlib.sha256((row["url"] + row["updated_at"]).encode()).hexdigest()
        prior = state["results"].get(row["id"], {})
        if prior.get("fingerprint") == fingerprint:
            if prior.get("body_status") == "BODY_OK" or prior.get("attempts", 0) >= 3 or prior.get("retry_after", "") > now.isoformat():
                continue
        pending.append((row, fingerprint, prior))
    def process(job):
        row, fingerprint, prior = job
        attempts = prior.get("attempts", 0) + 1 if prior.get("fingerprint") == fingerprint else 1
        result = {**row, "fingerprint": fingerprint, "attempts": attempts, "checked_at": now.isoformat()}
        try:
            body, method = fetcher(row["url"])
            result.update(body_status="BODY_OK", extraction_method=method, body_chars=len(body),
                          body_sha256=hashlib.sha256(body.encode()).hexdigest(), **screen(body))
        except Exception as exc:
            result.update(body_status="BODY_UNAVAILABLE", candidate=False, decision="BODY_UNAVAILABLE",
                          target_status="UNRESOLVED", targets=[], evidence={}, final_bottleneck=None,
                          error=type(exc).__name__, retry_after=(now + timedelta(hours=6)).isoformat())
        return result
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(process, pending[:limit]))
    for result in results:
        state["results"][result["id"]] = result
    live = [state["results"][r["id"]] for r in scoped if r["id"] in state["results"]]
    ok = sum(r["body_status"] == "BODY_OK" for r in results)
    state["summary"] = {"db_news_articles": len(rows), "scope_articles": len(scoped),
                        "processed_this_run": len(results), "body_ok_this_run": ok,
                        "body_rate_this_run": round(ok / len(results), 4) if results else None,
                        "candidates_this_run": sum(r["candidate"] for r in results),
                        "processed_total": len(live), "body_ok_total": sum(r["body_status"] == "BODY_OK" for r in live),
                        "candidates_total": sum(r["candidate"] for r in live),
                        "pending_due": max(0, len(pending) - limit), "checked_at": now.isoformat()}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=output.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, output)
    finally:
        Path(name).unlink(missing_ok=True)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()
    result = run(args.db, args.output, limit=args.limit)
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
