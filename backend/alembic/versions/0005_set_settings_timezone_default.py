"""Set the default user timezone to India Standard Time."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_settings_timezone_default"
down_revision: Union[str, Sequence[str], None] = "0004_device_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_settings",
        "timezone",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        server_default="Asia/Kolkata",
    )


def downgrade() -> None:
    op.alter_column(
        "user_settings",
        "timezone",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        server_default="UTC",
    )