"""add durable job lifecycle

Revision ID: d071a6be7001
Revises: c95e170be501
"""
from alembic import op
import sqlalchemy as sa

revision = "d071a6be7001"
down_revision = "c95e170be501"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("current_stage", sa.String(120)))
    op.add_column("jobs", sa.Column("progress", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("active_attempt", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column("jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    op.create_table("job_stages",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "name", name="uq_job_stages_job_name"))
    op.create_index(op.f("ix_job_stages_job_id"), "job_stages", ["job_id"])
    op.create_table("job_attempts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("running", "succeeded", "failed", "interrupted", name="attempt_status", native_enum=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("worker_id", sa.String(200)),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "number", name="uq_job_attempts_job_number"))
    op.create_index(op.f("ix_job_attempts_job_id"), "job_attempts", ["job_id"])
    op.create_table("job_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False), sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_job_events_job_created", "job_events", ["job_id", "created_at"])
    op.create_table("job_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(120), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "stage", name="uq_job_checkpoints_job_stage"))
    op.create_index(op.f("ix_job_checkpoints_job_id"), "job_checkpoints", ["job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_job_checkpoints_job_id"), table_name="job_checkpoints"); op.drop_table("job_checkpoints")
    op.drop_index("ix_job_events_job_created", table_name="job_events"); op.drop_table("job_events")
    op.drop_index(op.f("ix_job_attempts_job_id"), table_name="job_attempts"); op.drop_table("job_attempts")
    op.drop_index(op.f("ix_job_stages_job_id"), table_name="job_stages"); op.drop_table("job_stages")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("cancel_requested_at"); batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("active_attempt"); batch_op.drop_column("progress"); batch_op.drop_column("current_stage")
