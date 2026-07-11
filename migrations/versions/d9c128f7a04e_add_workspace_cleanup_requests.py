"""add workspace cleanup confirmation ledger

Revision ID: d9c128f7a04e
Revises: a47d0921be04
"""
from alembic import op
import sqlalchemy as sa


revision = "d9c128f7a04e"
down_revision = "a47d0921be04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_cleanup_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("confirmation_token_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.Enum("pending", "completed", name="workspace_cleanup_status", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("confirmation_token_hash"),
    )
    op.create_index("ix_workspace_cleanup_requests_workspace", "workspace_cleanup_requests", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_workspace_cleanup_requests_workspace", table_name="workspace_cleanup_requests")
    op.drop_table("workspace_cleanup_requests")
