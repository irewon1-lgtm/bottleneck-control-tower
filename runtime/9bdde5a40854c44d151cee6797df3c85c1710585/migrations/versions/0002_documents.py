"""Canonical document metadata linked to immutable raw bytes."""
from alembic import op
import sqlalchemy as sa

revision = "0002_documents"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("cik", sa.String(10), nullable=False),
        sa.Column("form", sa.String(12), nullable=False),
        sa.Column("filing_date", sa.String(10), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("source", "external_id", name="uq_document_source_external"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_document_soft_delete"))
    op.execute("CREATE TRIGGER guard_documents_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_documents_delete")
    op.drop_table("documents")
