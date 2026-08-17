"""add max_connections to routes

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('routes', sa.Column('max_connections', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('routes', 'max_connections')
