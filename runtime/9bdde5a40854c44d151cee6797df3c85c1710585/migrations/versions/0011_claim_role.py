"""Manual Claim roles; prior Claims start as OTHER."""
from alembic import op
import sqlalchemy as sa

revision = "0011_claim_role"
down_revision = "0010_countersearch_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("claims", sa.Column("role", sa.String(20),
        sa.CheckConstraint("role IN ('DRIVER', 'CONSTRAINT', 'RELIEF', 'OTHER')", name="ck_claim_role"),
        nullable=False, server_default="OTHER"))


def downgrade():
    op.drop_column("claims", "role")
