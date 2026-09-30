"""Minimal Federal Register search document metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0004_federal_register_documents"
down_revision = "0003_contract_awards"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("federal_register_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("title", sa.String(2000), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("publication_date", sa.String(10), nullable=False),
        sa.Column("agency_names", sa.String(1000)),
        sa.Column("html_url", sa.String(1200), nullable=False),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("source", "external_id", name="uq_fr_document_identity"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_fr_document_soft_delete"))
    op.execute("CREATE TRIGGER guard_fr_documents_delete BEFORE DELETE ON federal_register_documents BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_fr_documents_delete")
    op.drop_table("federal_register_documents")
