"""Add unique constraint for alert deduplication

Revision ID: c1d2e3f4a5b6
Revises: a3f1b2c4d5e6
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'a3f1b2c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Remove duplicate alert rows for the same medication_log_id/title pair
    # before enforcing uniqueness at the database layer.
    op.execute(sa.text("""
        DELETE FROM alert
        WHERE alert_id NOT IN (
            SELECT MIN(alert_id)
            FROM alert
            WHERE medication_log_id IS NOT NULL
              AND title IS NOT NULL
            GROUP BY medication_log_id, title
        )
          AND medication_log_id IS NOT NULL
          AND title IS NOT NULL
    """))

    with op.batch_alter_table('alert', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_alert_medication_log_title',
            ['medication_log_id', 'title']
        )


def downgrade():
    with op.batch_alter_table('alert', schema=None) as batch_op:
        batch_op.drop_constraint('uq_alert_medication_log_title', type_='unique')
