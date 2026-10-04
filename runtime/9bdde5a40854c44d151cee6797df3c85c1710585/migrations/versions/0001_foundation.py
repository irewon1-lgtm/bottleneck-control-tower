"""Stage 0 foundation schema and immutable guards."""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def pk():
    return sa.Column("id", sa.String(36), primary_key=True)


def timestamps():
    return (sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False))


def upgrade():
    op.create_table("raw_documents", pk(),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("external_key", sa.String(500), nullable=False),
        sa.Column("external_id", sa.String(500)),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("relative_path", sa.String(150), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False), *timestamps(),
        sa.UniqueConstraint("source", "external_key", "sha256", name="uq_raw_identity"))
    op.create_index("ix_raw_documents_sha256", "raw_documents", ["sha256"])
    op.create_table("entities", pk(),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("stable_key", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), *timestamps(),
        sa.Column("deleted_at", sa.String(40)),
        sa.UniqueConstraint("kind", "stable_key", name="uq_entity_key"),
        sa.CheckConstraint("(status = 'active' AND deleted_at IS NULL) OR (status = 'deleted' AND deleted_at IS NOT NULL)", name="ck_entity_soft_delete"))
    op.create_table("collector_runs", pk(),
        sa.Column("collector", sa.String(120), nullable=False),
        sa.Column("run_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()), *timestamps(),
        sa.UniqueConstraint("collector", "run_key", name="uq_collector_run"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed')", name="ck_run_status"))
    op.create_table("jobs", pk(),
        sa.Column("job_type", sa.String(120), nullable=False),
        sa.Column("job_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.String(40)),
        sa.Column("last_error", sa.Text()), *timestamps(),
        sa.UniqueConstraint("job_type", "job_key", name="uq_job_identity"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed')", name="ck_job_status"))
    op.create_table("audit_log", pk(),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("evidence_freezes", pk(),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False), *timestamps(),
        sa.UniqueConstraint("version", name="uq_freeze_version"))
    for table in ("raw_documents", "audit_log", "evidence_freezes"):
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER guard_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, '{table} is immutable'); END")
    for table in ("entities", "collector_runs", "jobs"):
        op.execute(f"CREATE TRIGGER guard_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'use soft delete or status transitions'); END")


def downgrade():
    for table in ("entities", "collector_runs", "jobs"):
        op.execute(f"DROP TRIGGER guard_{table}_delete")
    for table in ("raw_documents", "audit_log", "evidence_freezes"):
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER guard_{table}_{action}")
    for table in ("evidence_freezes", "audit_log", "jobs", "collector_runs", "entities", "raw_documents"):
        op.drop_table(table)
