"""Track configured scanner networks and device-agent availability."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_speed_agent_readiness"
down_revision: Union[str, Sequence[str], None] = "0008_per_device_speed_tests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("speed_agent_seen_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "agent_discovered_networks",
        sa.Column("cidr", sa.String(length=43), nullable=False),
        sa.Column("last_reported_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cidr"),
    )


def downgrade() -> None:
    op.drop_table("agent_discovered_networks")
    op.drop_column("devices", "speed_agent_seen_at")
