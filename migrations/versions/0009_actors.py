"""Manually tagged actors and links to already indexed documents."""
from alembic import op
import sqlalchemy as sa

revision = "0009_actors"
down_revision = "0008_lineages"
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
    op.create_table("actors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stable_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("stable_key", name="uq_actor_stable_key"),
        sa.CheckConstraint("actor_type IN ('COMPANY', 'GOVERNMENT', 'CUSTOMER', 'SUPPLIER', 'COMPETITOR', 'OTHER')", name="ck_actor_type"),
        _soft_check("ck_actor_soft_delete"))
    op.create_table("actor_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("actors.id"), nullable=False),
        sa.Column("sec_document_id", sa.String(36), sa.ForeignKey("documents.id")),
        sa.Column("contract_award_id", sa.String(36), sa.ForeignKey("contract_awards.id")),
        sa.Column("federal_register_document_id", sa.String(36), sa.ForeignKey("federal_register_documents.id")),
        *_timestamps(),
        sa.UniqueConstraint("actor_id", "sec_document_id", name="uq_actor_sec_document"),
        sa.UniqueConstraint("actor_id", "contract_award_id", name="uq_actor_contract_award"),
        sa.UniqueConstraint("actor_id", "federal_register_document_id", name="uq_actor_fr_document"),
        sa.CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) = 1", name="ck_actor_one_document"),
        _soft_check("ck_actor_document_soft_delete"))
    for table in ("actors", "actor_documents"):
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    for table in ("actor_documents", "actors"):
        op.execute(f"DROP TRIGGER guard_{table}_delete")
        op.drop_table(table)
