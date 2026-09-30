import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .collector import MalformedRecord, SourceRecord
from .config import Settings
from .models import AuditLog, CollectorRun, Entity, EvidenceFreeze, Job, RawDocument, new_id, now


def audit(session: Session, event: str, kind: str, object_id: str, details: dict) -> None:
    session.add(AuditLog(event=event, object_type=kind, object_id=object_id,
                         details_json=json.dumps(details, sort_keys=True, ensure_ascii=False)))


def _nonempty(value: str, field: str, length: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > length:
        raise ValueError(f"invalid {field}")
    return value


def ingest(settings: Settings, session: Session, source: str, record: SourceRecord) -> RawDocument:
    """Caller owns commit; staged bytes are never referenced before atomic publish."""
    _nonempty(source, "source", 120)
    if not isinstance(record, SourceRecord) or not isinstance(record.content, bytes) or not record.content:
        raise MalformedRecord("content must be nonempty bytes")
    if record.external_id is not None:
        _nonempty(record.external_id, "external_id", 500)
    _nonempty(record.media_type, "media_type", 120)
    digest = hashlib.sha256(record.content).hexdigest()
    # Namespaces cannot collide, even if an external ID resembles a digest.
    key = ("id:" + hashlib.sha256(record.external_id.encode("utf-8")).hexdigest()
           if record.external_id is not None else f"content:{digest}")
    existing = session.scalar(select(RawDocument).where(RawDocument.source == source,
        RawDocument.external_key == key, RawDocument.sha256 == digest))
    if existing:
        return existing
    settings.mkdirs()
    relative = f"sha256/{digest[:2]}/{digest}"
    dest = settings.root / "raw" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="raw-", suffix=".tmp", dir=settings.staging_dir)
    try:
        with os.fdopen(fd, "wb") as staged:
            staged.write(record.content)
            staged.flush()
            os.fsync(staged.fileno())
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise IOError("content-addressed raw file is corrupted")
        else:
            try:
                os.link(tmp_name, dest)  # Never replace an existing blob, even concurrently.
            except FileExistsError:
                if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                    raise IOError("content-addressed raw file is corrupted")
            else:
                os.chmod(dest, 0o444)
                dir_fd = os.open(dest.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
    doc = RawDocument(source=source, external_key=key, external_id=record.external_id,
                      sha256=digest, relative_path=relative, byte_size=len(record.content),
                      media_type=record.media_type)
    session.add(doc)
    session.flush()
    audit(session, "raw.ingested", "raw_document", doc.id,
          {"source": source, "external_id": record.external_id, "sha256": digest})
    return doc


def get_or_create_run(session: Session, collector: str, run_key: str) -> CollectorRun:
    _nonempty(collector, "collector", 120)
    _nonempty(run_key, "run_key", 500)
    run = session.scalar(select(CollectorRun).where(CollectorRun.collector == collector,
                                                  CollectorRun.run_key == run_key))
    if run:
        return run
    run = CollectorRun(collector=collector, run_key=run_key)
    session.add(run)
    session.flush()
    audit(session, "run.created", "collector_run", run.id, {"collector": collector, "run_key": run_key})
    return run


def transition_run(session: Session, run: CollectorRun, target: str, error: str | None = None) -> None:
    if target == "running" and run.status in ("pending", "failed"):
        run.attempts += 1
    elif target == "succeeded" and run.status == "running":
        pass
    elif target == "failed" and run.status == "running":
        pass
    else:
        raise ValueError(f"invalid run transition {run.status} -> {target}")
    prior = run.status
    run.status, run.last_error, run.updated_at = target, error, now()
    audit(session, "run.transition", "collector_run", run.id, {"from": prior, "to": target, "error": error})


def get_or_create_job(session: Session, job_type: str, job_key: str) -> Job:
    _nonempty(job_type, "job_type", 120)
    _nonempty(job_key, "job_key", 500)
    job = session.scalar(select(Job).where(Job.job_type == job_type, Job.job_key == job_key))
    if job:
        return job
    job = Job(job_type=job_type, job_key=job_key)
    session.add(job)
    session.flush()
    audit(session, "job.created", "job", job.id, {"job_type": job_type, "job_key": job_key})
    return job


def claim_job(session: Session, job_id: str, lease_seconds: int = 300) -> bool:
    instant = now()
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat(timespec="microseconds")
    result = session.execute(update(Job).where(Job.id == job_id,
        (Job.status.in_(["pending", "failed"])) |
        ((Job.status == "running") & (Job.lease_until < instant)))
        .values(status="running", attempts=Job.attempts + 1, lease_until=expiry,
                last_error=None, updated_at=instant))
    if result.rowcount:
        audit(session, "job.claimed", "job", job_id, {"lease_until": expiry})
        return True
    return False


def finish_job(session: Session, job_id: str, *, error: str | None = None) -> bool:
    target = "failed" if error else "succeeded"
    result = session.execute(update(Job).where(Job.id == job_id, Job.status == "running")
        .values(status=target, lease_until=None, last_error=error, updated_at=now()))
    if result.rowcount:
        audit(session, "job.finished", "job", job_id, {"status": target, "error": error})
        return True
    return False


def put_entity(session: Session, kind: str, stable_key: str, name: str) -> Entity:
    _nonempty(kind, "kind", 80)
    _nonempty(stable_key, "stable_key", 500)
    _nonempty(name, "display_name", 500)
    entity = session.scalar(select(Entity).where(Entity.kind == kind, Entity.stable_key == stable_key))
    if entity:
        if entity.status == "deleted":
            raise ValueError("deleted entity must be explicitly restored")
        if entity.display_name != name:
            old = entity.display_name
            entity.display_name, entity.updated_at = name, now()
            audit(session, "entity.renamed", "entity", entity.id, {"from": old, "to": name})
        return entity
    entity = Entity(kind=kind, stable_key=stable_key, display_name=name)
    session.add(entity)
    session.flush()
    audit(session, "entity.created", "entity", entity.id, {"kind": kind, "key": stable_key})
    return entity


def set_deleted(session: Session, entity: Entity, deleted: bool) -> None:
    target = "deleted" if deleted else "active"
    if entity.status == target:
        return
    entity.status = target
    entity.deleted_at = now() if deleted else None
    entity.updated_at = now()
    audit(session, "entity.deleted" if deleted else "entity.restored", "entity", entity.id, {})


def create_freeze(session: Session, version: str, documents: list[RawDocument]) -> EvidenceFreeze:
    _nonempty(version, "version", 120)
    if not documents:
        raise ValueError("freeze must contain raw evidence")
    items = sorted({(d.id, d.sha256) for d in documents})
    manifest = json.dumps(items, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(manifest.encode()).hexdigest()
    if session.scalar(select(EvidenceFreeze).where(EvidenceFreeze.version == version)):
        raise ValueError("freeze version already exists")
    freeze = EvidenceFreeze(version=version, manifest_json=manifest, manifest_sha256=digest)
    session.add(freeze)
    session.flush()
    audit(session, "freeze.created", "evidence_freeze", freeze.id,
          {"version": version, "manifest_sha256": digest})
    return freeze
