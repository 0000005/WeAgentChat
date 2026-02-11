"""add_message_voice_payload

Revision ID: c2d4e6f8a9b0
Revises: b1a2c3d4e5f6
Create Date: 2026-02-11 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2d4e6f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b1a2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voice_payload", sa.JSON(), nullable=True))

    with op.batch_alter_table("group_messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voice_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("group_messages", schema=None) as batch_op:
        batch_op.drop_column("voice_payload")

    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_column("voice_payload")

