"""add smartwatch account and sync state tables

Revision ID: ab12cd34ef56
Revises: f1a2b3c4d5e7
Create Date: 2026-03-21 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab12cd34ef56'
down_revision = 'f1a2b3c4d5e7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'smartwatch_account',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_user_id', sa.String(length=128), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('connection_status', sa.String(length=20), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('account_id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_smartwatch_account_user_provider'),
    )
    op.create_index('ix_smartwatch_account_provider', 'smartwatch_account', ['provider'], unique=False)
    op.create_index('ix_smartwatch_account_user_id', 'smartwatch_account', ['user_id'], unique=False)

    op.create_table(
        'smartwatch_sync_state',
        sa.Column('state_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('incremental_cursor', sa.String(length=255), nullable=True),
        sa.Column('incremental_since', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['smartwatch_account.account_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('state_id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_smartwatch_sync_state_user_provider'),
    )
    op.create_index('ix_smartwatch_sync_state_account_id', 'smartwatch_sync_state', ['account_id'], unique=False)
    op.create_index('ix_smartwatch_sync_state_provider', 'smartwatch_sync_state', ['provider'], unique=False)
    op.create_index('ix_smartwatch_sync_state_user_id', 'smartwatch_sync_state', ['user_id'], unique=False)


def downgrade():
    op.drop_index('ix_smartwatch_sync_state_user_id', table_name='smartwatch_sync_state')
    op.drop_index('ix_smartwatch_sync_state_provider', table_name='smartwatch_sync_state')
    op.drop_index('ix_smartwatch_sync_state_account_id', table_name='smartwatch_sync_state')
    op.drop_table('smartwatch_sync_state')

    op.drop_index('ix_smartwatch_account_user_id', table_name='smartwatch_account')
    op.drop_index('ix_smartwatch_account_provider', table_name='smartwatch_account')
    op.drop_table('smartwatch_account')
