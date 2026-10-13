"""add_revocation_table_and_capability_token

Revision ID: b5e1dd5d3944
Revises: 51344ae88ae5
Create Date: 2026-10-13 07:53:36.208310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e1dd5d3944'
down_revision: Union[str, Sequence[str], None] = '51344ae88ae5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create revoked_tokens table
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_revoked_tokens_token_hash', 'revoked_tokens', ['token_hash'], unique=True)

    # 2. Add upload_capability_token_hash to reports
    op.add_column('reports', sa.Column('upload_capability_token_hash', sa.String(length=64), nullable=True))

    # 3. Add signature columns to integrity_checkpoints
    op.add_column('integrity_checkpoints', sa.Column('signature', sa.Text(), nullable=True))
    op.add_column('integrity_checkpoints', sa.Column('signer_public_key', sa.Text(), nullable=True))
    op.add_column('integrity_checkpoints', sa.Column('signature_algorithm', sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('integrity_checkpoints', 'signature_algorithm')
    op.drop_column('integrity_checkpoints', 'signer_public_key')
    op.drop_column('integrity_checkpoints', 'signature')
    op.drop_column('reports', 'upload_capability_token_hash')
    op.drop_index('ix_revoked_tokens_token_hash', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
