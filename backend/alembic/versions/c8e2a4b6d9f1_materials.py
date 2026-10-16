"""materials: biblioteca de materiales de estudio por asignatura

Revision ID: c8e2a4b6d9f1
Revises: b3d7f1a2c6e8
Create Date: 2026-10-16 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e2a4b6d9f1"
down_revision: Union[str, None] = "b3d7f1a2c6e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_ref", sa.String(64), nullable=False, server_default=""),
        sa.Column("kind", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("has_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    op.drop_table("materials")
