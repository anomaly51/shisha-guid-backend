"""add user role index

Revision ID: 20260528_0005
Revises: 20260528_0004
Create Date: 2026-05-28
"""
from alembic import op

revision = "20260528_0005"
down_revision = "20260528_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_role")
