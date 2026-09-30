"""Manual document lineage groups; no independence inference."""
from alembic import op
import sqlalchemy as sa

revision = "0008_lineages"
down_revision = "0007_evidence"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False),
            sa.Column("deleted_at", sa.String(40))]


def _soft_check(name):
    return sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name=name)


def upgrade():
    op.create_table("lineages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stable_key", sa.String(200), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("stable_key", name="uq_lineage_stable_key"),
        _soft_check("ck_lineage_soft_delete"))
    op.create_table("lineage_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lineage_id", sa.String(36), sa.ForeignKey("lineages.id"), nullable=False),
        sa.Column("sec_document_id", sa.String(36), sa.ForeignKey("documents.id")),
        sa.Column("contract_award_id", sa.String(36), sa.ForeignKey("contract_awards.id")),
        sa.Column("federal_register_document_id", sa.String(36), sa.ForeignKey("federal_register_documents.id")),
        *_timestamps(),
        sa.UniqueConstraint("lineage_id", "sec_document_id", name="uq_lineage_sec_document"),
        sa.UniqueConstraint("lineage_id", "contract_award_id", name="uq_lineage_contract_award"),
        sa.UniqueConstraint("lineage_id", "federal_register_document_id", name="uq_lineage_fr_document"),
        sa.CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) = 1", name="ck_lineage_one_document"),
        _soft_check("ck_lineage_document_soft_delete"))
    for table in ("lineages", "lineage_documents"):
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    for table in ("lineage_documents", "lineages"):
        op.execute(f"DROP TRIGGER guard_{table}_delete")
        op.drop_table(table)
