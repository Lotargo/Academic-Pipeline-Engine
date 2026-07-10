"""add auth credentials and token version

Revision ID: 8b5214f0c3a2
Revises: fbf25766e8b5
"""
from alembic import op
import sqlalchemy as sa

revision = "8b5214f0c3a2"
down_revision = "fbf25766e8b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    # Existing users predate authentication and must reset a password before login.
    op.execute("UPDATE users SET password_hash = 'password-reset-required' WHERE password_hash IS NULL")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(512), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("token_version")
        batch_op.drop_column("password_hash")
