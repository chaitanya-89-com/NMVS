"""Track whether devices were entered manually or discovered by scan."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_device_source"
down_revision: Union[str, Sequence[str], None] = "0003_device_network_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
    )
    op.create_index("ix_devices_source", "devices", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_devices_source", table_name="devices")
    op.drop_column("devices", "source")