"""Lazy direct library calls. Entity spans never authorize forecast/S upgrades."""
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from bct import future_body, precursor_official_source, target_acquisition
from bct.collectors.sec.collector import SECTransport, parse_listing
from .store import sha, now, file_sha

MAX_BYTES = 20_000_000
MODEL = "fastino/gliner2-base-v1"
MODEL_REVISION = "f9634218e53580c56edf0de97ca1a7d3f1c2354e"


def exact_date(text):
    import dateparser
    value = dateparser.parse(text, languages=["en"], settings={"STRICT_PARSING": True,
                                                               "DATE_ORDER": "YMD"})
    return value.date().isoformat() if value else None


def rss_leads(raw):
    import feedparser
    feed = feedparser.parse(raw)
    if feed.bozo:
        raise ValueError("MALFORMED_RSS")
    leads = []
    for entry in feed.entries:
        url = entry.get("link")
        if not url:
            continue
        target_acquisition.public_url(url)
        leads.append({"url": url, "title": entry.get("title", "UNKNOWN"),
                      "feed_published_raw": entry.get("published", "UNKNOWN"),
                      "publication_verified": False})
    return leads


def pdf_text(raw):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(raw), strict=True)
    pages = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages)]
    body = "\n".join(page["text"] for page in pages)
    return {"body": body, "pages": pages, "status": "PARTIAL" if body else "UNAVAILABLE",
            "limitations": ["OCR/complex tables/attachments not verified", "publication/origin requires separate evidence"]}


def html_views(raw):
    import trafilatura
    html = raw.decode("utf-8", errors="replace")
    started = time.process_time()
    baseline = future_body.extract_document(html)
    baseline_cpu = time.process_time() - started
    started = time.process_time()
    alternative = trafilatura.extract(html, include_tables=True, include_comments=False) or ""
    return {"baseline": baseline, "trafilatura": alternative,
            "cpu_seconds": {"baseline": baseline_cpu, "trafilatura": time.process_time() - started},
            "selection": "BCT existing parser retained until same-input accuracy is demonstrated"}


class SourceClient:
    def __init__(self, user_agent=None):
        identity = user_agent or os.environ.get("BCT_SEC_USER_AGENT")
        self.sec = SECTransport(identity) if identity and re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", identity) else None
        self.listings = {}

    def fetch(self, url):
        target_acquisition.public_url(url)
        host = urlsplit(url).hostname
        if host in ("www.sec.gov", "data.sec.gov"):
            if self.sec is None:
                raise ValueError("SEC_IDENTITY_REQUIRED: set BCT_SEC_USER_AGENT with real project/contact")
            return self.sec.get(url), url, 200, "text/html" if host == "www.sec.gov" else "application/json"
        with urlopen(Request(url, headers={"User-Agent": "BCT-V4-shadow/1.0", "Accept-Encoding": "identity"}), timeout=20) as response:
            target_acquisition.public_url(response.url)
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("BODY_TOO_LARGE")
            return raw, response.url, response.status, response.headers.get_content_type()

    def listing(self, cik):
        cik = str(cik).zfill(10)
        if not re.fullmatch(r"\d{10}", cik):
            raise ValueError("INVALID_CIK")
        if cik not in self.listings:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            raw, _, _, _ = self.fetch(url)
            self.listings[cik] = ({"url": url, "acquired_at": now(), "status": "CAPTURED",
                                   "raw_sha256": target_acquisition.digest(raw)}, raw)
        return self.listings[cik]

    def filings(self, cik, limit=1):
        record, raw = self.listing(cik)
        return [{"url": f.url, "form": f.form, "filing_date": f.filing_date,
                 "accession": f.accession} for f in parse_listing(raw, str(cik).zfill(10), limit)]

    def document(self, url):
        raw, final, status, content_type = self.fetch(url)
        match = precursor_official_source.SEC.fullmatch(url)
        metadata, metadata_raw = self.listing(match[1]) if match else (None, None)
        at = now()
        if content_type.split(";")[0] == "application/pdf":
            view = pdf_text(raw)
            doc = {"origin_url": final, "body": view["body"], "body_status": view["status"],
                   "body_sha256": target_acquisition.digest(view["body"]), "raw_sha256": target_acquisition.digest(raw),
                   "published_at": None, "publication_precision": "UNKNOWN", "origin_id": "UNKNOWN",
                   "origin_publisher": "UNKNOWN", "provenance": "BLOCKED", "provenance_verified": False,
                   "provenance_blockers": view["limitations"], "acquired_at": at, "available_at": at}
            views = {"pdf": view}
        else:
            views = html_views(raw)
            doc = precursor_official_source.verify(raw, url, final, at, status, content_type,
                                                  metadata_record=metadata, metadata_raw=metadata_raw)
        doc["document_id"] = "v4doc-" + sha([url, doc["raw_sha256"]])
        doc["requested_url"] = url
        doc["publication_date_normalized"] = exact_date(doc["published_at"]) if doc.get("published_at") else None
        return doc, raw, views


def prepare_model(root):
    """Fetch only the selected CPU model AFTER checking its distinct weight license."""
    root = Path(root)
    os.environ["HF_HOME"] = str(root.resolve() / "model-cache")
    os.environ["XDG_CACHE_HOME"] = str(root.resolve() / "cache")
    # Supported HTTPS downloader, with bounded socket waits. Xet's native
    # transport stalled without receiving any model bytes in this environment.
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "30"
    from huggingface_hub import model_info, snapshot_download, hf_hub_url, get_hf_file_metadata
    info = model_info(MODEL, revision=MODEL_REVISION, files_metadata=True)
    license_id = (info.card_data.to_dict() if info.card_data else {}).get("license")
    if license_id != "apache-2.0":
        raise ValueError("MODEL_WEIGHT_LICENSE_UNVERIFIED")
    model_dir = root / "models" / "gliner2-base-v1"
    snapshot_download(MODEL, revision=info.sha, local_dir=model_dir,
                      allow_patterns=["*.json", "*.txt", "README.md", "LICENSE*"])
    # A read-only range probe succeeded through urllib after the hub HTTP
    # transport returned 403. Download the same official, pinned files using
    # standard verified TLS and verify the upstream LFS digest before use.
    expected = {item.rfilename: item.lfs.sha256 for item in info.siblings if item.lfs
                and item.rfilename.endswith((".safetensors", ".model"))}
    for name, expected_sha in expected.items():
        destination = model_dir / name
        if destination.exists() and file_sha(destination) == expected_sha:
            continue
        remote = get_hf_file_metadata(hf_hub_url(MODEL, name, revision=info.sha))
        if remote.etag != expected_sha or remote.commit_hash != info.sha:
            raise ValueError("MODEL_UPSTREAM_METADATA_MISMATCH")
        temporary = destination.with_suffix(destination.suffix + ".partial")
        size = 0
        with urlopen(Request(remote.location), timeout=30) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > remote.size:
                    raise ValueError("MODEL_DOWNLOAD_EXCEEDS_DECLARED_SIZE")
                handle.write(chunk)
        if size != remote.size or file_sha(temporary) != expected_sha:
            raise ValueError("MODEL_UPSTREAM_CHECKSUM_MISMATCH")
        temporary.replace(destination)
    files = [{"path": str(p.relative_to(model_dir)), "sha256": file_sha(p)}
             for p in sorted(model_dir.rglob("*")) if p.is_file() and ".cache" not in p.parts
             and p.name != "bct-manifest.json" and not p.name.endswith(".partial")]
    observed = {item["path"]: item["sha256"] for item in files}
    if not expected or any(observed.get(name) != digest for name, digest in expected.items()):
        raise ValueError("MODEL_UPSTREAM_CHECKSUM_MISMATCH")
    manifest = {"model": MODEL, "revision": info.sha, "weights_license": license_id,
                "files": files, "upstream_lfs_checksums": expected, "prepared_at": now()}
    (model_dir / "bct-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class CPUExtractor:
    def __init__(self, root):
        self.root = Path(root)
        self.model = None

    def load(self):
        model_dir = self.root / "models" / "gliner2-base-v1"
        path = model_dir / "bct-manifest.json"
        if not path.exists():
            raise ValueError("CPU_MODEL_NOT_PREPARED: run prepare-model; no paid fallback")
        manifest = json.loads(path.read_text())
        if (manifest.get("weights_license") != "apache-2.0" or manifest.get("model") != MODEL
                or manifest.get("revision") != MODEL_REVISION):
            raise ValueError("MODEL_MANIFEST_INVALID")
        for record in manifest["files"]:
            source = (model_dir / record["path"]).resolve()
            if not source.is_relative_to(model_dir.resolve()) or file_sha(source) != record["sha256"]:
                raise ValueError("MODEL_FILE_HASH_MISMATCH")
        # Offline loading avoids unexpected downloads or remote executable code.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(self.root.resolve() / "model-cache")
        import torch
        from gliner2 import GLiNER2
        torch.set_num_threads(4)
        self.model = GLiNER2.from_pretrained(str(model_dir), map_location="cpu", attention_backend="standard").to("cpu")
        self.model.eval()
        self.revision = manifest["revision"]

    def extract(self, doc, *, max_windows=4):
        if type(max_windows) is not int or not 1 <= max_windows <= 16:
            raise ValueError("AI_WINDOW_LIMIT_MUST_BE_1_TO_16")
        if self.model is None:
            self.load()
        labels = ["product", "specification", "industry", "subindustry", "location", "customer", "supplier", "quantity", "date"]
        spans = []
        # Paragraph windows retain offsets and bounded CPU input. Oversize lines
        # are split; cross-window relations remain UNKNOWN.
        from bct.precursor_discovery import PATTERNS
        pattern = re.compile("|".join(PATTERNS.values()), re.I)
        chunks = [chunk for chunk in re.finditer(r"[^\n]{1,1800}", doc["body"]) if pattern.search(chunk.group())]
        future_years = {str(datetime.now(timezone.utc).year + i) for i in (1, 2, 3)}
        chunks.sort(key=lambda chunk: (not any(y in chunk.group() for y in future_years), chunk.start()))
        selected = sorted(chunks[:max_windows], key=lambda chunk: chunk.start())
        for chunk in selected:
            output = self.model.extract_entities(chunk.group(), labels, include_confidence=True, include_spans=True)
            spans.extend(validate_spans(doc, output, offset=chunk.start()))
        return {"status": "PASS" if selected else "NOT_RUN", "model": MODEL, "revision": self.revision, "device": "cpu", "threads": 4,
                "spans": spans, "event_link_accuracy": "UNKNOWN", "target_accuracy": "UNKNOWN",
                "selected_windows": [{"start": c.start(), "end": c.end()} for c in selected],
                "unread_signal_windows": max(0, len(chunks)-len(selected)),
                "coverage": "BOUNDED_SIGNAL_WINDOWS_NOT_FULL_DOCUMENT",
                "policy": "Source-located advisory entities; no automatic scope/qualification/S upgrade"}


def validate_spans(doc, output, offset=0):
    spans = []
    for label, items in output.get("entities", {}).items():
        for item in items:
            start, end = item.get("start"), item.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end:
                raise ValueError("INVALID_MODEL_SPAN")
            start += offset
            end += offset
            if end > len(doc["body"]) or doc["body"][start:end] != item["text"]:
                raise ValueError("MODEL_SPAN_SOURCE_MISMATCH")
            spans.append({"label": label, "text": item["text"], "confidence": item.get("confidence"),
                          "document_id": doc["document_id"], "body_sha256": doc["body_sha256"],
                          "locator": {"start": start, "end": end}, "semantic_status": "UNKNOWN"})
    return spans
