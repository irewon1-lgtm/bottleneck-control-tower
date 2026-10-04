"""Minimal federal contract award metadata linked to immutable API response."""
from alembic import op
import sqlalchemy as sa

revision = "0003_contract_awards"
down_revision = "0002_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("contract_awards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("award_id", sa.String(160), nullable=False),
        sa.Column("recipient_name", sa.String(500), nullable=False),
        sa.Column("award_amount", sa.String(80)),
        sa.Column("awarding_agency", sa.String(300)),
        sa.Column("last_modified_date", sa.String(40)),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("source", "external_id", name="uq_contract_award_identity"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_contract_award_soft_delete"))
    op.execute("CREATE TRIGGER guard_contract_awards_delete BEFORE DELETE ON contract_awards BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_contract_awards_delete")
    op.drop_table("contract_awards")
