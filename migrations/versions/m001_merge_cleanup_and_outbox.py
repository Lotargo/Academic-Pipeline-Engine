"""merge workspace_cleanup_requests and queue_outbox heads

Revision ID: m001_merge_cleanup_and_outbox
Revises: e06a6be60001, d9c128f7a04e
"""
from alembic import op
import sqlalchemy as sa


revision = "m001_merge_cleanup_and_outbox"
down_revision = ("e06a6be60001", "d9c128f7a04e")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
