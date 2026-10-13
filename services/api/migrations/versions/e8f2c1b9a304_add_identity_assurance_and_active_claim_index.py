"""add_identity_assurance_and_active_claim_index

Revision ID: e8f2c1b9a304
Revises: c7a3b4e12f01
Create Date: 2026-10-13 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f2c1b9a304'
down_revision: Union[str, Sequence[str], None] = 'c7a3b4e12f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add identity assurance to users and partial unique index on active resolution claims."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('is_identity_verified', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column('identity_provider', sa.String(length=50), nullable=True)
        )

    op.create_index(
        'uq_active_resolution_claim_per_case',
        'resolution_claims',
        ['case_id'],
        unique=True,
        sqlite_where=sa.text("status = 'AWAITING_VERIFICATION'"),
        postgresql_where=sa.text("status = 'AWAITING_VERIFICATION'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_active_resolution_claim_per_case', table_name='resolution_claims')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('identity_provider')
        batch_op.drop_column('is_identity_verified')
