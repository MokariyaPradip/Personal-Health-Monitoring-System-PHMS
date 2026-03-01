"""Remove rule_based_risk_label from health_data

Revision ID: d7e8f9a0b1c2
Revises: 52c26be4e468
Create Date: 2026-03-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e8f9a0b1c2'
down_revision = '52c26be4e468'
branch_labels = None
depends_on = None


def upgrade():
    """Remove rule_based_risk_label column as it's redundant (can be computed from health_score)"""
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.drop_column('rule_based_risk_label')


def downgrade():
    """Restore rule_based_risk_label column"""
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rule_based_risk_label', sa.String(length=20), nullable=True))
