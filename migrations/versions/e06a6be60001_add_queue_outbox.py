"""add queue outbox and worker delivery receipts

Revision ID: e06a6be60001
Revises: d071a6be7001
"""
from alembic import op
import sqlalchemy as sa

revision = "e06a6be60001"
down_revision = "d071a6be7001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("workload", sa.String(40), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_outbox_events_job_id"), "outbox_events", ["job_id"])
    op.create_index("ix_outbox_pending", "outbox_events", ["published_at", "available_at"])
    op.create_table("worker_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False), sa.Column("consumer", sa.String(120), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["outbox_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "consumer", name="uq_worker_delivery_event_consumer"))
    op.create_index(op.f("ix_worker_deliveries_event_id"), "worker_deliveries", ["event_id"])
    op.create_index(op.f("ix_worker_deliveries_job_id"), "worker_deliveries", ["job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_worker_deliveries_job_id"), table_name="worker_deliveries")
    op.drop_index(op.f("ix_worker_deliveries_event_id"), table_name="worker_deliveries")
    op.drop_table("worker_deliveries")
    op.drop_index("ix_outbox_pending", table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_job_id"), table_name="outbox_events")
    op.drop_table("outbox_events")
