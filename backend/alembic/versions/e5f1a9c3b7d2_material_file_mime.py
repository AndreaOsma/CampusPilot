"""material: tipo del fichero guardado (PDF o vídeo)

Revision ID: e5f1a9c3b7d2
Revises: c8e2a4b6d9f1
Create Date: 2026-10-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f1a9c3b7d2"
down_revision: Union[str, None] = "c8e2a4b6d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("materials") as batch:
        batch.add_column(sa.Column("file_mime", sa.String(40), nullable=False, server_default=""))
    op.execute("UPDATE materials SET file_mime = 'application/pdf' WHERE has_file = 1")


def downgrade() -> None:
    with op.batch_alter_table("materials") as batch:
        batch.drop_column("file_mime")
