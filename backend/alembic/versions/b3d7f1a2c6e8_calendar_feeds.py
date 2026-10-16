"""calendar_feeds: enlaces iCal del campus virtual que se sincronizan con la agenda

Revision ID: b3d7f1a2c6e8
Revises: a9c4e2f7b1d3
Create Date: 2026-10-16 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d7f1a2c6e8"
down_revision: Union[str, None] = "a9c4e2f7b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_feeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(12), nullable=False, server_default="events"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("items", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("calendar_feeds")
