"""Persist one-time password reset token state."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_one_time_reset_tokens"
down_revision: Union[str, Sequence[str], None] = "0005_settings_timezone_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_reset_token_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_reset_token_expires_at")
    op.drop_column("users", "password_reset_token_hash")