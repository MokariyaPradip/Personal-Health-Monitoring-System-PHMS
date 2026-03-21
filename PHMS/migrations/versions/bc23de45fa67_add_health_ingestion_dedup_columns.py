"""add health ingestion dedup columns

Revision ID: bc23de45fa67
Revises: ab12cd34ef56
Create Date: 2026-03-21 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc23de45fa67'
down_revision = 'ab12cd34ef56'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_source', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('source_record_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('ingestion_fingerprint', sa.String(length=64), nullable=True))

    op.execute("UPDATE health_data SET data_source = 'manual' WHERE data_source IS NULL")

    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.alter_column('data_source', existing_type=sa.String(length=30), nullable=False)
        batch_op.create_index('ix_health_data_ingestion_fingerprint', ['ingestion_fingerprint'], unique=False)
        batch_op.create_unique_constraint(
            'uq_health_user_source_record',
            ['user_id', 'data_source', 'source_record_id'],
        )
        batch_op.create_unique_constraint(
            'uq_health_user_fingerprint',
            ['user_id', 'ingestion_fingerprint'],
        )


def downgrade():
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.drop_constraint('uq_health_user_fingerprint', type_='unique')
        batch_op.drop_constraint('uq_health_user_source_record', type_='unique')
        batch_op.drop_index('ix_health_data_ingestion_fingerprint')
        batch_op.drop_column('ingestion_fingerprint')
        batch_op.drop_column('source_record_id')
        batch_op.drop_column('data_source')
