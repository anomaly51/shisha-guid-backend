from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "1234567890ab"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("role", sa.String(), server_default="user", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("users", "role")
