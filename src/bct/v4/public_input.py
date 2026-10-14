"""Hash-bound public excerpt reviews. Originals and engine provenance stay intact.

Only native, independently identified public sources can use this path. Contact
footers are excluded by coordinates, never redacted or sent to the provider.
"""
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import parse_qsl, urlsplit

from bct import future_body
from bct.target_acquisition import public_url
from .store import sha, now

VERSION = "bct-v4-public-input-1"
SECRET = re.compile(r"api[_ -]?key|authorization\s*:|bearer\s+|password\s*[:=]|private key|sk-[A-Za-z0-9]|gsk_[A-Za-z0-9]|AIza[A-Za-z0-9]|\b\d{6}-[1-4]\d{6}\b|\b(?:account number|계좌번호)\b", re.I)
CONTACT = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b|\(\d{3}\)\s*\d{3}[- ]\d{4}", re.I)
SIGNAL = re.compile(r"order|contract|deliver|backlog|demand|capacity|production|qualif|delay|lead.time|supply|inventory|expand|alternative|relief", re.I)
LINK = re.compile(r"^(?:however|but|whereas|nevertheless|unless|subject to|provided that|in contrast|despite|although)\b", re.I)
COUNTER = re.compile(r"\b(?:not|no longer|never|cancelled|canceled|surplus|inventory|substitute|shortened|eased|relief)\b", re.I)
PUBLISHERS = {"www.esa.int": ("ESA", "European Space Agency"),
              "www.aehr.com": ("Aehr", "Aehr Test Systems"),
              "www.eia.gov": ("U.S. Energy Information Administration", "Energy Information Administration"),
              "www.nist.gov": ("National Institute of Standards and Technology",),
              "www.energy.gov": ("Energy.gov", "Department of Energy")}


def valid_article_url(url, final_url=None):
    """The only query exception is EIA's single, decimal public article id."""
    try:
        public_url(url)
        p = urlsplit(url)
        if p.scheme != "https" or p.fragment or p.port not in (None, 443):
            return False
        if final_url is not None and final_url != url:
            return False  # no identity-changing redirect for this review path
        if not p.query:
            return True
        return (p.hostname == "www.eia.gov" and p.path == "/todayinenergy/detail.php"
                and re.fullmatch(r"id=[1-9][0-9]{0,7}", p.query) is not None
                and parse_qsl(p.query, strict_parsing=True) == [("id", p.query[3:])])
    except (ValueError, TypeError):
        return False


def _public_date(record, raw_text):
    """Recheck literal native header evidence; a URL/date assertion is not proof."""
    from lxml import html
    proof = record.get("publication_proof", {})
    expected = record.get("published_at")
    try:
        day = datetime.fromisoformat(expected.replace("Z", "+00:00")).date()
        if day > datetime.now(timezone.utc).date():
            return False
        dom = html.fromstring(raw_text)
        host = urlsplit(record["url"]).hostname
        if host == "www.esa.int":
            dates = dom.xpath('//h1/following-sibling::div[contains(@class,"meta")][1]/span')
            return any(datetime.strptime(x.text_content().strip(), "%d/%m/%Y").date() == day for x in dates
                       if re.fullmatch(r"\d{2}/\d{2}/\d{4}", x.text_content().strip()))
        if host == "www.eia.gov":
            if urlsplit(record["url"]).path == "/electricity/monthly/":
                dates = dom.xpath('//span[@class="label" and normalize-space(.)="Release Date:"]/following-sibling::span[@class="date"][1]')
                return any(x.text_content().strip() == day.strftime("%B %d, %Y").replace(" 0", " ") for x in dates)
            dates = dom.xpath('//span[@class="date"]')
            return any(x.text_content().strip() == day.strftime("%B %d, %Y").replace(" 0", " ") for x in dates)
        # article:published_time, not sidebar/news dates or a guessed URL date
        dates = dom.xpath('//meta[@property="article:published_time"]/@content')
        return any(datetime.fromisoformat(x.replace("Z", "+00:00")).date() == day for x in dates)
    except (ValueError, TypeError, KeyError):
        return False


def review_native(doc, raw, record, *, reviewer="Codex native-source verifier"):
    """Create a reproducible review receipt, without upgrading source provenance."""
    reasons = []
    body = doc.get("body", "")
    if any(doc.get(k) for k in ("confidential", "personal_data", "api_transfer_forbidden")):
        reasons.append("EXPLICIT_TRANSFER_RESTRICTION")
    url = doc.get("origin_url", "")
    if not valid_article_url(url, record.get("final_url", record.get("url"))):
        reasons.append("URL_OR_REDIRECT_NOT_APPROVED")
    if raw is None:
        reasons.append("NATIVE_ORIGINAL_MISSING")
    else:
        if hashlib.sha256(raw).hexdigest() != doc.get("raw_sha256") or doc.get("raw_sha256") != record.get("raw_sha256"):
            reasons.append("NATIVE_HASH_MISMATCH")
        text = raw.decode("utf-8", errors="replace")
        if hashlib.sha256(body.encode()).hexdigest() != doc.get("body_sha256") or doc.get("body_sha256") != record.get("body_sha256"):
            reasons.append("BODY_HASH_MISMATCH")
        if future_body.extract_document(text).get("body") != body:
            reasons.append("NATIVE_TO_FROZEN_BODY_MISMATCH")
        host = urlsplit(url).hostname
        publisher = PUBLISHERS.get(host)
        checks = doc.get("checks", {})
        if (not publisher or not any(x in text for x in publisher)
                or not checks.get("http_success") or not checks.get("not_republication")
                or record.get("url") != url):
            reasons.append("PUBLIC_ORIGINAL_IDENTITY_UNVERIFIED")
        if not _public_date(record, text):
            reasons.append("NATIVE_PUBLICATION_UNVERIFIED")
        try:
            publication = datetime.fromisoformat(record["published_at"].replace("Z", "+00:00")).date()
            acquired = datetime.fromisoformat(doc["acquired_at"].replace("Z", "+00:00")).date()
            if publication > acquired or datetime.fromisoformat(doc["published_at"].replace("Z", "+00:00")).date() != publication:
                reasons.append("PUBLICATION_AFTER_ACQUISITION_OR_METADATA_MISMATCH")
        except (KeyError, ValueError, TypeError):
            reasons.append("PUBLICATION_ACQUISITION_UNVERIFIED")
    if SECRET.search(body):
        reasons.append("SENSITIVE_DATA_ANYWHERE_IN_BODY")
    excluded = []
    contacts = list(CONTACT.finditer(body))
    if contacts:
        footer = list(re.finditer(r"(?im)^\s*(?:Contacts?|Media contacts?|Press contacts?)\s*:?[^\n]*$", body))
        # Only a terminal, explicitly labelled press contact region is exempt.
        boundary = footer[-1].start() if footer else len(body)
        if (not footer or boundary < len(body) * .65 or any(m.start() < boundary for m in contacts)
                or SIGNAL.search(body[footer[-1].end():]) or COUNTER.search(body[footer[-1].end():])):
            reasons.append("CONTACT_OUTSIDE_VERIFIED_TERMINAL_FOOTER")
        else:
            excluded.append({"start": boundary, "end": len(body), "reason": "PUBLIC_PRESS_CONTACT_FOOTER_NOT_TRANSMITTED"})
    return {"version": VERSION, "status": "BLOCKED" if reasons else "PASS", "reasons": sorted(set(reasons)),
            "document_id": doc["document_id"], "body_sha256": doc.get("body_sha256"),
            "raw_sha256": doc.get("raw_sha256"), "origin_url": url,
            "published_at": doc.get("published_at"), "reviewer": reviewer, "reviewed_at": now(),
            "excluded_ranges": excluded, "source_provenance_unchanged": doc.get("provenance"),
            "scope": "VERIFIED_PUBLIC_EXCERPT_ONLY_NOT_ENGINE_PROVENANCE"}


def selected_input(doc, config, review, env):
    """Whole paragraphs, including adjacent qualification/counterevidence blocks.

    Oversized paragraphs are withheld, not truncated. The 600-character limit
    remains fixed; missing context is a coverage limitation, never a fake FULL.
    """
    body = doc["body"]
    if (review.get("version") != VERSION or review.get("status") != "PASS"
            or any(review.get(k) != doc.get(k) for k in ("document_id", "body_sha256", "raw_sha256", "origin_url", "published_at"))
            or not review.get("reviewer") or not review.get("reviewed_at")
            or any(doc.get(k) for k in ("confidential", "personal_data", "api_transfer_forbidden"))
            or not valid_article_url(doc["origin_url"])):
        raise ValueError("PUBLIC_REVIEW_MISMATCH")
    if (hashlib.sha256(body.encode()).hexdigest() != doc["body_sha256"] or SECRET.search(body)
            or any(value and len(value) >= 8 and value in body for key in ("GROQ_API_KEY", "GEMINI_API_KEY") if (value := env.get(key)))):
        raise ValueError("SENSITIVE_OR_CHANGED_SOURCE")
    excluded = review["excluded_ranges"]
    if any(not any(x["start"] <= m.start() < m.end() <= x["end"] for x in excluded) for m in CONTACT.finditer(body)):
        raise ValueError("UNREVIEWED_CONTACT")
    paragraphs = list(re.finditer(r"[^\n]+", body))
    groups, current = [], []
    for paragraph in paragraphs:
        if any(paragraph.start() < x["end"] and paragraph.end() > x["start"] for x in excluded):
            continue
        if current and (LINK.search(paragraph[0].strip()) or COUNTER.search(paragraph[0])):
            current.append(paragraph)
        else:
            if current:
                groups.append(current)
            current = [paragraph]
    if current:
        groups.append(current)
    ranked = sorted(groups, key=lambda g: (-len(SIGNAL.findall(body[g[0].start():g[-1].end()])), g[0].start()))
    windows, held = [], []
    remaining = config["max_input_characters"]
    for group in ranked:
        a, b = group[0].start(), group[-1].end()
        if not SIGNAL.search(body[a:b]):
            continue
        if b-a > remaining or len(windows) >= config["max_windows"]:
            held.append({"start": a, "end": b, "reason": "WHOLE_CONTEXT_EXCEEDS_INPUT_BUDGET"})
            continue
        windows.append({"start": a, "end": b, "text": body[a:b]})
        remaining -= b-a
    if not windows:
        raise ValueError("NO_COMPLETE_SAFE_SIGNAL_CONTEXT_WITHIN_BUDGET" if held else "NO_SIGNAL_CONTEXT_IN_SOURCE")
    windows.sort(key=lambda x: x["start"])
    selected = {"windows": windows, "publication": {"published_at": doc.get("published_at"),
                "precision": doc.get("publication_precision", "UNKNOWN")},
                "provenance_scope": review["scope"], "selected_characters": sum(w["end"]-w["start"] for w in windows),
                "body_characters": len(body), "coverage": "BOUNDED_WHOLE_CONTEXT_NOT_FULL_DOCUMENT",
                "input_policy_version": VERSION}
    # No review identity, raw source, contact text or local env is transmitted.
    from .store import encode
    if CONTACT.search(encode(selected)) or SECRET.search(encode(selected)):
        raise ValueError("UNSAFE_SERIALIZED_INPUT")
    return selected
