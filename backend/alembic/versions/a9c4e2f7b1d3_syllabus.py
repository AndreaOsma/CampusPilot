"""syllabus: plan docente por asignatura (objetivos, temario, recursos), módulo de cada unidad y objetivos de cada paso

Revision ID: a9c4e2f7b1d3
Revises: f7a3c9d1e2b4
Create Date: 2026-10-16 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c4e2f7b1d3"
down_revision: Union[str, None] = "f7a3c9d1e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # '{}' = sin plan docente importado.
    with op.batch_alter_table("subjects") as batch:
        batch.add_column(sa.Column("syllabus", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("course_units") as batch:
        batch.add_column(sa.Column("module_ref", sa.String(64), nullable=False, server_default=""))
    with op.batch_alter_table("lesson_steps") as batch:
        batch.add_column(sa.Column("objectives", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("lesson_steps") as batch:
        batch.drop_column("objectives")
    with op.batch_alter_table("course_units") as batch:
        batch.drop_column("module_ref")
    with op.batch_alter_table("subjects") as batch:
        batch.drop_column("syllabus")
