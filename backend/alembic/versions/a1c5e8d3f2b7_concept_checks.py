"""concept_checks: comprobador Feynman (explicaciones por concepto y su valoración)

Revision ID: a1c5e8d3f2b7
Revises: e5f1a9c3b7d2
Create Date: 2026-10-28 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c5e8d3f2b7"
down_revision: Union[str, None] = "e5f1a9c3b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "concept_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept", sa.String(120), nullable=False),
        sa.Column("rating", sa.String(12), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    op.drop_table("concept_checks")
