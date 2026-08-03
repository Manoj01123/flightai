"""add passenger fields, is_admin, fcm_token to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("users", sa.Column("date_of_birth", sa.Date, nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(10), nullable=True))
    op.add_column("users", sa.Column("title", sa.String(10), nullable=True))
    op.add_column("users", sa.Column("fcm_token", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "fcm_token")
    op.drop_column("users", "title")
    op.drop_column("users", "gender")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "is_admin")
