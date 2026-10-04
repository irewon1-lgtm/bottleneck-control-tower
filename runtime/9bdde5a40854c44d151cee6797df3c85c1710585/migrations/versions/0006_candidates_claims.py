"""Candidates, claims, and minimal links to already collected documents."""
from alembic import op
import sqlalchemy as sa

revision = "0006_candidates_claims"
down_revision = "0005_federal_register_full_texts"
branch_labels = None
depends_on = None


def _soft_delete_constraint(name):
    return sa.CheckConstraint(
        "(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)",
        name=name)


def _timestamps():
    return [sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False),
            sa.Column("deleted_at", sa.String(40))]


def upgrade():
    op.create_table("candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stable_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("stable_key", name="uq_candidate_stable_key"),
        _soft_delete_constraint("ck_candidate_soft_delete"))
    op.create_table("claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("statement", sa.String(2000), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("candidate_id", "statement", name="uq_candidate_claim_statement"),
        _soft_delete_constraint("ck_claim_soft_delete"))
    op.create_table("claim_document_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("sec_document_id", sa.String(36), sa.ForeignKey("documents.id")),
        sa.Column("contract_award_id", sa.String(36), sa.ForeignKey("contract_awards.id")),
        sa.Column("federal_register_document_id", sa.String(36), sa.ForeignKey("federal_register_documents.id")),
        *_timestamps(),
        sa.UniqueConstraint("claim_id", "sec_document_id", name="uq_claim_sec_document"),
        sa.UniqueConstraint("claim_id", "contract_award_id", name="uq_claim_contract_award"),
        sa.UniqueConstraint("claim_id", "federal_register_document_id", name="uq_claim_fr_document"),
        sa.CheckConstraint("(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) = 1", name="ck_claim_one_document"),
        _soft_delete_constraint("ck_claim_link_soft_delete"))
    for table in ("candidates", "claims", "claim_document_links"):
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    for table in ("claim_document_links", "claims", "candidates"):
        op.execute(f"DROP TRIGGER guard_{table}_delete")
        op.drop_table(table)
