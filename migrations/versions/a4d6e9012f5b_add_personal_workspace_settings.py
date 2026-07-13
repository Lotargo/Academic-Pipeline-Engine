"""add personal and workspace-member settings

Revision ID: a4d6e9012f5b
Revises: f1b7d26009e1
"""

from alembic import op
import sqlalchemy as sa


revision = "a4d6e9012f5b"
down_revision = "f1b7d26009e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="ru"),
        sa.Column("theme", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "workspace_member_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("editor_defaults_json", sa.JSON(), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=True),
        sa.Column("model_id", sa.String(length=200), nullable=True),
        sa.Column("credential_policy", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member_settings_workspace_user"),
    )
    op.create_index("ix_workspace_member_settings_user", "workspace_member_settings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_member_settings_user", table_name="workspace_member_settings")
    op.drop_table("workspace_member_settings")
    op.drop_table("user_preferences")
