"""add_group_sessions

Revision ID: 8b7e6c3d2f1a
Revises: 78103eb008a2
Create Date: 2026-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.db.types import UTCDateTime


# revision identifiers, used by Alembic.
revision: str = "8b7e6c3d2f1a"
down_revision: Union[str, Sequence[str], None] = "78103eb008a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "group_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("create_time", UTCDateTime(), nullable=False),
        sa.Column("update_time", UTCDateTime(), nullable=False),
        sa.Column("ended", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_message_time", UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name=op.f("fk_group_sessions_group_id_groups")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group_sessions")),
    )
    with op.batch_alter_table("group_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_group_sessions_id"), ["id"], unique=False)
        batch_op.create_index("ix_group_sessions_group_id", ["group_id"], unique=False)

    with op.batch_alter_table("group_messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_group_messages_session_id", ["session_id"], unique=False)

    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO group_sessions (group_id, title, create_time, update_time, ended, last_message_time)
            SELECT g.id,
                   '群聊会话',
                   CURRENT_TIMESTAMP,
                   CURRENT_TIMESTAMP,
                   0,
                   MAX(m.create_time)
            FROM groups g
            LEFT JOIN group_messages m ON m.group_id = g.id
            GROUP BY g.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE group_messages
            SET session_id = (
                SELECT gs.id
                FROM group_sessions gs
                WHERE gs.group_id = group_messages.group_id
                ORDER BY gs.id DESC
                LIMIT 1
            )
            WHERE session_id IS NULL
            """
        )
    )

    with op.batch_alter_table("group_messages", schema=None) as batch_op:
        batch_op.alter_column("session_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_group_messages_session_id_group_sessions",
            "group_sessions",
            ["session_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("group_messages", schema=None) as batch_op:
        batch_op.drop_constraint("fk_group_messages_session_id_group_sessions", type_="foreignkey")
        batch_op.drop_index("ix_group_messages_session_id")
        batch_op.drop_column("session_id")

    with op.batch_alter_table("group_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_group_sessions_group_id")
        batch_op.drop_index(batch_op.f("ix_group_sessions_id"))

    op.drop_table("group_sessions")
