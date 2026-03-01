"""Rename ML columns to distinguish regression vs classifier

Rename ml_predicted_health_score → ml_regression_health_score (regression-based)
Rename ml_predicted_risk_label → ml_classifier_risk_label (classifier-based)

Revision ID: e4e5f6a7b8c9
Revises: d7e8f9a0b1c2
Create Date: 2026-03-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4e5f6a7b8c9'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    """Rename columns to distinguish regression vs classifier predictions"""
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.alter_column('ml_predicted_health_score', new_column_name='ml_regression_health_score')
        batch_op.alter_column('ml_predicted_risk_label', new_column_name='ml_classifier_risk_label')


def downgrade():
    """Revert column names to original"""
    with op.batch_alter_table('health_data', schema=None) as batch_op:
        batch_op.alter_column('ml_regression_health_score', new_column_name='ml_predicted_health_score')
        batch_op.alter_column('ml_classifier_risk_label', new_column_name='ml_predicted_risk_label')
