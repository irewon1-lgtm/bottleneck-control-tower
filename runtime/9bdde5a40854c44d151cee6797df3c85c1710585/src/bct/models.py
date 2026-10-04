import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class RawDocument(Base):
    __tablename__ = "raw_documents"
    __table_args__ = (UniqueConstraint("source", "external_key", "sha256", name="uq_raw_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    external_key: Mapped[str] = mapped_column(String(500), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    relative_path: Mapped[str] = mapped_column(String(150), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("kind", "stable_key", name="uq_entity_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class CollectorRun(Base):
    __tablename__ = "collector_runs"
    __table_args__ = (UniqueConstraint("collector", "run_key", name="uq_collector_run"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collector: Mapped[str] = mapped_column(String(120), nullable=False)
    run_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("job_type", "job_key", name="uq_job_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    job_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_until: Mapped[str | None] = mapped_column(String(40))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class EvidenceFreeze(Base):
    __tablename__ = "evidence_freezes"
    __table_args__ = (UniqueConstraint("version", name="uq_freeze_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_document_source_external"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    form: Mapped[str] = mapped_column(String(12), nullable=False)
    filing_date: Mapped[str] = mapped_column(String(10), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class ContractAward(Base):
    __tablename__ = "contract_awards"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_contract_award_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    award_id: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(500), nullable=False)
    award_amount: Mapped[str | None] = mapped_column(String(80))
    awarding_agency: Mapped[str | None] = mapped_column(String(300))
    last_modified_date: Mapped[str | None] = mapped_column(String(40))
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class FederalRegisterDocument(Base):
    __tablename__ = "federal_register_documents"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_fr_document_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(2000), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    publication_date: Mapped[str] = mapped_column(String(10), nullable=False)
    agency_names: Mapped[str | None] = mapped_column(String(1000))
    html_url: Mapped[str] = mapped_column(String(1200), nullable=False)
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class FederalRegisterFullText(Base):
    __tablename__ = "federal_register_full_texts"
    __table_args__ = (UniqueConstraint("document_id", "raw_document_id", name="uq_fr_full_text_link"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("federal_register_documents.id"), nullable=False)
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1200), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)


class ResearchDocument(Base):
    __tablename__ = "research_documents"
    __table_args__ = (
        UniqueConstraint("source_url", "raw_document_id", name="uq_research_url_raw"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_research_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(80), default="research", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1200), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    publisher: Mapped[str] = mapped_column(String(300), nullable=False)
    published_on: Mapped[str | None] = mapped_column(String(10))
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("stable_key", name="uq_candidate_stable_key"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_candidate_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    stable_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("candidate_id", "statement", name="uq_candidate_claim_statement"),
        CheckConstraint("role IN ('DRIVER', 'CONSTRAINT', 'RELIEF', 'OTHER')", name="ck_claim_role"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_claim_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    statement: Mapped[str] = mapped_column(String(2000), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="OTHER", server_default="OTHER", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class ClaimDocumentLink(Base):
    __tablename__ = "claim_document_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "sec_document_id", name="uq_claim_sec_document"),
        UniqueConstraint("claim_id", "contract_award_id", name="uq_claim_contract_award"),
        UniqueConstraint("claim_id", "federal_register_document_id", name="uq_claim_fr_document"),
        UniqueConstraint("claim_id", "research_document_id", name="uq_claim_research_document"),
        CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) + (research_document_id IS NOT NULL) = 1", name="ck_claim_one_document"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_claim_link_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    sec_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    contract_award_id: Mapped[str | None] = mapped_column(ForeignKey("contract_awards.id"))
    federal_register_document_id: Mapped[str | None] = mapped_column(ForeignKey("federal_register_documents.id"))
    research_document_id: Mapped[str | None] = mapped_column(ForeignKey("research_documents.id"))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("claim_document_link_id", name="uq_evidence_claim_document"),
        CheckConstraint("direction IN ('SUPPORT', 'CONTRADICT', 'NEUTRAL')", name="ck_evidence_direction"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_evidence_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_document_link_id: Mapped[str] = mapped_column(ForeignKey("claim_document_links.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(12), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class Lineage(Base):
    __tablename__ = "lineages"
    __table_args__ = (
        UniqueConstraint("stable_key", name="uq_lineage_stable_key"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_lineage_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    stable_key: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class LineageDocument(Base):
    __tablename__ = "lineage_documents"
    __table_args__ = (
        UniqueConstraint("lineage_id", "sec_document_id", name="uq_lineage_sec_document"),
        UniqueConstraint("lineage_id", "contract_award_id", name="uq_lineage_contract_award"),
        UniqueConstraint("lineage_id", "federal_register_document_id", name="uq_lineage_fr_document"),
        UniqueConstraint("lineage_id", "research_document_id", name="uq_lineage_research_document"),
        CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) + (research_document_id IS NOT NULL) = 1", name="ck_lineage_one_document"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_lineage_document_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lineage_id: Mapped[str] = mapped_column(ForeignKey("lineages.id"), nullable=False)
    sec_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    contract_award_id: Mapped[str | None] = mapped_column(ForeignKey("contract_awards.id"))
    federal_register_document_id: Mapped[str | None] = mapped_column(ForeignKey("federal_register_documents.id"))
    research_document_id: Mapped[str | None] = mapped_column(ForeignKey("research_documents.id"))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (
        UniqueConstraint("stable_key", name="uq_actor_stable_key"),
        CheckConstraint("actor_type IN ('COMPANY', 'GOVERNMENT', 'CUSTOMER', 'SUPPLIER', 'COMPETITOR', 'OTHER')", name="ck_actor_type"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_actor_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    stable_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class ActorDocument(Base):
    __tablename__ = "actor_documents"
    __table_args__ = (
        UniqueConstraint("actor_id", "sec_document_id", name="uq_actor_sec_document"),
        UniqueConstraint("actor_id", "contract_award_id", name="uq_actor_contract_award"),
        UniqueConstraint("actor_id", "federal_register_document_id", name="uq_actor_fr_document"),
        UniqueConstraint("actor_id", "research_document_id", name="uq_actor_research_document"),
        CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) + (research_document_id IS NOT NULL) = 1", name="ck_actor_one_document"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_actor_document_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(ForeignKey("actors.id"), nullable=False)
    sec_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    contract_award_id: Mapped[str | None] = mapped_column(ForeignKey("contract_awards.id"))
    federal_register_document_id: Mapped[str | None] = mapped_column(ForeignKey("federal_register_documents.id"))
    research_document_id: Mapped[str | None] = mapped_column(ForeignKey("research_documents.id"))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class CountersearchRun(Base):
    __tablename__ = "countersearch_runs"
    __table_args__ = (
        UniqueConstraint("candidate_id", "record_key", name="uq_countersearch_candidate_key"),
        CheckConstraint("search_kind IN ('SUPPLY_EXPANSION', 'NEW_SUPPLIER', 'DEMAND_SLOWDOWN', 'SUBSTITUTION', 'POLICY_CHANGE', 'OTHER')", name="ck_countersearch_kind"),
        CheckConstraint("result_status IN ('NOT_RUN', 'RESULTS_FOUND', 'NO_RESULTS', 'INCONCLUSIVE', 'FAILED')", name="ck_countersearch_result"),
        CheckConstraint("(result_status = 'NOT_RUN' AND executed_on IS NULL) OR (result_status != 'NOT_RUN' AND executed_on IS NOT NULL)", name="ck_countersearch_execution_date"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_countersearch_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    record_key: Mapped[str] = mapped_column(String(200), nullable=False)
    search_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    executed_on: Mapped[str | None] = mapped_column(String(10))
    result_status: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))


class RadarItem(Base):
    __tablename__ = "radar_items"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_radar_source_external"),
        CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_radar_soft_delete"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(2000), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    published_at: Mapped[str | None] = mapped_column(String(40))
    collected_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    snippet: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String(40))
