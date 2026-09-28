"""mcp_usage: MCP tool calls per day and tool (counts only, no caller data)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("tool", sa.String(64), primary_key=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refused", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ms", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("mcp_usage")
