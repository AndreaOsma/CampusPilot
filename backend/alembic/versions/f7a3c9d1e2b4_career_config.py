"""career_config: reglas de la universidad por carrera (escala, aprobado, créditos, calendario, nombres)

Revision ID: f7a3c9d1e2b4
Revises: e4f1b7c2a9d0
Create Date: 2026-10-13 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a3c9d1e2b4"
down_revision: Union[str, None] = "e4f1b7c2a9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # '{}' = valores por defecto (0–10, aprobado 5, ECTS, semestres): el comportamiento de siempre.
    with op.batch_alter_table("careers") as batch:
        batch.add_column(sa.Column("config", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("careers") as batch:
        batch.drop_column("config")
