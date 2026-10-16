"""inbox_messages

Revision ID: 5e1c0a7b9d21
Revises: 0bd2864fb7bf
Create Date: 2026-10-12 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e1c0a7b9d21'
down_revision: Union[str, None] = '0bd2864fb7bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inbox_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(length=500), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('sender', sa.String(length=320), nullable=False),
        sa.Column('recipient', sa.String(length=320), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('proposals', sa.JSON(), nullable=False),
        sa.Column('classify_status', sa.String(length=16), nullable=False),
        sa.Column('classify_error', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
    )


def downgrade() -> None:
    op.drop_table('inbox_messages')
