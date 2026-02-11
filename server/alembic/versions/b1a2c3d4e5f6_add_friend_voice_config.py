"""add_friend_voice_config

Revision ID: b1a2c3d4e5f6
Revises: 3d7944bf1dae
Create Date: 2026-02-11 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3d7944bf1dae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('friends', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('enable_voice', sa.Boolean(), nullable=False, server_default=sa.text('0'))
        )
        batch_op.add_column(
            sa.Column('voice_id', sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('friends', schema=None) as batch_op:
        batch_op.drop_column('voice_id')
        batch_op.drop_column('enable_voice')
