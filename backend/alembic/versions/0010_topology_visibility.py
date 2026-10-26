"""Persist topology suppression without deleting devices."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_topology_visibility"
down_revision: Union[str, Sequence[str], None] = "0009_speed_agent_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("topology_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "devices",
        sa.Column("mac_address", sa.String(length=17), nullable=True),
    )
    op.create_index(
        "ix_devices_mac_address",
        "devices",
        ["mac_address"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_devices_mac_address", table_name="devices")
    op.drop_column("devices", "mac_address")
    op.drop_column("devices", "topology_hidden")
