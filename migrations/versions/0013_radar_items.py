"""Lightweight discovery metadata, without article bodies."""
from alembic import op
import sqlalchemy as sa

revision = "0013_radar_items"
down_revision = "0012_research_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("radar_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(2000), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("published_at", sa.String(40)),
        sa.Column("collected_at", sa.String(40), nullable=False),
        sa.Column("snippet", sa.String(1000)),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("source", "external_id", name="uq_radar_source_external"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_radar_soft_delete"))
    op.create_index("ix_radar_published_at", "radar_items", ["published_at"])
    op.create_index("ix_radar_collected_at", "radar_items", ["collected_at"])
    op.execute("CREATE TRIGGER guard_radar_items_delete BEFORE DELETE ON radar_items BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_radar_items_delete")
    op.drop_index("ix_radar_collected_at", table_name="radar_items")
    op.drop_index("ix_radar_published_at", table_name="radar_items")
    op.drop_table("radar_items")
