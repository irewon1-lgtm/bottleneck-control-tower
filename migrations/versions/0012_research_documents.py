"""Permit archived manual web sources in the three existing research links."""
from alembic import op
import sqlalchemy as sa

revision = "0012_research_documents"
down_revision = "0011_claim_role"
branch_labels = None
depends_on = None

LINKS = {
    "claim_document_links": ("claim_id", "ck_claim_one_document", "uq_claim_research_document"),
    "lineage_documents": ("lineage_id", "ck_lineage_one_document", "uq_lineage_research_document"),
    "actor_documents": ("actor_id", "ck_actor_one_document", "uq_actor_research_document"),
}
OLD = "(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) = 1"
NEW = "(sec_document_id IS NOT NULL) + (contract_award_id IS NOT NULL) + (federal_register_document_id IS NOT NULL) + (research_document_id IS NOT NULL) = 1"


def upgrade():
    op.create_table("research_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_url", sa.String(1200), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("publisher", sa.String(300), nullable=False),
        sa.Column("published_on", sa.String(10)),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("source_url", "raw_document_id", name="uq_research_url_raw"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_research_soft_delete"))
    op.execute("CREATE TRIGGER guard_research_documents_delete BEFORE DELETE ON research_documents BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")
    # SQLite recreates tables for CHECK changes. Temporarily release the old delete
    # guards and FK enforcement, then restore them after copying existing rows.
    op.execute("PRAGMA foreign_keys=OFF")
    for table, (parent, check, unique) in LINKS.items():
        op.execute(f"DROP TRIGGER guard_{table}_delete")
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("research_document_id", sa.String(36)))
            batch.create_foreign_key(f"fk_{table}_research", "research_documents",
                                     ["research_document_id"], ["id"])
            batch.drop_constraint(check, type_="check")
            batch.create_check_constraint(check, NEW)
            batch.create_unique_constraint(unique, [parent, "research_document_id"])
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")
    for table, (parent, check, unique) in reversed(list(LINKS.items())):
        op.execute(f"DROP TRIGGER guard_{table}_delete")
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(unique, type_="unique")
            batch.drop_constraint(check, type_="check")
            batch.drop_column("research_document_id")
            batch.create_check_constraint(check, OLD)
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")
    op.execute("PRAGMA foreign_keys=ON")
    op.execute("DROP TRIGGER guard_research_documents_delete")
    op.drop_table("research_documents")
