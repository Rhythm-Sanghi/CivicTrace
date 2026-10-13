"""add_sequence_counters_table

Revision ID: c7a3b4e12f01
Revises: b5e1dd5d3944
Create Date: 2026-10-13 08:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a3b4e12f01'
down_revision: Union[str, Sequence[str], None] = 'b5e1dd5d3944'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add sequence_counters table for database-enforced monotonic ID allocation."""
    op.create_table(
        'sequence_counters',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('name'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('sequence_counters')
