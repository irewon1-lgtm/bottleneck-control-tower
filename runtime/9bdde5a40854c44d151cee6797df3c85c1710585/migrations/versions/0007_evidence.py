"""One manual direction per existing Claim-document link."""
from alembic import op
import sqlalchemy as sa

revision = "0007_evidence"
down_revision = "0006_candidates_claims"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claim_document_link_id", sa.String(36), sa.ForeignKey("claim_document_links.id"), nullable=False),
        sa.Column("direction", sa.String(12), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("claim_document_link_id", name="uq_evidence_claim_document"),
        sa.CheckConstraint("direction IN ('SUPPORT', 'CONTRADICT', 'NEUTRAL')", name="ck_evidence_direction"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_evidence_soft_delete"))
    op.execute("CREATE TRIGGER guard_evidence_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_evidence_delete")
    op.drop_table("evidence")
