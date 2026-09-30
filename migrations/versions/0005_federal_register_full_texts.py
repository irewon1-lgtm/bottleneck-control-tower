"""Link Federal Register documents to immutable full-text RAW versions."""
from alembic import op
import sqlalchemy as sa

revision = "0005_federal_register_full_texts"
down_revision = "0004_federal_register_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("federal_register_full_texts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("federal_register_documents.id"), nullable=False),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("source_url", sa.String(1200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("document_id", "raw_document_id", name="uq_fr_full_text_link"))
    op.execute("CREATE TRIGGER guard_fr_full_texts_update BEFORE UPDATE ON federal_register_full_texts BEGIN SELECT RAISE(ABORT, 'full text links are immutable'); END")
    op.execute("CREATE TRIGGER guard_fr_full_texts_delete BEFORE DELETE ON federal_register_full_texts BEGIN SELECT RAISE(ABORT, 'full text links are immutable'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_fr_full_texts_delete")
    op.execute("DROP TRIGGER guard_fr_full_texts_update")
    op.drop_table("federal_register_full_texts")
