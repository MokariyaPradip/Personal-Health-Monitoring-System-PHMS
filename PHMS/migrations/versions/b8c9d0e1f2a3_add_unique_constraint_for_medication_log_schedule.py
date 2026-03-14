"""Add unique constraint for medication log schedule

Revision ID: b8c9d0e1f2a3
Revises: c1d2e3f4a5b6
Create Date: 2026-03-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # Keep the strongest row per schedule key before enforcing uniqueness.
    op.execute(
        """
        DELETE FROM medication_log
        WHERE log_id IN (
            SELECT log_id
            FROM (
                SELECT
                    log_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY medication_id, log_date, scheduled_time
                        ORDER BY
                            CASE status
                                WHEN 'taken' THEN 4
                                WHEN 'missed' THEN 3
                                WHEN 'skipped' THEN 2
                                ELSE 1
                            END DESC,
                            CASE WHEN taken_at IS NOT NULL THEN 1 ELSE 0 END DESC,
                            COALESCE(taken_at, created_at) DESC,
                            log_id ASC
                    ) AS row_num
                FROM medication_log
            ) ranked
            WHERE ranked.row_num > 1
        )
        """
    )

    with op.batch_alter_table('medication_log', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_medication_log_schedule',
            ['medication_id', 'log_date', 'scheduled_time']
        )


def downgrade():
    with op.batch_alter_table('medication_log', schema=None) as batch_op:
        batch_op.drop_constraint('uq_medication_log_schedule', type_='unique')
