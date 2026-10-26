"""Create per-user settings table."""

from typing import Sequence, Union

from alembic import op
# pyrefly: ignore[missing-import]
import sqlalchemy as sa


revision: str = "0002_user_settings"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "0001_initial_schema"

branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "theme",
            sa.String(10),
            nullable=False,
            server_default="light",
        ),
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "alert_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="UTC",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            name="uq_user_settings_user_id",
        ),
    )

    op.create_index(
        "ix_user_settings_id",
        "user_settings",
        ["id"],
    )

    op.create_index(
        "ix_user_settings_user_id",
        "user_settings",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_settings_user_id",
        table_name="user_settings",
    )

    op.drop_index(
        "ix_user_settings_id",
        table_name="user_settings",
    )

    op.drop_table("user_settings")