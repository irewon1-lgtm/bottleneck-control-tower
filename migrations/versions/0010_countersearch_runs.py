"""Manual counterevidence search log; unexecuted records are explicit."""
from alembic import op
import sqlalchemy as sa

revision = "0010_countersearch_runs"
down_revision = "0009_actors"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("countersearch_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("record_key", sa.String(200), nullable=False),
        sa.Column("search_kind", sa.String(40), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("executed_on", sa.String(10)),
        sa.Column("result_status", sa.String(40), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("candidate_id", "record_key", name="uq_countersearch_candidate_key"),
        sa.CheckConstraint("search_kind IN ('SUPPLY_EXPANSION', 'NEW_SUPPLIER', 'DEMAND_SLOWDOWN', 'SUBSTITUTION', 'POLICY_CHANGE', 'OTHER')", name="ck_countersearch_kind"),
        sa.CheckConstraint("result_status IN ('NOT_RUN', 'RESULTS_FOUND', 'NO_RESULTS', 'INCONCLUSIVE', 'FAILED')", name="ck_countersearch_result"),
        sa.CheckConstraint("(result_status = 'NOT_RUN' AND executed_on IS NULL) OR (result_status != 'NOT_RUN' AND executed_on IS NOT NULL)", name="ck_countersearch_execution_date"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_countersearch_soft_delete"))
    op.execute("CREATE TRIGGER guard_countersearch_runs_delete BEFORE DELETE ON countersearch_runs BEGIN SELECT RAISE(ABORT, 'use soft delete'); END")


def downgrade():
    op.execute("DROP TRIGGER guard_countersearch_runs_delete")
    op.drop_table("countersearch_runs")
