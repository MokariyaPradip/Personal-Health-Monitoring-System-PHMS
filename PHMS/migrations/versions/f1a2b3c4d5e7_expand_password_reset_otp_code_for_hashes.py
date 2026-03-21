"""Expand password reset OTP storage for hashed values

Revision ID: f1a2b3c4d5e7
Revises: b8c9d0e1f2a3
Create Date: 2026-03-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e7'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('password_reset_otp', schema=None) as batch_op:
        batch_op.alter_column(
            'otp_code',
            existing_type=sa.String(length=6),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table('password_reset_otp', schema=None) as batch_op:
        batch_op.alter_column(
            'otp_code',
            existing_type=sa.String(length=255),
            type_=sa.String(length=6),
            existing_nullable=False,
        )
