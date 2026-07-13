"""add external identity links

Revision ID: f1b7d26009e1
Revises: m001_merge_cleanup_and_outbox
"""

from alembic import op
import sqlalchemy as sa


revision = "f1b7d26009e1"
down_revision = "m001_merge_cleanup_and_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "provider_subject", name="uq_external_identities_issuer_subject"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_external_identities_provider_subject"),
    )
    op.create_index("ix_external_identities_user", "external_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_external_identities_user", table_name="external_identities")
    op.drop_table("external_identities")
