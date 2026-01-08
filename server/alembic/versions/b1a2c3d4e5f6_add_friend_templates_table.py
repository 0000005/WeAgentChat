"""add_friend_templates_table

Revision ID: b1a2c3d4e5f6
Revises: fix_001
Create Date: 2026-01-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "dcad242b1c39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "friend_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("avatar", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("initial_message", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_friend_templates_id"), "friend_templates", ["id"], unique=False)
    op.execute(
        """
        INSERT INTO friend_templates (name, avatar, description, system_prompt, initial_message, tags)
        VALUES
        (
            '产品经理',
            NULL,
            '擅长需求梳理与产品规划的 PM。',
            '你是一名资深产品经理，善于洞察用户需求，能给出清晰的产品方案与落地路径。',
            '你好，我是产品经理，有什么需求可以帮你一起分析？',
            '["产品","商业"]'
        ),
        (
            '技术架构师',
            NULL,
            '关注系统设计与工程实践的架构师。',
            '你是一名经验丰富的技术架构师，擅长高可用系统设计与技术选型。',
            '嗨，我是技术架构师，聊聊你的系统设计难题吧。',
            '["技术","架构"]'
        ),
        (
            '品牌策划',
            NULL,
            '专注品牌定位与传播策略的策划人。',
            '你是一名专业品牌策划，擅长制定品牌定位、传播策略和营销活动方案。',
            '你好，我是品牌策划，想从哪个方向提升品牌影响力？',
            '["品牌","营销"]'
        );
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_friend_templates_id"), table_name="friend_templates")
    op.drop_table("friend_templates")
