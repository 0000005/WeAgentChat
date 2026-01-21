"""multi_provider_configs

Revision ID: 7c9a1b2d3e4f
Revises: 2f3c9b8c4f2a
Create Date: 2026-02-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9a1b2d3e4f'
down_revision: Union[str, Sequence[str], None] = '2f3c9b8c4f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_reasoning_capability(model_name: str | None) -> bool:
    if not model_name:
        return False
    lowered = model_name.lower()
    keywords = ("r1", "o1", "reasoning", "deepseek-chat", "gpt-4o")
    return any(keyword in lowered for keyword in keywords)


def _upsert_setting(conn, group_name: str, key: str, value: str, value_type: str, description: str) -> None:
    existing = conn.execute(
        sa.text(
            "SELECT id FROM system_settings WHERE group_name = :group_name AND key = :key"
        ),
        {"group_name": group_name, "key": key},
    ).fetchone()
    if existing:
        conn.execute(
            sa.text(
                """
                UPDATE system_settings
                SET value = :value, value_type = :value_type, description = :description
                WHERE id = :id
                """
            ),
            {
                "value": value,
                "value_type": value_type,
                "description": description,
                "id": existing[0],
            },
        )
    else:
        conn.execute(
            sa.text(
                """
                INSERT INTO system_settings (group_name, key, value, value_type, description)
                VALUES (:group_name, :key, :value, :value_type, :description)
                """
            ),
            {
                "group_name": group_name,
                "key": key,
                "value": value,
                "value_type": value_type,
                "description": description,
            },
        )


def upgrade() -> None:
    """Upgrade schema and migrate legacy configuration."""
    with op.batch_alter_table('llm_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('provider', sa.String(), nullable=True, server_default=sa.text("'openai'")))
        batch_op.add_column(sa.Column('config_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('capability_vision', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('capability_search', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('capability_reasoning', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('capability_function_call', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    with op.batch_alter_table('embedding_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('config_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    conn = op.get_bind()

    # Normalize provider defaults
    conn.execute(
        sa.text(
            "UPDATE llm_configs SET provider = 'openai' WHERE provider IS NULL OR provider = ''"
        )
    )

    llm_rows = conn.execute(
        sa.text(
            "SELECT id, model_name FROM llm_configs WHERE deleted = 0 ORDER BY id ASC"
        )
    ).fetchall()

    if llm_rows:
        first_id = llm_rows[0][0]
        first_model = llm_rows[0][1]
        default_name = "\u6211\u7684\u9ed8\u8ba4\u914d\u7f6e"
        conn.execute(
            sa.text(
                "UPDATE llm_configs SET config_name = :name, is_active = 1 WHERE id = :id"
            ),
            {"name": default_name, "id": first_id},
        )
        conn.execute(
            sa.text(
                """
                UPDATE llm_configs
                SET config_name = 'OpenAI'
                WHERE (config_name IS NULL OR config_name = '') AND id != :id
                """
            ),
            {"id": first_id},
        )

        if _has_reasoning_capability(first_model):
            conn.execute(
                sa.text(
                    "UPDATE llm_configs SET capability_reasoning = 1 WHERE id = :id"
                ),
                {"id": first_id},
            )

        _upsert_setting(
            conn,
            "chat",
            "active_llm_config_id",
            str(first_id),
            "int",
            "当前聊天模型配置ID",
        )

    embedding_rows = conn.execute(
        sa.text(
            "SELECT id FROM embedding_settings WHERE deleted = 0 ORDER BY id ASC"
        )
    ).fetchall()
    if embedding_rows:
        first_embedding_id = embedding_rows[0][0]
        conn.execute(
            sa.text(
                "UPDATE embedding_settings SET config_name = 'OpenAI' WHERE id = :id"
            ),
            {"id": first_embedding_id},
        )
        conn.execute(
            sa.text(
                """
                UPDATE embedding_settings
                SET config_name = 'OpenAI'
                WHERE (config_name IS NULL OR config_name = '') AND id != :id
                """
            ),
            {"id": first_embedding_id},
        )
        _upsert_setting(
            conn,
            "memory",
            "active_embedding_config_id",
            str(first_embedding_id),
            "int",
            "当前向量模型配置ID",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('embedding_settings', schema=None) as batch_op:
        batch_op.drop_column('is_verified')
        batch_op.drop_column('config_name')

    with op.batch_alter_table('llm_configs', schema=None) as batch_op:
        batch_op.drop_column('capability_function_call')
        batch_op.drop_column('capability_reasoning')
        batch_op.drop_column('capability_search')
        batch_op.drop_column('capability_vision')
        batch_op.drop_column('is_verified')
        batch_op.drop_column('is_active')
        batch_op.drop_column('config_name')
        batch_op.drop_column('provider')
