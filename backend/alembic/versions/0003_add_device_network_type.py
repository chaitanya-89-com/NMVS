"""Add network type to devices."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_device_network_type"
down_revision: Union[str, Sequence[str], None] = "0002_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "network_type",
            sa.String(),
            nullable=False,
            server_default="Unknown",
        ),
    )


def downgrade() -> None:
    op.drop_column("devices", "network_type")