"""add credential envelope encryption metadata

Revision ID: c95e170be501
Revises: a47d0921be04
"""
import os
from alembic import op
import sqlalchemy as sa

revision = "c95e170be501"
down_revision = "a47d0921be04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("credentials", sa.Column("wrapped_data_key", sa.LargeBinary(), nullable=True))
    op.add_column("credentials", sa.Column("payload_nonce", sa.LargeBinary(), nullable=True))
    op.add_column("credentials", sa.Column("encryption_version", sa.Integer(), nullable=False, server_default="1"))
    connection = op.get_bind()
    ids = connection.execute(sa.text("SELECT id FROM credentials")).scalars().all()
    for credential_id in ids:
        connection.execute(sa.text("UPDATE credentials SET wrapped_data_key=:key, payload_nonce=:nonce WHERE id=:id"),
                           {"key": os.urandom(60), "nonce": os.urandom(12), "id": credential_id})
    if ids:
        # Pre-BE-05 payloads have no valid envelope metadata and must be replaced.
        connection.execute(sa.text("UPDATE credentials SET status='disabled'"))
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.alter_column("wrapped_data_key", existing_type=sa.LargeBinary(), nullable=False)
        batch_op.alter_column("payload_nonce", existing_type=sa.LargeBinary(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.drop_column("encryption_version")
        batch_op.drop_column("payload_nonce")
        batch_op.drop_column("wrapped_data_key")
